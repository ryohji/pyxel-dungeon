"""Views of P11 for visual checks: the catacombs on floor 3. The gallery of coffins by torchlight and
in the dark, a coffin opened, the sconces, the moths, the library, the Lord's hall dark and lit, the map.

Usage: python shots_p11.py OUT_DIR
"""

import os
import sys

import pyxel

import main
from enemies import Lord, Moth
from objects import cell_center

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)


def go(cell, yaw, pitch=0.0, still=True):
    def setup(app):
        w = app.world
        if w.surface:
            w.report = None
            w.descend("floor3")
            w.travel = None
        p = w.player
        p.x, p.z = cell_center(cell)
        p.yaw, p.pitch = yaw, pitch
        w.party.mage.cooldown = 10 ** 6
        if still:
            for e in w.floor.enemies:
                e.update = lambda floor, world, e=e: e.node.refresh()
    return setup


def torch(on):
    def setup(app):
        for m in app.world.party.members:
            for t in m.equip.values():
                if t is not None and t.is_torch:
                    t.out = not on
    return setup


def coffin_open(app):
    w = app.world
    fx = w.floor.fixtures[(7, 1)]
    fx.open = True


def moth_by(app):
    w = app.world
    m = next(e for e in w.floor.enemies if isinstance(e, Moth))
    m.x, m.z = cell_center((11, 2))
    m.node.refresh()
    w.floor.view.move(m.node, m.cell)


def light_hall(n):
    def setup(app):
        lord = next(e for e in app.world.floor.enemies if isinstance(e, Lord))
        for i, sc in enumerate(lord.sconces):
            sc.lit = i < n
    return setup


def both(*fs):
    def setup(app):
        for f in fs:
            f(app)
    return setup


def show_map(app):
    w = app.world
    for x in range(w.floor.d.w):
        for y in range(w.floor.d.h):
            w.explored.setdefault("floor3", set()).add((x, y))
    app.show_map = True


SCENES = [
    ("gallery_torch", both(go((4, 2), 90), torch(True)), 3),
    ("gallery_dark", both(go((4, 2), 90), torch(False)), 3),
    ("coffin_open", both(go((7, 2), 0), torch(True), coffin_open), 3),
    ("sconce_entry", both(go((2, 2), 0), torch(False)), 3),
    ("moths", both(go((8, 2), 90), torch(True), moth_by), 3),
    ("library", both(go((16, 2), 90), torch(True)), 3),
    ("shelf", both(go((17, 1), 0), torch(True)), 3),
    ("hall_dark", both(go((14, 13), 180), torch(True), light_hall(0)), 3),
    ("hall_lit", both(go((14, 13), 180), torch(True), light_hall(4)), 3),
    ("map", both(go((14, 9), 0), show_map), 3),
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
            self.show_map = False
            name, setup, frames = SCENES[self.scene]
            setup(self)
            self.wait = frames
        if not self.help.open:
            super().update()
        self.world.messages.lines.clear()

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
