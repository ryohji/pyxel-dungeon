"""Rune magic: three runes (power, element, shape) make a spell.

  power    1-4: multiplies the mana cost and the strength or duration
  element  fire, frost, light, life
  shape    bolt (flies at the target), ward (on the party for a while),
           burst (everything close around the caster), wall (fills the
           cell in front for a while)

The numbers for each element + shape are in data/spells.csv. A power rune
may be at most `power_over_skill` levels above the caster's skill (wizard,
or priest for life); above that the runes fizzle and some mana is lost.
"""

import math
import random

from pyxel.cube import Mat4, Node, Vec3

from dungeon import CELL, WALL_H
from objects import cell_center, cell_of
from palette import BLUE_I, FIRE_I, MOSS_I, STONE_I, WHITE
from party import BOLT_SPEED, Bolt
from tables import TUNE, rows

POWERS = (1, 2, 3, 4)
ELEMENTS = ("fire", "frost", "light", "life")
SHAPES = ("bolt", "ward", "burst", "wall")
ROWS = (POWERS, ELEMENTS, SHAPES)
ROW_NAMES = ("power", "element", "shape")
SPELLS = {(r["element"], r["shape"]): r for r in rows("spells.csv")}
COLORS = {"fire": (FIRE_I[3], FIRE_I[5]), "frost": (BLUE_I[2], WHITE), "light": (WHITE, FIRE_I[5]),
          "life": (MOSS_I[2], MOSS_I[1]), None: (FIRE_I[5], WHITE)}
SOUND = {"fire": "burn", "frost": "freeze", "light": "flash", "life": "heal"}
rnd = random.Random()


def skill_of(element):
    return "priest" if element == "life" else "wizard"


def describe(runes):
    """Name and mana cost of a (partial) rune sequence, for the panel."""
    if len(runes) < 3:
        return None, 0
    power, element, shape = runes
    row = SPELLS[(element, shape)]
    return row["name"], row["mana"] * power


def amount(row, power):
    return rnd.randint(row["amount_min"], row["amount_max"]) * power


def frames(row, power):
    return int(row["duration_sec"] * 60 * (1 + 0.5 * (power - 1)))


# ---------------------------------------------------------------- casting
def cast(world, caster, runes):
    """Cast runes = (power, element, shape) as caster.

    Returns 'cast', 'fizzle' (mana partly lost) or 'wait' (nothing happened:
    busy, not enough mana, or no room for a wall)."""
    power, element, shape = runes
    row = SPELLS[(element, shape)]
    cost = row["mana"] * power
    msgs = world.messages
    if not caster.up or caster.cooldown:
        return "wait"
    if caster.mana < cost:
        msgs.add(f"{caster.name} lacks the mana ({cost}).")
        world.sfx.play("fizzle")
        return "wait"
    skill = skill_of(element)
    caster.busy(TUNE["cast_cooldown"])
    if power > caster.level[skill] + TUNE["power_over_skill"]:
        caster.mana -= cost * TUNE["fizzle_mana"]
        msgs.add(f"The runes fizzle: {caster.name}'s {skill} skill is too low.")
        world.sfx.play("fizzle")
        return "fizzle"
    fl = world.floor
    p = world.player
    if shape == "wall":
        cell = front_cell(world)
        if cell is None or fl.solid(*cell) or fl.d.char(*cell) in "OXU":
            msgs.add("There is no room for it there.")
            world.sfx.play("fizzle")
            return "wait"
        blocking = element in ("frost", "light")
        if blocking and (any(e.alive and e.cell == cell for e in fl.enemies) or cell == p.cell):
            msgs.add("Something is in the way.")
            world.sfx.play("fizzle")
            return "wait"
    caster.mana -= cost
    world.sfx.play("cast")
    world.award(caster, skill, cost * TUNE["xp_per_mana"])
    if shape == "bolt":
        start, d = world.aim()
        fl.add_bolt(Bolt(start, d * BOLT_SPEED, caster, amount(row, power), element, power))
    elif shape == "ward":
        world.party.add_ward(element, frames(row, power), row["amount_min"] * power)
        msgs.add(f"{row['name']} surrounds the party.")
    elif shape == "burst":
        burst(world, caster, element, row, power)
    elif shape == "wall":
        fl.add_field(Field(element, cell, frames(row, power), amount(row, power)))
        msgs.add(f"{row['name']}!")
    return "cast"


def front_cell(world):
    """The open cell the caster faces (one cell ahead)."""
    p = world.player
    yr = math.radians(p.yaw)
    cell = cell_of(p.x + math.sin(yr) * CELL * 0.9, p.z - math.cos(yr) * CELL * 0.9)
    if cell == p.cell:
        cell = cell_of(p.x + math.sin(yr) * CELL * 1.4, p.z - math.cos(yr) * CELL * 1.4)
    return cell


def burst(world, caster, element, row, power):
    p = world.player
    fl = world.floor
    fl.add_effect(Burst(p.x, p.z, element, p.cell))
    if element == "life":
        for m in world.party.members:
            if m.up:
                m.heal(amount(row, power))
        world.sfx.play("heal")
        world.messages.add(f"{row['name']}: the party's wounds close.")
        return
    world.sfx.play(SOUND[element])
    for e in fl.enemies:
        if e.alive and math.hypot(e.x - p.x, e.z - p.z) <= TUNE["burst_radius"]:
            strike(world, e, caster, element, row, power, p.x, p.z)


