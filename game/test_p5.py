"""Headless checks of P5: rune spells (bolts, wards, bursts, walls), fizzles, the rune panel.

Run: python test_p5.py   (exits non-zero on failure)
"""

import math

import pyxel

from objects import cell_center
from palette import PALETTE
from runes import RunePanel
from sound import NullSfx
from spells import ELEMENTS, SHAPES, SPELLS
from textures import make_atlas
from view import MAX_DARK
from world import World

import lang

lang.current[0] = "en"  # these checks read the English lines
W, H = 320, 240
pyxel.init(W, H)
pyxel.colors[:] = PALETTE
sfx = NullSfx()
world = World(make_atlas(), W, H, sfx)
p = world.player
party = world.party
arn, mira = party.fighter, party.mage
fl = world.floor
guard = min(fl.enemies, key=lambda e: math.hypot(e.x - 650, e.z - 1350))


def check(cond, what):
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        raise SystemExit(1)


def place(cell, yaw, pitch=0.0):
    x, z = cell_center(cell)
    p.x, p.z, p.yaw, p.pitch = x, z, yaw, pitch


def tick(n=1, **keys):
    for _ in range(n):
        world.update(W // 2, H // 2, False, **keys)


def ready(mana=None):
    """Rested and full of mana, as if some time had passed."""
    arn.cooldown = 0
    arn.mana = arn.max_mana if mana is None else mana


def hold(enemy, cell):
    """Keep an enemy standing still in a cell."""
    enemy.x, enemy.z = cell_center(cell)
    enemy.state, enemy.t, enemy.cooldown = "idle", 1, 10_000


check(len(SPELLS) == 16 and all((e, s) in SPELLS for e in ELEMENTS for s in SHAPES), "16 spells in spells.csv")
check(party.leader is arn and arn.max_mana > 0, "Arn leads and has mana")

# 1. Light ward: light without a torch
place((3, 3), 0)
mira.equip["left"] = None
tick()
check(fl.view.dark == MAX_DARK, "dark without a torch")
ready()
check(world.cast((1, "light", "ward")) == "cast", "cast Light")
check(arn.mana == arn.max_mana - 2 and "light" in party.wards, "Light cost 2 mana and lies on the party")
tick()
check(fl.view.dark == 0, "the Light ward lights the way")
party.wards["light"][0] = 1
tick(2)
check("light" not in party.wards and fl.view.dark == MAX_DARK, "the Light ward ran out")

# 2. fizzles and lack of mana
ready()
before = arn.mana
check(world.cast((4, "fire", "bolt")) == "fizzle", "power 4 fizzles at wizard level 1")
check(arn.mana < before and "fizzle" in sfx.played, "a fizzle loses mana")
ready(1)
check(world.cast((1, "fire", "bolt")) == "wait" and arn.mana == 1, "not enough mana: nothing happens")

# 3. Fireball at a targeted enemy; wizard xp
place((3, 13), 90)
hold(guard, (6, 13))
tick(tab=True)
check(world.target is not None and world.target.obj is guard, "Tab targets the guard")
ready()
hp, xp = guard.hp, arn.xp["wizard"]
check(world.cast((2, "fire", "bolt")) == "cast", "cast a power-2 Fireball")
for _ in range(80):
    hold(guard, (6, 13))
    tick()
    if guard.hp < hp:
        break
check(guard.hp < hp, f"the Fireball burned the guard ({hp} -> {guard.hp})")
check(arn.xp["wizard"] > xp, "wizard skill gained xp")

# 4. Frost bolt slows, Sunbolt stuns
ready()
world.cast((1, "frost", "bolt"))
for _ in range(80):
    hold(guard, (6, 13))
    tick()
    if guard.slow:
        break
check(guard.slow > 0, f"the Frost Bolt slowed the guard ({guard.slow} frames)")
ready()
world.cast((1, "light", "bolt"))
for _ in range(80):
    hold(guard, (6, 13))
    tick()
    if guard.stun:
        break
check(guard.stun > 0, "the Sunbolt dazed the guard")

# 5. Cold Snap reaches enemies close by, not far ones
guard.hp = guard.MAX_HP
place((5, 13), 90)
hold(guard, (6, 13))
other = next(e for e in fl.enemies if e is not guard)
ready()
far_hp = other.hp
world.cast((1, "frost", "burst"))
check(guard.hp < guard.MAX_HP and guard.slow > 0, "Cold Snap hurt and slowed the guard beside you")
check(other.hp == far_hp, "the far guard was out of reach")
tick(30 + world.hitstop)
check(not fl.effects, "the burst faded")

# 6. walls: ice blocks everyone, light only the undead, fire burns
place((3, 11), 90)
ready()
check(world.cast((1, "frost", "wall")) == "cast", "cast Ice Wall")
check(fl.solid(4, 11) and fl.enemy_solid(4, 11), "the ice blocks the cell")
fl.fields[(4, 11)].frames = 1
tick(2)
check(not fl.solid(4, 11) and (4, 11) not in fl.fields, "the ice melted")
ready()
world.cast((1, "light", "wall"))
check(fl.enemy_solid(4, 11) and not fl.solid(4, 11), "Bright Ward keeps the undead out but lets the party in")
ready()
world.cast((1, "fire", "wall"))
hold(guard, (4, 11))
hp = guard.hp
for _ in range(70):
    hold(guard, (4, 11))
    tick()
check(guard.hp < hp, f"the Fire Wall burned the guard standing in it ({hp} -> {guard.hp})")
place((3, 11), 0)
ready()
world.cast((1, "frost", "wall"))
check(not fl.solid(*p.cell), "ice never forms on the party's own cell")

# 7. life: Mend heals the party; priest xp
arn.hp, mira.hp = 10, 10
ready()
pxp = arn.xp["priest"]
world.cast((1, "life", "burst"))
check(arn.hp > 10 and mira.hp > 10 and arn.xp["priest"] > pxp, "Mend healed both and trained priest")

# 8. wards: Frost Skin softens blows, Flame Blade sharpens the sword
arn.hp = arn.max_hp
ready()
world.cast((1, "frost", "ward"))
hp = arn.hp
world.hit_party(5, None)
check(hp - arn.hp == 5 - arn.defense - 1, f"Frost Skin took 1 more off the blow ({hp - arn.hp})")
ready()
world.cast((2, "fire", "ward"))
check(party.ward("fire") == 4, "Flame Blade at power 2 adds 4 to the sword")

# 9. the rune panel: keys pick runes, Enter casts
panel = RunePanel(H)
panel.runes = [1, "light"]
panel.runes.append("ward")
ready()
panel.cast(world)
check(not panel.runes and "light" in party.wards, "the panel cast its runes and cleared")
panel.runes = [1]
panel.cast(world)
check(panel.runes == [1], "an unfinished spell is not cast")

print("all checks passed")
