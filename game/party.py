"""The party: the player's fighter and the AI companion who casts bolts and heals."""

import math
import random

from pyxel.cube import Mat4, Node, Vec3

from enemies import line_of_sight
from objects import cell_of
from palette import FIRE_I, WHITE

ATTACK_COOLDOWN = 36  # frames between sword swings
SWORD_REACH = 130.0  # horizontal distance to the enemy's center
SWORD_DAMAGE = (4, 7)

BOLT_SPEED = 9.0
BOLT_DAMAGE = (3, 5)
BOLT_COOLDOWN = 95
BOLT_RANGE = 600.0
HEAL_COOLDOWN = 540
HEAL_AMOUNT = 12
REGEN_AFTER = 300  # frames out of combat before wounds slowly close


class Member:
    def __init__(self, name, role, max_hp):
        self.name = name
        self.role = role
        self.max_hp = max_hp
        self.hp = max_hp
        self.cooldown = 0
        self.cooldown_max = 1
        self.hit_flash = 0

    @property
    def up(self):
        return self.hp > 0

    def damage(self, amount):
        self.hp = max(0, self.hp - amount)
        self.hit_flash = 12

    def heal(self, amount):
        self.hp = min(self.max_hp, self.hp + amount)

    def busy(self, frames):
        self.cooldown = self.cooldown_max = frames


class Party:
    def __init__(self):
        self.fighter = Member("Arn", "fighter", 40)
        self.mage = Member("Mira", "mage", 28)
        self.members = (self.fighter, self.mage)
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

    def snapshot(self):
        return [(m.hp, m.cooldown) for m in self.members]

    def restore(self, snap):
        for m, (hp, cd) in zip(self.members, snap):
            m.hp, m.cooldown, m.hit_flash = hp, cd, 0

    def tick(self):
        for m in self.members:
            m.cooldown = max(0, m.cooldown - 1)
            m.hit_flash = max(0, m.hit_flash - 1)
        self.heal_cooldown = max(0, self.heal_cooldown - 1)

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
        if self.heal_cooldown == 0 and hurt.hp < hurt.max_hp * (0.45 if foes else 0.8):
            hurt.heal(HEAL_AMOUNT if hurt.up else HEAL_AMOUNT // 2)
            self.heal_cooldown = HEAL_COOLDOWN
            mage.busy(60)
            world.sfx.play("heal")
            who = "you" if hurt is fighter else "herself"
            world.messages.add(f"{mage.name} heals {who}." if hurt.up else f"{mage.name} revives {hurt.name}.")
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
        floor.add_bolt(Bolt(start, aim * BOLT_SPEED))
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
class Bolt:
    def __init__(self, pos, vel):
        self.pos = pos
        self.vel = vel
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
        flicker = (self.bolt.age // 2) % 2
        self.sphere(Vec3.ZERO, 5 + flicker, FIRE_I[5] if flicker else WHITE)
        tail = self.bolt.vel * -0.8
        self.sphere(tail, 3, FIRE_I[3])
        self.sphere(tail * 2, 2, FIRE_I[2])
