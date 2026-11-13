"""Headless checks after the story play test: doors that shut again, the journal, finding the guardians.

Run: python test_feedback.py   (exits non-zero on failure)
"""

import pyxel
from pyxel.cube import Vec3

from camp import restore
from enemies import Guardian
from objects import cell_center
from palette import PALETTE
from sound import NullSfx
from tables import RELICS
from textures import make_atlas
from things import Thing
from world import World

W, H = 320, 240
pyxel.init(W, H)
pyxel.colors[:] = PALETTE
world = World(make_atlas(), W, H, NullSfx())
p = world.player


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


def door_hit(cell, y):
    x, z = cell_center(cell)
    return world.pick(*world.project(Vec3(x, y, z)))


fl = world.floor
door = fl.doors[(20, 5)]

# 1. a plain door opens, then shuts again by hand
place((20, 6), 0)
tick()
hit = door_hit((20, 5), 40)
check(hit.kind == "door" and world.action_name(hit) == "open", f"a closed door offers to open (got {hit.kind})")
world.click(hit)
tick(60)
check(not fl.solid(20, 5), "the door is open")
hit = door_hit((20, 5), 92)
check(hit.kind == "door" and world.action_name(hit) == "close", f"its lower edge can still be chosen (got {hit.kind})")
world.click(hit)
tick(60)
check(fl.solid(20, 5), "the door shut again")

# 2. a door does not shut on a skeleton standing in it
world.click(door_hit((20, 5), 40))
tick(60)
sk = next(e for e in fl.enemies if not isinstance(e, Guardian))
sk.x, sk.z = cell_center((20, 5))
door.target_open = False
fl.update(p.cell, world.messages)
check(door.open == 1.0, "a door never closes on an enemy")

# 3. the iron key's door opens and shuts by hand once unlocked
key_door = fl.doors[(20, 8)]
check(key_door.lock and not key_door.controlled, "the iron door is locked but not lever-bound")
key_door.lock, key_door.target_open = None, True  # as the key leaves it
world._use_door(key_door)
check(key_door.target_open is False, "once unlocked it can be shut")

# 4. the journal keeps what was read, a note's request too
world.pages.clear()
shard = next(it for it in fl.items if it.kind == "relic_shard")
world._take(shard)
note = next(it for it in fl.items if it.kind == "note_lantern")
world._take(note)
titles = [t for t, _ in world.journal]
check(any(text == RELICS["relic_shard"]["text"] for _, text in world.journal), "the shard's lore is in the journal")
check(len(titles) == 2, f"the note is in the journal too ({titles})")
world.read(*world.journal[0])
check(len(world.journal) == 2, "a page read twice is kept once")
world._remember_entry()
world._restart_floor()
check(len(world.journal) == 2, "the journal survives a wipe")

# 5. a woken guardian is told of
world.floor = world.get_floor("camp")
world.hand = Thing("relic_seal")
restore(world, "relic_seal")
check(any("guardian wakes on floor 1" in m for m, _ in world.messages.lines), "the message says where a guardian woke")

print("all checks passed")
