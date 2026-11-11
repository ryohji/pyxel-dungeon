"""P4 views for visual checks: HUD, Tab target, inventory, fountain, items, darkness.

Usage: python shots_p4.py OUT_DIR
"""

import os
import sys

import pyxel

import main
from objects import Item, cell_center
from things import Thing

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)


def at(cell, yaw, pitch=0.0):
    def setup(app):
        p = app.world.player
        p.x, p.z = cell_center(cell)
        p.yaw, p.pitch = yaw, pitch
    return setup


def both(*fs):
    def setup(app):
        for f in fs:
            f(app)
    return setup


def keys(app):
    app.world.mode = "keys"


def inventory(app):
    app.inventory.open = True
    app.world.hand = Thing("dagger")
    app.world.party.mage.food = 15


def items(app):
    fl = app.world.floor
    x, z = cell_center((3, 1))
    for i, kind in enumerate(("torch", "bread", "waterskin", "dagger", "sword", "buckler", "cap", "jerkin")):
        fl.add_item(Item(kind, x - 70 + (i % 4) * 45, z + 30 - (i // 4) * 40, yaw=i * 40))


def dark(app):
    app.world.party.mage.equip["left"] = None


def dim(app):
    app.world.party.mage.equip["left"].fuel = 60 * 60


SCENES = [
    ("hud", at((3, 3), 0, -10), 3),
    ("target_lever", both(at((5, 3), 90), keys), 3),
    ("target_item", both(at((3, 3), 0, -15), keys), 3),
    ("inventory", inventory, 2),
    ("fountain", both(at((5, 13), 180, -10), lambda a: setattr(a.inventory, "open", False),
                      lambda a: setattr(a.world, "hand", None)), 3),
    ("items", both(items, at((3, 3), 0, -25)), 3),
    ("dim", both(dim, at((3, 12), 90)), 3),
    ("dark", both(dark, at((3, 12), 90)), 3),
    ("help", lambda a: setattr(a, "keep_help", True), 2),
]


class ShotApp(main.App):
    START = "floor1"
    def __init__(self):
        self.scene = 0
        self.wait = None
        super().__init__()

    def pointer(self):
        return 200, 150, False

    def update(self):
        self.help.open = getattr(self, "keep_help", False)
        if self.wait is None:
            name, setup, frames = SCENES[self.scene]
            setup(self)
            self.wait = frames
        super().update()

    def draw(self):
        super().draw()
        self.wait -= 1
        if self.wait == 0:
            pyxel.screen.save(os.path.join(OUT, SCENES[self.scene][0] + ".png"), 2)
            self.scene += 1
            self.wait = None
            if self.scene == len(SCENES):
                pyxel.quit()


ShotApp()
