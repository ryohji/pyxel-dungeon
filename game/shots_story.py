"""Views of the old kingdom for visual checks: camp people, carving, niche, the king's hall, a guardian, reading.

Usage: python shots_story.py OUT_DIR
"""

import os
import sys

import pyxel

import main
from objects import cell_center
from things import Thing

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)


def go(floor, cell, yaw, pitch=0.0):
    def setup(app):
        w = app.world
        w.floor = w.get_floor(floor)
        w.player.solid = w.floor.solid
        p = w.player
        p.x, p.z = cell_center(cell)
        p.yaw, p.pitch = yaw, pitch
        for e in w.floor.enemies:
            e.update = lambda floor, world, e=e: e.node.refresh()
    return setup


def both(*fs):
    def setup(app):
        for f in fs:
            f(app)
    return setup


def lore(app):
    w = app.world
    w.read("A CROWN SHARD", w_text("relic_shard"))


def w_text(kind):
    from tables import RELICS
    return RELICS[kind]["text"]


def scholar_table(app):
    app.world.hand = Thing("relic_seal")
    app.camp.show("scholar")


def close(app):
    app.camp.close()
    app.world.hand = None


SCENES = [
    ("camp_people", go("camp", (5, 4), 300), 3),
    ("scholar", go("camp", (7, 2), 45), 3),
    ("carving", go("floor1", (1, 3), 270, 5), 3),
    ("niche", go("floor1", (22, 2), 90), 3),
    ("hall", go("floor3", (18, 5), 0, 5), 3),
    ("guardian", go("floor3", (16, 5), 0, 5), 3),
    ("west_room", go("floor3", (8, 9), 270), 3),
    ("lore", both(go("floor1", (3, 3), 0), lore), 3),
    ("table", both(go("camp", (7, 2), 45), scholar_table), 2),
]


class ShotApp(main.App):
    START = "camp"

    def __init__(self):
        self.scene = 0
        self.wait = None
        super().__init__()

    def pointer(self):
        return 300, 20, False

    def update(self):
        self.help.open = False
        if self.wait is None:
            name, setup, frames = SCENES[self.scene]
            if self.camp.open:
                close(self)
            setup(self)
            self.wait = frames
        super().update()

    def draw(self):
        super().draw()
        self.wait -= 1
        if self.wait == 0:
            pyxel.screen.save(os.path.join(OUT, SCENES[self.scene][0] + ".png"), 2)
            self.reader.pages.clear()
            self.scene += 1
            self.wait = None
            if self.scene == len(SCENES):
                pyxel.quit()


ShotApp()
