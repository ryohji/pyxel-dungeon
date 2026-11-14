"""Development keys, live only while the debug display (F) is on.

  F5  read data/*.csv again and rebuild the current floor from its map
  F6  the party takes no harm (on / off)
  F7  go up a floor, F8 go down a floor (to its stairs or start)
  F9  put the next kind of item in the hand (Shift+F9: the one before)

They exist so that numbers and maps can be tried at once, without restarting
the game or walking to the place under test.
"""

import os

import pyxel

import enemies
import spells
import tables
from objects import cell_center
from things import Thing

MAPS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "maps")
HELP = "F5 reload  F6 no harm  F7/F8 floor up/down  F9 item"


def floor_names():
    """The camp, then floor1, floor2, ... in order."""
    names = sorted(f[:-4] for f in os.listdir(MAPS) if f.startswith("floor") and f.endswith(".txt"))
    return ["camp"] + sorted(names, key=lambda n: int(n[5:]))


class DevTools:
    def __init__(self):
        self.item = -1

    def update(self, world):
        if pyxel.btnp(pyxel.KEY_F5):
            reload(world)
        if pyxel.btnp(pyxel.KEY_F6):
            world.no_harm = not world.no_harm
            world.messages.add(f"[dev] no harm {'on' if world.no_harm else 'off'}")
        if pyxel.btnp(pyxel.KEY_F7) or pyxel.btnp(pyxel.KEY_F8):
            names = floor_names()
            i = names.index(world.floor.name) + (1 if pyxel.btnp(pyxel.KEY_F8) else -1)
            if 0 <= i < len(names):
                warp(world, names[i])
        if pyxel.btnp(pyxel.KEY_F9):
            kinds = list(tables.ITEMS)
            back = pyxel.btn(pyxel.KEY_SHIFT)
            self.item = (self.item + (-1 if back else 1)) % len(kinds)
            world.hand = Thing(kinds[self.item])
            world.messages.add(f"[dev] in hand: {world.hand.name}")


def reload(world):
    """New numbers from the CSVs, and the current floor rebuilt from its map file."""
    tables.reload()
    spells.SPELLS.clear()
    spells.SPELLS.update({(r["element"], r["shape"]): r for r in tables.rows("spells.csv")})
    enemies.apply_tables()
    p = world.player
    x, z = p.x, p.z
    name = world.floor.name
    world.floors.pop(name, None)
    world.floor = world.get_floor(name)
    p.solid = world.floor.solid
    if world.floor.solid(*p.cell):  # the map changed under our feet
        place(world)
    else:
        p.x, p.z = x, z
    world._remember_entry()
    world.messages.add("[dev] data and map reloaded")


def warp(world, name):
    world.floor = world.get_floor(name)
    world.player.solid = world.floor.solid
    place(world)
    world.arrived_on = world.player.cell
    world._remember_entry()
    world.messages.add(f"[dev] to {name}")


def place(world):
    """Stand on the floor's start, else its up stairs, else its down stairs, else any open cell."""
    d = world.floor.d
    p = world.player
    if d.start:
        cell, p.yaw = d.start[:2], d.start[2]
    else:
        cells = list(d.cells_of("U")) or list(d.cells_of("X")) or [(x, y) for y in range(d.h) for x in range(d.w)
                                                       if not d.is_wall(x, y)]
        cell = cells[0]
    p.x, p.z = cell_center(cell)
