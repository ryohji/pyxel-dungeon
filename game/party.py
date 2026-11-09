"""The party: stats, skills and belongings, and the AI companion who casts bolts and heals.

The numbers live in data/*.csv (see tables.py)."""

import copy
import math
import random

from pyxel.cube import Mat4, Node, Vec3

from enemies import line_of_sight
from objects import cell_of
from palette import BLUE_I, FIRE_I, MOSS_I, WHITE
from tables import KIT, LEVELS, MEMBERS, SKILLS, STATS, TUNE, xp_for
from things import Thing

SWORD_REACH = 130.0  # horizontal distance to the enemy's center

BOLT_SPEED = 9.0
BOLT_COOLDOWN = 95
BOLT_RANGE = 600.0
HEAL_COOLDOWN = 540
REGEN_AFTER = 300  # frames out of combat before wounds slowly close
SLOTS = ("right", "left", "head", "body")
PACK_SIZE = 8


class Member:
    """A party member: stats from data/members.csv, skills, belongings, hunger."""

    def __init__(self, name):
        row = MEMBERS[name]
        self.name = name
        self.role = row["role"]
        self.stats = {k: row[k] for k in STATS}  # hp / stamina / mana are the maxima
        self.hp = self.max_hp
        self.stamina = float(self.stats["stamina"])
        self.mana = float(self.stats["mana"])
        self.level = {s: row[s] for s in SKILLS}
        self.xp = {s: xp_for(s, row[s]) for s in SKILLS}
        self.food = float(TUNE["food_start"])
        self.water = float(TUNE["water_start"])
        self.equip = dict.fromkeys(SLOTS)
        self.pack = [None] * PACK_SIZE
        self.cooldown = 0
        self.cooldown_max = 1
        self.hit_flash = 0
        self.starve_tick = 0
        self.warned = set()  # 'hungry' / 'thirsty' already said

    # ------------------------------------------------------------ stats
    @property
    def max_hp(self):
        return self.stats["hp"]

    @property
    def max_stamina(self):
        return self.stats["stamina"]

    @property
    def max_mana(self):
        return self.stats["mana"]

    @property
    def up(self):
        return self.hp > 0

    @property
    def tired(self):
        return self.stamina < TUNE["tired_below"]

    @property
    def defense(self):
        return sum(t.row["defense"] for t in self.equip.values() if t is not None)

    @property
    def light(self):
        return max((t.light for s in ("right", "left") if (t := self.equip[s]) is not None), default=0.0)

    def damage(self, amount):
        self.hp = max(0, self.hp - amount)
        self.hit_flash = 12

    def heal(self, amount):
        self.hp = min(self.max_hp, self.hp + amount)

    def busy(self, frames):
        self.cooldown = self.cooldown_max = frames

    def bonus(self, stat, per_key, skill):
        """Extra damage from a stat and a skill level, as set in tuning.csv."""
        return self.stats[stat] // TUNE[per_key] + (self.level[skill] - 1) // TUNE["level_per_damage"]

    def gain_xp(self, skill, amount):
        """Add xp; returns the levels reached (stats grow per data/skills.csv)."""
        self.xp[skill] += amount
        reached = []
        for lv, need, gains in LEVELS[skill]:
            if lv > self.level[skill] and self.xp[skill] >= need:
                self.level[skill] = lv
                for k, g in gains.items():
                    self.stats[k] += g
                self.hp += gains["hp"] if self.up else 0
                self.stamina += gains["stamina"]
                self.mana += gains["mana"]
                reached.append(lv)
        return reached

    # ------------------------------------------------------------ belongings
    def give(self, thing):
        """Put a thing in the first free pack slot; False if the pack is full."""
        for i, t in enumerate(self.pack):
            if t is None:
                self.pack[i] = thing
                return True
        return False

    def consume(self, thing):
        """Eat or drink. Returns (message, used_up) or None if it is not food or drink."""
        row = thing.row
        if row["food"]:
            self.food = min(100.0, self.food + row["food"])
            self.warned.discard("hungry")
            return f"{self.name} eats {thing.name}.", True
        if row["water"]:
            if thing.charges <= 0:
                return "It is empty.", False
            thing.charges -= 1
            self.water = min(100.0, self.water + row["water"])
            self.warned.discard("thirsty")
            return f"{self.name} drinks.", False
        return None


