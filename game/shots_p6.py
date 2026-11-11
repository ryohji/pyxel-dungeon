"""P6 views for visual checks: the camp, its board and counter, carrying a load.

Usage: python shots_p6.py OUT_DIR
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


def screen(kind):
    def setup(app):
        app.camp.show(kind)
    return setup


def close(app):
    app.camp.close()


def carry(app):
    app.world.back = Thing("remains_brenn")
    app.world.quests["ring"] = "accepted"


def finds(app):
    fl = app.world.floor
    x, z = cell_center((5, 2))
    for i, kind in enumerate(("ring", "lantern", "note_lantern", "remains_brenn", "idol")):
        fl.add_item(Item(kind, x - 80 + i * 40, z - (30 if i % 2 else 0), yaw=90))


SCENES = [
    ("camp", at((5, 4), 0, -5), 3),
    ("camp_counter", at((8, 2), 90, -10), 3),
    ("board", both(at((5, 1), 0), screen("board")), 2),
    ("counter", both(carry, screen("counter")), 2),
    ("finds", both(close, finds, at((5, 4), 0, -20)), 3),
    ("carrying", both(at((5, 4), 180)), 3),
]


class ShotApp(main.App):
    START = "camp"

    def __init__(self):
        self.scene = 0
        self.wait = None
        super().__init__()

    def pointer(self):
        return 160, 120, False

    def update(self):
        self.help.open = False
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
