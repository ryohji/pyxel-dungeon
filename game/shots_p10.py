"""Views of P10 in Japanese for visual checks: the camp with the smith, the smith's screen, the weapon
rack, the habits in the inventory, the three weapons swinging, the heavy blow, and the help.

Usage: python shots_p10.py OUT_DIR
"""

import os
import sys

import pyxel

import main
from things import Thing

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)


def menu(app):
    app.world.mode = "keys"
    app.surface.sel = 2


def smith(app):
    w = app.world
    for _ in range(2):
        w.party.fighter.give(Thing("bone"))
    w.mode = "keys"
    app.camp.show("smith")


def arms(app):
    w = app.world
    w.armory.append("maul")
    app.camp.show("arms")


def habits(app):
    app.camp.close()
    w = app.world
    w.award(w.party.fighter, "fighter", 200)
    app.inventory.open = True


def held(kind, heavy=False):
    def setup(app):
        app.inventory.open = False
        w = app.world
        if w.surface:
            w.report = None
            w.descend()
        w.party.fighter.equip["right"] = Thing(kind)
        w.party.fighter.cooldown = 0
        w.swing = 12
        w.heavy = 12 if heavy else 0
    return setup


def helpscreen(app):
    app.help.open = True


SCENES = [
    ("menu", menu, 3),
    ("smith", smith, 3),
    ("arms", arms, 3),
    ("habits", habits, 3),
    ("sword", held("sword"), 45),
    ("spear", held("spear"), 6),
    ("maul", held("maul"), 6),
    ("sweep", held("sword", True), 6),
    ("help", helpscreen, 3),
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
            name, setup, frames = SCENES[self.scene]
            setup(self)
            self.wait = frames
        if not self.help.open:
            super().update()
        if self.wait == 2 and SCENES[self.scene][0] in ("sword", "spear", "maul", "sweep"):
            self.world.swing = 7  # catch the weapon mid-swing

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