class Party:
    def __init__(self):
        self.fighter = Member("Arn")
        self.mage = Member("Mira")
        self.members = (self.fighter, self.mage)
        self.leader = self.fighter  # the member the player controls (casts the runes)
        self.wards = {}  # element -> [frames left, amount]: spells laid on the whole party
        by_name = {m.name: m for m in self.members}
        for row in KIT:
            m = by_name[row["member"]]
            thing = Thing(row["kind"])
            if row["slot"] == "pack":
                m.give(thing)
            else:
                m.equip[row["slot"]] = thing
        self.heal_cooldown = 0
        self.focus = None  # the enemy the companion is watching
        self.spotted = 0  # frames since the companion first saw it
        self.calm = 0  # frames since the last fight
        self.regen_tick = 0
        self.rnd = random.Random()

    @property
    def alive(self):
        return any(m.up for m in self.members)

    def front(self):
        """Who takes a blow: the fighter, unless the fighter is down."""
        return self.fighter if self.fighter.up else self.mage

    @property
    def light(self):
        """0..1: the brightest torch anyone holds, or a Light ward."""
        if not self.alive:
            return 0.0
        return max(1.0 if "light" in self.wards else 0.0, *(m.light for m in self.members if m.up))

    def add_ward(self, element, frames, amount):
        old = self.wards.get(element)
        if old is None or old[0] < frames:
            self.wards[element] = [frames, max(amount, old[1] if old else 0)]

    def ward(self, element):
        """The strength of an active ward, or 0."""
        w = self.wards.get(element)
        return w[1] if w else 0

    def snapshot(self):
        return copy.deepcopy([m.__dict__ for m in self.members])

    def restore(self, snap):
        self.wards.clear()
        for m, state in zip(self.members, copy.deepcopy(snap)):
            m.__dict__.update(state)
            m.hit_flash = 0

    def tick(self):
        """Every frame the game runs: cooldowns, regaining stamina and mana."""
        for m in self.members:
            m.cooldown = max(0, m.cooldown - 1)
            m.hit_flash = max(0, m.hit_flash - 1)
            if not m.up:
                continue
            starving = m.food <= 0 or m.water <= 0
            regen = TUNE["stamina_regen"] / 60 * (0.3 if starving else 1.0)
            m.stamina = min(m.max_stamina, m.stamina + regen)
            m.mana = min(m.max_mana, m.mana + (TUNE["mana_regen"] + m.stats["wis"] / 20) / 60)
        self.heal_cooldown = max(0, self.heal_cooldown - 1)
        for element, w in list(self.wards.items()):
            w[0] -= 1
            if element == "life" and w[0] % 120 == 0:
                for m in self.members:
                    if m.up:
                        m.heal(w[1])
            if w[0] <= 0:
                del self.wards[element]

    def needs(self, messages):
        """Hunger, thirst and torches burning down, once per frame."""
        for m in self.members:
            for t in (m.equip["right"], m.equip["left"]):
                if t is not None and t.kind == "torch" and t.fuel > 0:
                    t.fuel -= 1
                    if t.fuel == 0:
                        messages.add(f"{m.name}'s torch burns out.")
            if not m.up:
                continue
            m.food = max(0.0, m.food - TUNE["food_per_min"] / 3600)
            m.water = max(0.0, m.water - TUNE["water_per_min"] / 3600)
            for need, value in (("hungry", m.food), ("thirsty", m.water)):
                if value < TUNE["hungry_below"] and need not in m.warned:
                    m.warned.add(need)
                    messages.add(f"{m.name} is {need}.")
            if m.food <= 0 or m.water <= 0:
                m.starve_tick += 1
                if m.starve_tick >= TUNE["starve_hp_sec"] * 60:
                    m.starve_tick = 0
                    if m.hp > 1:
                        m.hp -= 1
                        m.hit_flash = 6

    # ------------------------------------------------------------ companion
    def companion(self, world, floor):
        """Mira's turn: heal when the party is hurt, else bolt the nearest foe in sight."""
        mage, fighter = self.mage, self.fighter
        p = world.player
        foes = [e for e in floor.enemies if e.alive and e.state != "idle"]
        if foes:
            self.calm = 0
        else:
            self.calm += 1
            self._regen()
        if not mage.up or mage.cooldown:
            return
        hurt = min(self.members, key=lambda m: m.hp / m.max_hp)
        if (self.heal_cooldown == 0 and mage.mana >= TUNE["heal_mana"]
                and hurt.hp < hurt.max_hp * (0.45 if foes else 0.8)):
            amount = TUNE["heal_base"] + mage.stats["wis"] // TUNE["wis_per_heal"] + mage.level["priest"] - 1
            if not hurt.up:
                amount //= 2
            before = hurt.hp
            hurt.heal(amount)
            mage.mana -= TUNE["heal_mana"]
            self.heal_cooldown = HEAL_COOLDOWN
            mage.busy(60)
            world.sfx.play("heal")
            who = "you" if hurt is fighter else "herself"
            world.messages.add(f"{mage.name} heals {who}." if before else f"{mage.name} revives {hurt.name}.")
            world.award(mage, "priest", (hurt.hp - before) * TUNE["xp_heal"])
            return
        if mage.mana < TUNE["bolt_mana"]:
            return
        target = None
        best = BOLT_RANGE
        yr = math.radians(p.yaw)
        fx, fz = math.sin(yr), -math.cos(yr)
        for e in foes:
            dx, dz = e.x - p.x, e.z - p.z
            d = math.hypot(dx, dz)
            if d < best and (dx * fx + dz * fz) > d * 0.35 and line_of_sight(floor.solid, p.x, p.z, e.x, e.z):
                target, best = e, d
        if target is not self.focus:
            self.focus, self.spotted = target, 0
        if target is None:
            return
        self.spotted += 1
        if self.spotted < 25:  # a moment to take aim
            return
        eye = p.eye
        right = Vec3(-fz, 0, fx)
        start = eye + right * 14 + Vec3(0, -10, 0)
        aim = (target.center - start).normalize()
        damage = self.rnd.randint(TUNE["bolt_min"], TUNE["bolt_max"]) + mage.bonus("wis", "wis_per_bolt", "wizard")
        floor.add_bolt(Bolt(start, aim * BOLT_SPEED, mage, damage))
        mage.mana -= TUNE["bolt_mana"]
        world.sfx.play("bolt")
        mage.busy(BOLT_COOLDOWN)

    def _regen(self):
        if self.calm < REGEN_AFTER:
            return
        self.regen_tick += 1
        if self.regen_tick % 90 == 0:
            for m in self.members:
                if m.up:
                    m.heal(1)


