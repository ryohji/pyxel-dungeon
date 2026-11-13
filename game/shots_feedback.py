"""Views after the story play test: an open door, the journal, guardians on the map.

Usage: python shots_feedback.py OUT_DIR
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


def open_door(app):
    app.world.floor.doors[(20, 5)].target_open = True
    app.world.floor.doors[(20, 5)].open = 1.0


def journal(app):
    w = app.world
    w.read("A CROWN SHARD", w_text("relic_shard"))
    w.read("A CARVING", w.floor.fixtures[(0, 3)].text if (0, 3) in w.floor.fixtures else "x")
    w.pages.clear()
    app.journal.show(w.journal)


def guardians(app):
    w = app.world
    w.floor.wake_guardian()
    w.explored[w.floor.name] = {(x, y) for x in range(w.floor.d.w) for y in range(w.floor.d.h)
                                if not w.floor.d.is_wall(x, y)}
    app.show_map = True


SCENES = [
    ("door_open", both(go("floor1", (20, 7), 0), open_door), 3),
    ("door_open_near", both(go("floor1", (20, 6), 0, 8), open_door), 3),
    ("journal", both(go("floor1", (3, 3), 0), journal), 2),
    ("map_guardians", both(go("floor3", (18, 13), 0), guardians), 2),
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
            self.journal.open = False
            self.show_map = False
            self.scene += 1
            self.wait = None
            if self.scene == len(SCENES):
                pyxel.quit()


ShotApp()
