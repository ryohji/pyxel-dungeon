"""Pyxel Dungeon (P2): mechanisms, items and stairs.

Controls
  W A S D        move / strafe        Shift  run
  Q E, <- ->     turn                 up/down  look up / down
  right drag     look around          R      level the view
  left click     take an item / pull a lever / open a door
                 holding an item: click the floor to put it down,
                 a locked door to use a key, anything else to throw
  Tab            toggle map           F      toggle debug info
"""

import math
import time

import pyxel

from dungeon import CELL
from palette import BLACK, FIRE_I, PALETTE, STONE_I, WHITE
from sound import Sfx
from textures import ICON, icon_uv, make_atlas, make_icons
from world import REACH, World

W, H = 320, 240

COMPASS = ("N", "E", "S", "W")

HINTS = {
    "item": "take",
    "switch": "pull",
    "door": "open / close",
}


class App:
    def __init__(self):
        pyxel.init(W, H, title="Pyxel Dungeon (P2)", fps=60)
        pyxel.colors[:] = PALETTE
        self.icons = make_icons()
        self.world = World(make_atlas(), W, H, Sfx())
        self.show_map = False
        self.show_debug = False
        self.cost_ms = 0.0
        self.update_ms = 0.0
        pyxel.run(self.update, self.draw)

    def pointer(self):
        """Mouse position and whether the left button was just clicked."""
        return pyxel.mouse_x, pyxel.mouse_y, pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT)

    def update(self):
        t0 = time.perf_counter()
        if pyxel.btnp(pyxel.KEY_TAB):
            self.show_map = not self.show_map
        if pyxel.btnp(pyxel.KEY_F):
            self.show_debug = not self.show_debug
        self.world.update(*self.pointer())
        self.update_ms = (time.perf_counter() - t0) * 1000

    # ------------------------------------------------------------ draw
    def draw(self):
        t0 = time.perf_counter()
        w = self.world
        w.floor.view.draw(0, 0, W, H)
        draw_ms = (time.perf_counter() - t0) * 1000
        self.cost_ms = self.cost_ms * 0.9 + (self.update_ms + draw_ms) * 0.1
        if w.fade > 0:
            pyxel.dither(min(1.0, w.fade))
            pyxel.rect(0, 0, W, H, BLACK)
            pyxel.dither(1.0)
        self.draw_compass()
        self.draw_messages()
        if self.show_map:
            self.draw_map()
        if self.show_debug:
            p = w.player
            gx, gy = p.cell
            pyxel.text(4, H - 16, f"{w.floor.name} cell {gx},{gy} yaw {p.yaw:5.1f} pitch {p.pitch:5.1f}", WHITE)
            pyxel.text(4, H - 8, f"cells {w.floor.view.cells_drawn:3d}  cost {self.cost_ms:4.1f}ms", WHITE)
        self.draw_cursor()

    def draw_compass(self):
        """A heading strip like  W ── N ── E : the cardinal points that are in view."""
        half_w, span = 31, 100.0  # pixels each side, degrees each side
        scale = half_w / span
        cx, y = W // 2, 2
        yaw = self.world.player.yaw
        pyxel.rect(cx - half_w - 4, y, half_w * 2 + 9, 11, BLACK)
        pyxel.rectb(cx - half_w - 4, y, half_w * 2 + 9, 11, STONE_I[3])
        pyxel.line(cx - half_w, y + 5, cx + half_w, y + 5, STONE_I[2])
        for deg in range(0, 360, 30):
            off = (deg - yaw + 180) % 360 - 180
            if abs(off) > span:
                continue
            x = round(cx + off * scale)
            if deg % 90:
                pyxel.pset(x, y + 5, STONE_I[4])  # small tick every 30 degrees
                continue
            pyxel.rect(x - 2, y + 2, 5, 7, BLACK)
            pyxel.text(x - 1, y + 3, COMPASS[deg // 90], FIRE_I[5])
        pyxel.tri(cx - 2, y + 14, cx + 2, y + 14, cx, y + 12, FIRE_I[4])  # heading marker

    def draw_messages(self):
        lines = self.world.messages.visible()
        y = H - 10 - 8 * len(lines)
        for text, age in lines:
            col = WHITE if age < 150 else STONE_I[5]
            x = (W - len(text) * 4) // 2
            pyxel.text(x + 1, y + 1, text, BLACK)
            pyxel.text(x, y, text, col)
            y += 8

    def draw_cursor(self):
        w = self.world
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        hover = w.hover
        hint = None
        if hover is not None and hover.t <= REACH and w.travel is None:
            if w.hand is None:
                hint = HINTS.get(hover.kind)
                if hover.kind == "door" and (hover.obj.controlled or hover.obj.lock is not None):
                    hint = "try"
            elif hover.kind == "floor":
                hint = "put down"
            elif hover.kind == "door" and hover.obj.lock is not None:
                hint = "use key"
        if w.hand is None:
            pyxel.mouse(True)
        else:
            pyxel.mouse(False)
            u, v = icon_uv(w.hand)
            pyxel.blt(mx - ICON // 2, my - ICON // 2, self.icons, u, v, ICON, ICON, BLACK)
            hint = hint or "throw"
        if hint:
            pyxel.text(mx + 10, my + 6, hint, BLACK)
            pyxel.text(mx + 9, my + 5, hint, FIRE_I[5])

    def draw_map(self):
        s = 4
        w = self.world
        d = w.floor.d
        ox = W - d.w * s - 4
        oy = 14
        pyxel.rect(ox - 2, oy - 2, d.w * s + 4, d.h * s + 4, BLACK)
        for gx, gy in w.explored.get(w.floor.name, ()):
            ch = d.char(gx, gy)
            col = {"O": BLACK, "X": FIRE_I[2], "U": FIRE_I[2], "D": FIRE_I[1], "_": STONE_I[5]}.get(ch, STONE_I[3])
            pyxel.rect(ox + gx * s, oy + gy * s, s, s, col)
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if d.is_wall(gx + dx, gy + dy):
                    pyxel.rect(ox + (gx + dx) * s, oy + (gy + dy) * s, s, s, STONE_I[6])
        p = w.player
        px = ox + p.x / CELL * s
        pz = oy + p.z / CELL * s
        pyxel.circ(px, pz, 1, FIRE_I[5])
        yr = math.radians(p.yaw)
        pyxel.line(px, pz, px + math.sin(yr) * 5, pz - math.cos(yr) * 5, FIRE_I[4])


if __name__ == "__main__":
    App()
