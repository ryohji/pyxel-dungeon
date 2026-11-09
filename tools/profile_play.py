"""Play the game headless with an autopilot and report frame cost over time.

Run from the repository root:  .venv/bin/python tools/profile_play.py [FRAMES]
"""

import math
import os
import sys
import time

GAME = os.path.join(os.path.dirname(__file__), "..", "game")
sys.path.insert(0, GAME)

import pyxel  # noqa: E402

from objects import cell_center  # noqa: E402
from palette import PALETTE  # noqa: E402
from sound import NullSfx  # noqa: E402
from textures import make_atlas  # noqa: E402
from world import World  # noqa: E402

FRAMES = int(sys.argv[1]) if len(sys.argv) > 1 else 6000
W, H = 320, 240
pyxel.init(W, H, headless=True)
pyxel.colors[:] = PALETTE
world = World(make_atlas(), W, H, NullSfx())
p = world.player

# open the cell door, then stand in the rock room and fight whatever comes
for door in world.floor.doors.values():
    if door.cell == (3, 6):
        door.target_open = True
x, z = cell_center((3, 10))
p.x, p.z, p.yaw = x, z, 135

stats = {}


def count(name, n=1):
    stats[name] = stats.get(name, 0) + n


# instrument the suspects
import enemies  # noqa: E402

_find = enemies.find_path


def find_path(*a, **k):
    count("find_path")
    t0 = time.perf_counter()
    r = _find(*a, **k)
    count("find_path_ms", (time.perf_counter() - t0) * 1000)
    return r


enemies.find_path = find_path
_los = enemies.line_of_sight


def los(*a, **k):
    count("los")
    return _los(*a, **k)


enemies.line_of_sight = los
import party as party_mod  # noqa: E402

party_mod.line_of_sight = los

print(f"{'frames':>7} {'upd ms':>7} {'draw ms':>8} {'nodes':>6} {'bolts':>5} {'popups':>6} "
      f"{'paths':>6} {'path ms':>8} {'los':>6} {'hp':>9}  enemies")
upd = drw = 0.0
for f in range(1, FRAMES + 1):
    pyxel.frame_count = f if hasattr(pyxel, "frame_count") else None
    t0 = time.perf_counter()
    target = next((e for e in world.floor.enemies if e.alive), None)
    if target is not None and math.hypot(target.x - p.x, target.z - p.z) < 200:
        p.yaw = math.degrees(math.atan2(target.x - p.x, -(target.z - p.z)))
    world.update(W // 2, H // 2, False, attack_key=(f % 20 == 0))
    t1 = time.perf_counter()
    world.floor.view.draw(0, 0, W, H)
    t2 = time.perf_counter()
    upd += t1 - t0
    drw += t2 - t1
    if f % 300 == 0:
        fl = world.floor
        hp = "/".join(str(m.hp) for m in world.party.members)
        states = ",".join(e.state for e in fl.enemies)
        print(f"{f:7d} {upd / 300 * 1000:7.2f} {drw / 300 * 1000:8.2f} {len(fl.view.root.children):6d} "
              f"{len(fl.bolts):5d} {len(world.popups):6d} {stats.get('find_path', 0):6d} "
              f"{stats.get('find_path_ms', 0):8.1f} {stats.get('los', 0):6d} {hp:>9}  {states}", flush=True)
        upd = drw = 0.0
        stats.clear()
