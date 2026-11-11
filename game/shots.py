"""Render a few staged views to PNG for visual checks.

Usage: python shots.py OUT_DIR
"""

import os
import sys

import pyxel

import main
from objects import cell_center

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)


def place(w, cell, yaw, pitch=0.0, dx=0.0, dz=0.0):
    p = w.player
    x, z = cell_center(cell)
    p.x, p.z, p.yaw, p.pitch = x + dx, z + dz, yaw, pitch


def pull_lever(w):
    w.click(w.pick(160, 120))


def take_rock(w):
    rock = next(i for i in w.floor.items if i.kind == "rock")
    w.click(w.pick(*w.project(rock.center)))
    pyxel.set_mouse_pos(200, 180)


# (name, setup, frames to wait before the shot, pointer)
SCENES = [
    ("lever", lambda w: place(w, (4, 3), 60, -5), 5, (180, 130)),
    ("lever_pulled", pull_lever, 30, (180, 130)),
    ("cell_door", lambda w: place(w, (3, 4), 180, -10, dz=-30), 5, (160, 120)),
    ("rock_room", lambda w: place(w, (5, 10), 115, -30), 5, (150, 170)),
    ("near_rock", lambda w: place(w, (7, 10), 180, -40), 5, (150, 170)),
    ("holding", take_rock, 5, (200, 180)),
    ("gate", lambda w: place(w, (7, 12), 90, 0), 5, (160, 120)),
    ("pits", lambda w: place(w, (16, 12), 80, -20), 5, (160, 120)),
    ("locked_door", lambda w: place(w, (20, 10), 0, 0), 5, (160, 120)),
    ("stairs", lambda w: place(w, (20, 4), 0, -25), 5, (160, 120)),
]


class ShotApp(main.App):
    START = "floor1"
    def __init__(self):
        self.scene = 0
        self.wait = None
        super().__init__()

    def pointer(self):
        sc = SCENES[min(self.scene, len(SCENES) - 1)]
        return sc[3][0], sc[3][1], False

    def update(self):
        self.help.open = False
        if self.wait is None:
            name, setup, frames, _ = SCENES[self.scene]
            setup(self.world)
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
