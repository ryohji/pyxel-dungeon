"""P5 views for visual checks: the rune panel and each kind of spell.

Usage: python shots_p5.py OUT_DIR
"""

import os
import sys

import pyxel

import main
from objects import cell_center

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)


def at(cell, yaw, pitch=0.0):
    def setup(app):
        p = app.world.player
        p.x, p.z = cell_center(cell)
        p.yaw, p.pitch = yaw, pitch
    return setup


def cast(*runes):
    def setup(app):
        arn = app.world.party.leader
        arn.cooldown, arn.mana = 0, 99
        app.world.cast(runes)
    return setup


def panel(*runes):
    def setup(app):
        app.runes.runes = list(runes)
    return setup


def both(*fs):
    def setup(app):
        for f in fs:
            f(app)
    return setup


def calm(app):
    for e in app.world.floor.enemies:
        e.update = lambda floor, world, e=e: e.node.refresh()


SCENES = [
    ("panel", both(calm, at((3, 3), 0), panel(2, "fire")), 2),
    ("fireball", both(at((3, 11), 90), cast(2, "fire", "bolt")), 8),
    ("frost_bolt", both(at((3, 11), 90), cast(2, "frost", "bolt")), 8),
    ("burst", both(at((3, 11), 90), cast(1, "fire", "burst")), 8),
    ("fire_wall", both(at((2, 11), 90), cast(1, "fire", "wall"), at((2, 11), 90)), 20),
    ("ice_wall", both(at((2, 12), 90), cast(1, "frost", "wall"), at((1, 12), 90)), 10),
    ("light_wall", both(at((2, 13), 90), cast(1, "light", "wall")), 20),
    ("life_wall", both(at((5, 10), 180), cast(1, "life", "wall")), 20),
    ("ward", both(at((3, 3), 0), cast(1, "light", "ward"), cast(1, "frost", "ward")), 3),
]


class ShotApp(main.App):
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
