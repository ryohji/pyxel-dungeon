"""Views of P8 in Japanese for visual checks: the camp menu, the report of a delve, the requests and
where to go down, supplies, a fall, the journal's books, and the map with the load left behind.

Usage: python shots_p8.py OUT_DIR
"""

import os
import sys

import pyxel

import main
from objects import cell_center
from things import Thing

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)


def menu(app):
    app.world.mode = "keys"
    app.surface.sel = 2


def report(app):
    w = app.world
    w.descend()
    w.quests["ring"] = "accepted"
    w.party.fighter.give(Thing("ring"))
    w.back = Thing("relic_tablet")
    w.relic_log.append(("relic_shard", "bury", "floor1"))
    w.shortcuts.append("floor3")
    w.delve["opened"] = "floor3"
    w.arrive_surface()


def fallen(app):
    w = app.world
    w.descend()
    w.back = Thing("idol")
    w.player.x, w.player.z = cell_center((3, 10))
    w._fall_back()


def before_down(app):
    w = app.world
    w.report = None
    if "floor3" not in w.shortcuts:
        w.shortcuts.append("floor3")
    w.quests.pop("ring", None)
    w.quests["idol"] = "accepted"
    w.mode = "keys"
    app.camp.show("down")


def supplies(app):
    app.camp.show("supplies")


def talk(app):
    w = app.world
    w.report = None
    app.camp.close()
    w.talk("scholar")
    w.talk("keeper")
    w.pages.clear()
    app.journal.show(w, "talk")


def relics(app):
    w = app.world
    w.read(("relic", "relic_shard"))
    w.read(("relic", "relic_seal"))
    w.pages.clear()
    app.journal.show(w, "relic")
    app.journal.i = 0


def lost_map(app):
    w = app.world
    w.report = None
    w.descend()
    w.player.x, w.player.z = cell_center((5, 10))
    for x in range(1, 10):
        for y in range(9, 15):
            w.explored.setdefault("floor1", set()).add((x, y))
    app.show_map = True


SCENES = [
    ("menu", menu, 3),
    ("report", report, 3),
    ("fallen", fallen, 3),
    ("before_down", before_down, 3),
    ("supplies", supplies, 3),
    ("talk", talk, 3),
    ("relics", relics, 3),
    ("lost_map", lost_map, 30),
]


class ShotApp(main.App):
    START = "camp"
    SAVE = False  # never touch the player's saved game

    def __init__(self):
        self.scene = 0
        self.wait = None
        super().__init__()

    def pointer(self):
        return 300, 20, False

    def update(self):
        if self.wait is None:
            self.help.open = False
            self.journal.open = False
            name, setup, frames = SCENES[self.scene]
            setup(self)
            self.wait = frames
        if not self.help.open:
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
