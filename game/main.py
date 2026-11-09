"""P1: walk around one dungeon floor.

Controls
  W A S D        move / strafe        Shift  run
  Q E, <- ->     turn                 up/down  look up / down
  right drag     look around          R      level the view
  Tab            toggle map           F      toggle debug info
"""

import math
import os
import time

import pyxel

from dungeon import CELL, Dungeon
from palette import BLACK, FIRE_I, PALETTE, STONE_I, WHITE
from player import Player
from textures import make_atlas
from view import DungeonView

W, H = 320, 240
HERE = os.path.dirname(os.path.abspath(__file__))


class App:
    def __init__(self):
        pyxel.init(W, H, title="Pyxel Dungeon (P1)", fps=60)
        pyxel.colors[:] = PALETTE
        pyxel.mouse(True)
        self.dungeon = Dungeon.load(os.path.join(HERE, "maps", "floor1.txt"))
        self.player = Player(self.dungeon)
        self.view = DungeonView(self.dungeon, make_atlas())
        self.explored = set()
        self.show_map = False
        self.show_debug = False
        self.cost_ms = 0.0
        pyxel.run(self.update, self.draw)

    def update(self):
        t0 = time.perf_counter()
        if pyxel.btnp(pyxel.KEY_TAB):
            self.show_map = not self.show_map
        if pyxel.btnp(pyxel.KEY_F):
            self.show_debug = not self.show_debug
        self.player.update()
        self.view.update(self.player.eye, self.player.yaw, self.player.pitch, pyxel.frame_count)
        self.explored.update(self.view.shown)
        self.update_ms = (time.perf_counter() - t0) * 1000

    def draw(self):
        t0 = time.perf_counter()
        self.view.draw(0, 0, W, H)
        draw_ms = (time.perf_counter() - t0) * 1000
        self.cost_ms = self.cost_ms * 0.9 + (self.update_ms + draw_ms) * 0.1
        self.draw_compass()
        if self.show_map:
            self.draw_map()
        if self.show_debug:
            gx, gy = self.player.cell
            pyxel.text(4, H - 16, f"cell {gx},{gy} yaw {self.player.yaw:5.1f} pitch {self.player.pitch:5.1f}", WHITE)
            pyxel.text(4, H - 8, f"cells {self.view.cells_drawn:3d}  cost {self.cost_ms:4.1f}ms", WHITE)

    def draw_compass(self):
        cx = W // 2
        pyxel.rect(cx - 9, 2, 19, 9, BLACK)
        pyxel.rectb(cx - 9, 2, 19, 9, STONE_I[3])
        pyxel.text(cx - 1, 4, self.player.facing, FIRE_I[5])

    def draw_map(self):
        s = 4
        d = self.dungeon
        ox = W - d.w * s - 4
        oy = 14
        pyxel.rect(ox - 2, oy - 2, d.w * s + 4, d.h * s + 4, BLACK)
        for gx, gy in self.explored:
            pyxel.rect(ox + gx * s, oy + gy * s, s, s, STONE_I[3])
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if d.is_wall(gx + dx, gy + dy):
                    x = ox + (gx + dx) * s
                    y = oy + (gy + dy) * s
                    pyxel.rect(x, y, s, s, STONE_I[6])
        px = ox + self.player.x / CELL * s
        pz = oy + self.player.z / CELL * s
        pyxel.circ(px, pz, 1, FIRE_I[5])
        yr = math.radians(self.player.yaw)
        pyxel.line(px, pz, px + math.sin(yr) * 5, pz - math.cos(yr) * 5, FIRE_I[4])


App()
