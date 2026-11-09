"""Headless walk-through of the floor 1 puzzle, driving World directly.

Run: python test_p2.py   (exits non-zero on failure)
"""

import pyxel
from pyxel.cube import Vec3

from objects import cell_center
from palette import PALETTE
from textures import make_atlas
from world import World

W, H = 320, 240
pyxel.init(W, H)
pyxel.colors[:] = PALETTE
world = World(make_atlas(), W, H)
fl1 = world.floor
p = world.player


def place(cell, yaw, pitch=0.0, dx=0.0, dz=0.0):
    x, z = cell_center(cell)
    p.x, p.z, p.yaw, p.pitch = x + dx, z + dz, yaw, pitch
    world.arrived_on = None


def tick(n=1, mx=W // 2, my=H // 2, click=False):
    for i in range(n):
        world.update(mx, my, click and i == 0)


def click_at(pt):
    sx, sy = world.project(pt)
    hit = world.pick(sx, sy)
    world.click(hit)
    return hit


def check(cond, what):
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        raise SystemExit(1)


# 1. pull the lever: the cell door opens
place((5, 3), 90)
tick()
check(world.hover.kind == "switch", f"aiming at the lever (got {world.hover.kind})")
tick(click=True)
tick(40)
check(not fl1.solid(3, 6), "lever opened the cell door")

# 2. take the rock
rock = next(it for it in fl1.items if it.kind == "rock")
place((rock.cell[0], rock.cell[1] - 1), 180, pitch=-30)
hit = click_at(rock.center)
check(hit.kind == "item" and world.hand == "rock", f"picked up the rock (hit {hit.kind})")

# 3. the gate opens only while something is on the plate
place((1, 14), 90)
tick(40)
check(not fl1.solid(10, 12), "standing on the plate opens the gate")
place((3, 13), 0)
tick(40)
check(fl1.solid(10, 12), "stepping off closes the gate")

# 4. put the rock on the plate
place((2, 13), 225, pitch=-40)
px, pz = cell_center((1, 14))
hit = click_at(Vec3(px, 0, pz))
check(hit.kind == "floor" and world.hand is None, f"put the rock down (hit {hit.kind})")
tick(40)
check(fl1.plates[(1, 14)].pressed and not fl1.solid(10, 12), "the rock holds the plate down")

# 5. take the key, unlock the door to the stairs
key = next(it for it in fl1.items if it.kind == "key_iron")
place((key.cell[0] - 1, key.cell[1]), 90, pitch=-35)
hit = click_at(key.center)
check(world.hand == "key_iron", f"picked up the key (hit {hit.kind})")
place((20, 9), 0)
tick()
check(world.hover.kind == "door", f"aiming at the locked door (got {world.hover.kind})")
tick(click=True)
tick(40)
check(not fl1.solid(20, 8), "the key opened the door")

# 6. stairs down and back up
place((20, 3), 0)
p.z -= 100
for _ in range(80):
    tick()
check(world.floor.name == "floor2", "went down the stairs")
check(world.arrived_on == (20, 2), "arrived on the stairs up")
place((20, 3), 0)
tick()
p.z -= 100
tick(80)
check(world.floor.name == "floor1", "climbed back up")

# 7. a thrown rock bounces off a wall and lands
place((2, 13), 225, pitch=-40)
rock = next(it for it in fl1.items if it.kind == "rock")
world.click(world.pick(*world.project(rock.center)))
check(world.hand == "rock", "took the rock back")
tick(40)
check(fl1.solid(10, 12), "gate closed again without the rock")
place((5, 12), 90, pitch=10)
world.click(world.pick(W // 2, H // 2 - 40))
tick(200)
thrown = next(it for it in fl1.items if it.kind == "rock")
check(not thrown.moving and thrown.y == 0.0 and not fl1.solid(*thrown.cell), f"rock came to rest in {thrown.cell}")

# 8. a pit drops the player to floor 2
place((17, 11), 180)
p.z += 100
for _ in range(80):
    tick()
check(world.floor.name == "floor2" and p.cell == (17, 12), f"fell through the pit to {p.cell}")

print("all checks passed")
