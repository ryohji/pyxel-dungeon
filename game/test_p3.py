"""Headless checks of enemies, the companion, combat and the party wipe.

Run: python test_p3.py   (exits non-zero on failure)
"""

import math

import pyxel

from objects import cell_center
from palette import PALETTE
from sound import NullSfx
from textures import make_atlas
from world import World

W, H = 320, 240
pyxel.init(W, H)
pyxel.colors[:] = PALETTE
sfx = NullSfx()
world = World(make_atlas(), W, H, sfx)
p = world.player
party = world.party


def check(cond, what):
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        raise SystemExit(1)


def place(cell, yaw, pitch=0.0):
    x, z = cell_center(cell)
    p.x, p.z, p.yaw, p.pitch = x, z, yaw, pitch


def tick(n=1):
    for _ in range(n):
        world.update(W // 2, H // 2, False)


def face(enemy):
    p.yaw = math.degrees(math.atan2(enemy.x - p.x, -(enemy.z - p.z)))


fl = world.floor
guard = min(fl.enemies, key=lambda e: math.hypot(e.x - 650, e.z - 1350))  # the rock-room guard
check(guard.state == "idle", "the guard starts idle")

# 1. it notices the party, comes over and strikes; Mira casts at it
place((2, 10), 135)
inside_wall = False
struck = False
for _ in range(600):
    tick()
    inside_wall |= fl.enemy_solid(*guard.cell)
    if party.fighter.hp < party.fighter.max_hp:
        struck = True
        break
check("alert" in sfx.played, "the guard noticed the party")
check(not inside_wall, "the guard never stepped into a wall or pit")
check(struck, f"the guard reached the party and hit (fighter {party.fighter.hp}/{party.fighter.max_hp})")
check("bolt" in sfx.played, "Mira cast a bolt")

# 2. Arn fights back until it falls apart
hp_before = guard.hp
for _ in range(900):
    face(guard)
    world.attack(guard)
    tick()
    if not guard.alive:
        break
tick(2)  # the collapse starts on the guard's next turn
check(not guard.alive and "collapse" in sfx.played, f"the guard was destroyed (hp {hp_before} -> {guard.hp})")
tick(60)
check(guard.state == "dead", "its bones lie still")

# 3. a closed door stops the other guard
other = next(e for e in fl.enemies if e is not guard)
gate = fl.doors[(10, 12)]
check(gate.blocks_move, "the gate is closed")
place((9, 12), 90)
party.restore([(40, 0), (28, 0)])
other.state, other.last_seen = "chase", (p.x, p.z)
crossed = False
for _ in range(400):
    tick()
    crossed |= other.x < 1000
check(not crossed, "the far guard could not get through the closed gate")

# 4. a thrown rock hurts an enemy
place((12, 12), 90)
world.hand = "rock"
other.state, other.x, other.z = "idle", 1450, 1250
face(other)
hp_before = other.hp
world.click(world.pick(*world.project(other.center)))
for _ in range(60):
    tick()
    if other.hp < hp_before:
        break
check(other.hp < hp_before, f"a thrown rock hurt the guard ({hp_before} -> {other.hp})")

# 5. a party wipe sends everyone back to the floor's entrance, floor reset
entry = dict(world.entry)
party.fighter.hp, party.mage.hp = 1, 1
world.hit_party(10, other)
world.hit_party(10, other)
check(world.wipe is not None and "defeat" in sfx.played, "the party fell")
old_floor = world.floor
tick(130)
check(world.wipe is None and world.floor is not old_floor, "the floor was loaded afresh")
check((round(p.x), round(p.z)) == (round(entry["x"]), round(entry["z"])), "back at the entrance")
check([m.hp for m in party.members] == [hp for hp, _ in entry["party"]], "party health as on entry")
check(all(e.alive for e in world.floor.enemies), "the guards are back")

print("all checks passed")