def strike(world, enemy, caster, element, row, power, from_x, from_z, damage=None):
    """An element's effect on one enemy (bolts and bursts)."""
    if damage is None:
        damage = amount(row, power)
    if element == "frost":
        enemy.slow = max(enemy.slow, frames(row, power))
    elif element == "light":
        enemy.stun = max(enemy.stun, frames(row, power))
        if getattr(enemy, "UNDEAD", False):
            damage *= 2
    if damage > 0:
        world._damage_enemy(enemy, damage, from_x, from_z, caster, skill_of(element))
    if element == "life":
        caster.heal(damage // 2)


# ---------------------------------------------------------------- walls
class Field:
    """A spell filling one cell for a while: fire burns, ice blocks, light repels the undead, life heals."""

    def __init__(self, element, cell, frames_left, amount_):
        self.element = element
        self.cell = cell
        self.frames = frames_left
        self.total = frames_left
        self.amount = amount_
        self.t = 0
        self.node = FieldNode(self)

    @property
    def blocks_all(self):
        return self.element == "frost"

    @property
    def blocks_enemies(self):
        return self.element in ("frost", "light")

    def update(self, world, floor):
        """Returns False when it has run out."""
        self.t += 1
        self.frames -= 1
        if self.element == "fire" and self.t % 60 == 0:
            for e in floor.enemies:
                if e.alive and e.cell == self.cell:
                    world._damage_enemy(e, self.amount, *cell_center(self.cell), world.party.leader, "wizard")
                    floor.emit("burn", cell_center(self.cell), 0.6)
        if self.element == "life" and self.t % 60 == 0 and world.player.cell == self.cell:
            for m in world.party.members:
                if m.up:
                    m.heal(self.amount)
        return self.frames > 0


class FieldNode(Node):
    def __init__(self, field):
        super().__init__()
        self.field = field
        x, z = cell_center(field.cell)
        self.transform = Mat4.from_translation(Vec3(x, 0, z))

    def on_draw(self):
        f = self.field
        fade = min(1.0, f.frames / 40)  # shrink away at the end
        t = f.t
        if f.element == "frost":  # stacked blocks of ice, a little uneven
            r = random.Random(f.cell[0] * 17 + f.cell[1])
            size = CELL * 0.86
            for row in range(3):
                bh = WALL_H / 3 * fade
                for col in range(3):
                    for depth in range(3):
                        if 0 < col < 2 and 0 < depth < 2:
                            continue  # hollow inside: only the outer blocks show
                        w = size / 3
                        x = (col - 1) * w + r.uniform(-2, 2)
                        z = (depth - 1) * w + r.uniform(-2, 2)
                        y = bh * (row + 0.5)
                        c = (BLUE_I[2], BLUE_I[1], STONE_I[6])[(row + col + depth + r.randint(0, 1)) % 3]
                        self.box(Mat4.from_translation(Vec3(x, y, z)), Vec3(w - 3, bh - 3, w - 3), c)
            return
        self.shaded(False)
        lo, hi = COLORS[f.element]
        r = random.Random(f.cell[0] * 31 + f.cell[1])  # same spots every frame
        for i in range(9):
            x, z = r.uniform(-40, 40), r.uniform(-40, 40)
            phase = r.uniform(0, math.tau)
            if f.element == "fire":
                h = (20 + 18 * math.sin(t * 0.3 + phase)) * fade
                self.box(Mat4.from_translation(Vec3(x, h / 2, z)), Vec3(10, h, 10), lo if i % 2 else FIRE_I[4])
                self.box(Mat4.from_translation(Vec3(x, h + 3, z)), Vec3(5, 6, 5), hi)
            elif f.element == "light":
                y = (t * 0.8 + phase * 20) % WALL_H
                self.sphere(Vec3(x, y, z), 2 + (i + t // 6) % 2, hi if i % 3 else lo)
            else:  # life
                y = (t * 0.5 + phase * 20) % 70
                self.sphere(Vec3(x * 0.8, y, z * 0.8), 2, hi if (i + t // 10) % 2 else lo)
        self.shaded(True)


# ---------------------------------------------------------------- bursts
class Burst:
    """A ring of sparks spreading out from the caster."""

    LIFE = 24

    def __init__(self, x, z, element, cell):
        self.x, self.z = x, z
        self.element = element
        self.cell = cell
        self.age = 0
        self.node = BurstNode(self)

    def update(self):
        self.age += 1
        return self.age < self.LIFE


class BurstNode(Node):
    def __init__(self, burst_):
        super().__init__()
        self.burst = burst_
        self.transform = Mat4.from_translation(Vec3(burst_.x, 0, burst_.z))

    def on_draw(self):
        b = self.burst
        k = b.age / b.LIFE
        radius = 30 + (TUNE["burst_radius"] - 30) * k
        lo, hi = COLORS[b.element]
        self.shaded(False)
        for i in range(16):
            a = i / 16 * math.tau + k
            self.sphere(Vec3(math.cos(a) * radius, 30 + 12 * math.sin(a * 3 + k * 6), math.sin(a) * radius),
                        4 * (1 - k) + 1, hi if i % 2 else lo)
        self.shaded(True)
