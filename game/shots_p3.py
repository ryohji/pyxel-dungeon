"""Staged combat views for visual checks.

Usage: python shots_p3.py OUT_DIR
"""

import os
import sys

import pyxel

import main
from objects import cell_center

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)


def guard(w):
    return min(w.floor.enemies, key=lambda e: abs(e.x - 650) + abs(e.z - 1350))


def stage(state, t=0, walk=0.0, phase=0.0, yaw=270, dist=1.6, pitch=-5):
    def setup(w):
        p = w.player
        x, z = cell_center((6, 13))
        g = guard(w)
        g.x, g.z, g.yaw = x, z, yaw
        g.state, g.t, g.walk_amount, g.walk_phase = state, t, walk, phase
        g.cooldown = 10_000  # hold the pose
        p.x, p.z, p.yaw, p.pitch = x - dist * 100, z, 90, pitch
    return setup


def freeze(w):
    """Stop the guard from thinking so the staged pose stays put."""
    g = guard(w)
    g.update = lambda floor, world: g.node.refresh()


def swing(w):
    w.swing = 7


SCENES = [
    ("idle", stage("idle"), 3),
    ("walk", stage("chase", walk=1.0, phase=0.8), 1),
    ("windup", stage("attack", t=24), 1),
    ("strike", stage("attack", t=31), 1),
    ("side", stage("chase", walk=1.0, phase=0.3, yaw=0, dist=1.4), 1),
    ("dying", stage("dying", t=22), 1),
    ("dead", stage("dead", t=0, pitch=-25), 1),
    ("sword", swing, 1),
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
            freeze(self.world)
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