# ---------------------------------------------------------------- bolts
BOLT_COLORS = {  # element -> (core, glow, tail)
    None: (FIRE_I[5], WHITE, FIRE_I[3]),
    "fire": (FIRE_I[5], FIRE_I[4], FIRE_I[2]),
    "frost": (WHITE, BLUE_I[2], BLUE_I[1]),
    "light": (WHITE, FIRE_I[5], FIRE_I[4]),
    "life": (MOSS_I[2], WHITE, MOSS_I[1]),
}

class Bolt:
    def __init__(self, pos, vel, caster=None, damage=3, element=None, power=1):
        self.pos = pos
        self.vel = vel
        self.caster = caster
        self.damage = damage
        self.element = element  # None: Mira's own bolt; else a rune spell's element
        self.power = power
        self.age = 0
        self.done = False
        self.node = BoltNode(self)

    @property
    def cell(self):
        return cell_of(self.pos.x, self.pos.z)

    def step(self, floor):
        """Advance; returns the enemy hit, 'wall', or None."""
        self.age += 1
        for _ in range(3):
            self.pos = self.pos + self.vel * (1 / 3)
            for e in floor.enemies:
                if e.alive and (self.pos - e.center).length() < 26:
                    return e
            if floor.solid(*self.cell) or not 0 < self.pos.y < 100 or self.age > 120:
                return "wall"
        self.node.refresh()
        return None


class BoltNode(Node):
    def __init__(self, bolt):
        super().__init__()
        self.bolt = bolt
        self.refresh()

    def refresh(self):
        self.transform = Mat4.from_translation(self.bolt.pos)

    def on_draw(self):
        self.shaded(False)
        b = self.bolt
        flicker = (b.age // 2) % 2
        core, glow, tail_col = BOLT_COLORS[b.element]
        size = 5 + (b.power - 1)
        self.sphere(Vec3.ZERO, size + flicker, core if flicker else glow)
        tail = b.vel * -0.8
        self.sphere(tail, size - 2, tail_col)
        self.sphere(tail * 2, max(1, size - 3), tail_col)
