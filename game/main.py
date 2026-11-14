"""Pyxel Dungeon (P6): the camp, requests, and bringing things back.

Controls
  W A S D        move / strafe        Shift  run
  Q E, <- ->     turn                 up/down  look up / down
  right drag     look around          R      level the view
  left click     act on what the mouse points at: attack, take, pull,
                 open, drink; holding an item: put down, use a key, throw
  Tab            choose the next target with the keyboard
  Space          act on the target (the Tab choice, or what the mouse
                 points at: whichever was used last)
  1-4            pick a rune (power, then element, then shape)
  Enter          cast the runes       Backspace  take the last rune back
  I              inventory (pauses)   M      map
  F              debug info           H      help (pauses; Esc also closes it)

Arn (you) fights up front; Mira follows, casting bolts and healing on her own.
"""

import math
import sys
import time

import pyxel

from camp import CampScreen
from devtools import HELP as DEV_HELP, DevTools
from dungeon import CELL
from enemies import Guardian
from help import HINT, Help
from ime import LatinInput
from inventory import Inventory
import lang
from lang import tr
from palette import BLACK, BLUE_I, EARTH_I, FIRE_I, MOSS_I, PALETTE, RED, STONE_I, WHITE
from reading import Journal, Reader
from runes import RunePanel, draw_glyph
from sound import Sfx
from textures import ICON, draw_icon, make_atlas, make_icons
from world import World

W, H = 320, 240
TITLE = "Pyxel Dungeon"
START = "camp"  # the floor a new game begins on

COMPASS = ("N", "E", "S", "W")

PANEL_W, PANEL_H = 70, 24


class App:
    START = START
    def __init__(self):
        # no quit key: Esc closes the help screen instead (quit by closing the window)
        pyxel.init(W, H, title=TITLE, fps=60, quit_key=pyxel.KEY_NONE)
        self.latin = LatinInput(TITLE)  # a composing input method would swallow held keys
        pyxel.colors[:] = PALETTE
        self.icons = make_icons()
        self.world = World(make_atlas(), W, H, Sfx(), start=self.START)
        if sys.platform == "emscripten":  # in a browser the input method is out of our hands
            self.world.messages.add(tr("Tip: turn off Japanese/IME input to play."))
        self.help = Help()
        self.help.open = True  # first thing a new player sees
        self.inventory = Inventory(self.icons)
        self.runes = RunePanel(H)
        self.camp = CampScreen()
        self.reader = Reader()
        self.journal = Journal()
        self.last_mouse = None
        self.show_map = False
        self.show_debug = False
        self.dev = DevTools()
        self.cost_ms = 0.0
        self.update_ms = 0.0
        self.frame_ms = 16.7  # measured time between frames (smoothed)
        self.last_frame = None
        pyxel.run(self.update, self.draw)

    def pointer(self):
        """Mouse position and whether the left button was just clicked."""
        return pyxel.mouse_x, pyxel.mouse_y, pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT)

    def update(self):
        t0 = time.perf_counter()
        if pyxel.frame_count % 30 == 0:
            self.latin.tick()
        closing = pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT) or pyxel.btnp(pyxel.KEY_ESCAPE)
        if pyxel.btnp(pyxel.KEY_H) or (self.help.open and closing):
            self.help.open = not self.help.open
            self.update_ms = 0.0
            return
        if self.help.open:
            return  # paused while reading
        mx, my, clicked = self.pointer()
        moved = self.last_mouse is not None and (mx, my) != self.last_mouse
        self.last_mouse = (mx, my)
        tab, space = pyxel.btnp(pyxel.KEY_TAB), pyxel.btnp(pyxel.KEY_SPACE)
        if self.reader.open:  # paused while reading
            self.reader.update(clicked)
            return
        if self.journal.open:  # paused while reading the journal again
            self.journal.update(self.world.journal, mx, clicked)
            return
        if self.camp.open:  # paused at the board or the counter
            if pyxel.btnp(pyxel.KEY_ESCAPE):
                self.camp.close()
            else:
                self.camp.update(self.world, mx, my, clicked, space, tab, moved)
                self.take_pages()
            return
        if self.inventory.open:  # paused while sorting belongings
            if pyxel.btnp(pyxel.KEY_I) or pyxel.btnp(pyxel.KEY_ESCAPE):
                self.inventory.open = False
            else:
                self.inventory.update(self.world, mx, my, clicked, space, tab, moved)
            return
        if pyxel.btnp(pyxel.KEY_ESCAPE):
            self.show_map = False
        if pyxel.btnp(pyxel.KEY_M):
            self.show_map = not self.show_map
        if pyxel.btnp(pyxel.KEY_L):
            lang.switch()
            self.world.messages.add(tr("Language: English"))
        if pyxel.btnp(pyxel.KEY_J):
            self.journal.show(self.world.journal)
            return
        if pyxel.btnp(pyxel.KEY_F):
            self.show_debug = not self.show_debug
        if self.show_debug:
            self.dev.update(self.world)
        if pyxel.btnp(pyxel.KEY_I) or (clicked and self.panel_at(mx, my) is not None):
            self.inventory.open = True
            return
        if self.runes.update(self.world, mx, my, clicked):
            clicked = False  # the click was on the rune panel, not the dungeon
        self.world.update(mx, my, clicked, attack_key=space, tab=tab, mouse_moved=moved)
        self.take_pages()
        self.update_ms = (time.perf_counter() - t0) * 1000

    def take_pages(self):
        """Open whatever the world wants shown: pages to read first, then a camp screen."""
        w = self.world
        while w.pages:
            self.reader.show(*w.pages.pop(0))
        if w.screen is not None:
            self.camp.show(w.screen)
            w.screen = None

    # ------------------------------------------------------------ draw
    def draw(self):
        t0 = time.perf_counter()
        if self.last_frame is not None:
            self.frame_ms = self.frame_ms * 0.95 + (t0 - self.last_frame) * 1000 * 0.05
        self.last_frame = t0
        w = self.world
        w.floor.view.draw(0, 0, W, H)
        draw_ms = (time.perf_counter() - t0) * 1000
        self.cost_ms = self.cost_ms * 0.9 + (self.update_ms + draw_ms) * 0.1
        self.draw_popups()
        self.draw_sword()
        if w.hurt_flash:
            pyxel.dither(0.5)
            for i in range(4):
                pyxel.rectb(i, i, W - 2 * i, H - 2 * i, RED)
            pyxel.dither(1.0)
        if w.flash:  # light and dark in turn, so the flash keeps its contrast
            pyxel.dither(0.35 if w.flash % 2 else 0.25)
            pyxel.rect(0, 0, W, H, WHITE if w.flash % 2 else BLACK)
            pyxel.dither(1.0)
        if w.fade > 0:
            pyxel.dither(min(1.0, w.fade))
            pyxel.rect(0, 0, W, H, BLACK)
            pyxel.dither(1.0)
        self.draw_compass()
        self.draw_party()
        self.runes.draw(w, pyxel.mouse_x, pyxel.mouse_y)
        self.draw_wards()
        self.draw_messages()
        if self.show_map:
            self.draw_map()
        self.draw_load()
        if self.world.mode == "keys" and not (self.inventory.open or self.camp.open or self.reader.open or self.journal.open):
            self.draw_target()
        if self.show_debug:
            p = w.player
            gx, gy = p.cell
            pyxel.text(4, 16, f"{w.floor.name} cell {gx},{gy} yaw {p.yaw:5.1f} pitch {p.pitch:5.1f}", WHITE)
            pyxel.text(4, 24, f"cells {w.floor.view.cells_drawn:3d}  cost {self.cost_ms:4.1f}ms  "
                              f"fps {1000 / self.frame_ms:4.1f}", WHITE)
            pyxel.text(4, 32, DEV_HELP, FIRE_I[4])
        lang.text(4, 4, tr(HINT), STONE_I[4])
        if self.inventory.open:
            self.inventory.draw(w, pyxel.mouse_x, pyxel.mouse_y)
        if self.camp.open:
            self.camp.draw(w, pyxel.mouse_x, pyxel.mouse_y)
        if self.reader.open:
            self.reader.draw(H)
        if self.journal.open:
            self.journal.draw(self.world.journal, H)
        if self.help.open:
            self.help.draw(W, H)
            pyxel.mouse(True)
        else:
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

    def panel_at(self, mx, my):
        """The member whose panel is under the mouse (clicking it opens the inventory)."""
        party = self.world.party
        for m, x in ((party.fighter, 4), (party.mage, W - 4 - PANEL_W)):
            if x <= mx < x + PANEL_W and H - 4 - PANEL_H <= my < H - 4:
                return m
        return None

    def draw_party(self):
        """One panel per member: name, health, stamina, mana and readiness."""
        party = self.world.party
        for m, x in ((party.fighter, 4), (party.mage, W - 4 - PANEL_W)):
            y = H - 4 - PANEL_H
            frame = RED if m.hit_flash % 4 >= 2 else STONE_I[3]
            pyxel.rect(x, y, PANEL_W, PANEL_H, BLACK)
            pyxel.rectb(x, y, PANEL_W, PANEL_H, frame)
            pyxel.text(x + 3, y + 3, m.name, WHITE if m.up else STONE_I[4])
            hp = f"{m.hp}/{m.max_hp}" if m.up else "down"
            pyxel.text(x + 67 - len(hp) * 4, y + 3, hp, FIRE_I[5] if m.up else STONE_I[4])
            bw = PANEL_W - 6
            for row, (v, top, col) in enumerate(((m.hp, m.max_hp, RED), (m.stamina, m.max_stamina, MOSS_I[2]),
                                                  (m.mana, m.max_mana, BLUE_I[2]))):
                if not top:
                    continue
                by = y + 10 + row * 4
                pyxel.rect(x + 3, by, bw, 3 if row == 0 else 2, STONE_I[1])
                pyxel.rect(x + 3, by, round(bw * max(0, v) / top), 3 if row == 0 else 2, col)
            ready = 1 - m.cooldown / m.cooldown_max if m.cooldown else 1.0
            pyxel.rect(x + 3, y + 21, round(bw * ready), 1, FIRE_I[4] if ready >= 1 else STONE_I[3])
            if m.food < 20 or m.water < 20:  # hungry or thirsty: a small warning dot
                pyxel.circ(x + PANEL_W - 4, y + PANEL_H - 4, 1, EARTH_I[6] if pyxel.frame_count // 20 % 2 else RED)

    def draw_load(self):
        """What Arn carries on his back, above his panel."""
        back = self.world.back
        if back is None:
            return
        x, y = 4, H - 4 - PANEL_H - 19
        pyxel.rect(x, y, 18, 18, BLACK)
        pyxel.rectb(x, y, 18, 18, FIRE_I[3])
        draw_icon(self.icons, back, x + 1, y + 1)
        lang.text(x + 21, y + 6, tr("on your back"), STONE_I[6])

    def draw_wards(self):
        """Spells on the party, with the seconds they have left."""
        x = 4
        for element, (frames, _) in sorted(self.world.party.wards.items()):
            if frames > 180 or frames // 8 % 2:  # blink in the last three seconds
                draw_glyph(element, x, 14)
            pyxel.text(x + 11, 16, str(frames // 60 + 1), STONE_I[6])
            x += 26

    def draw_sword(self):
        """The sword sweeping across the view while Arn swings, with a faint trail."""
        s = self.world.swing
        if not s:
            return
        k = 1 - s / 12
        for lag, alpha in ((0.24, 0.25), (0.12, 0.5), (0.0, 1.0)):
            if k - lag < 0:
                continue
            self._blade(math.radians(-80 - 85 * (k - lag)), alpha)
        pyxel.dither(1.0)

    def _blade(self, a, alpha):
        px, py = W * 0.9, H + 40
        dx, dy = math.cos(a), math.sin(a)
        nx, ny = -dy, dx
        bx, by = px + dx * 60, py + dy * 60
        tx, ty = px + dx * 235, py + dy * 235
        w = 9
        pyxel.dither(alpha)
        pyxel.tri(bx + nx * w, by + ny * w, bx - nx * w, by - ny * w, tx, ty, STONE_I[5])
        if alpha < 1:
            return
        pyxel.line(bx + nx * w, by + ny * w, tx, ty, STONE_I[7])
        pyxel.line(bx, by, tx, ty, STONE_I[3])  # fuller groove
        for i in range(-1, 2):
            pyxel.line(bx - nx * 22 + dx * i, by - ny * 22 + dy * i, bx + nx * 22 + dx * i, by + ny * 22 + dy * i, EARTH_I[3])

    def draw_popups(self):
        for pos, text, age, kind in self.world.popups:
            sp = self.world.project(pos)
            if sp is None:
                continue
            x, y = sp[0] - len(text) * 2, sp[1] - age * 0.6
            pyxel.text(x + 1, y + 1, text, BLACK)
            pyxel.text(x, y, text, FIRE_I[5] if kind else WHITE)

    def draw_messages(self):
        rows = [(part, age) for text, age in self.world.messages.visible() for part in lang.wrap(text, W - 16)]
        step = lang.line(8)
        y = H - 34 - step * len(rows)
        for text, age in rows:
            col = WHITE if age < 150 else STONE_I[5]
            x = (W - lang.width(text)) // 2
            lang.text(x + 1, y + 1, text, BLACK)
            lang.text(x, y, text, col)
            y += step

    def draw_target(self):
        """Corner brackets around the target chosen with Tab, with what Space will do."""
        w = self.world
        hit = w.key_target
        if hit is None or w.travel is not None:
            if w.hand is not None:
                draw_icon(self.icons, w.hand, W // 2 - ICON // 2, H // 2 - ICON // 2)
            return
        x, y = hit.screen
        s = max(6, min(26, 1600 / max(hit.t, 1)))
        col = FIRE_I[5] if pyxel.frame_count // 15 % 2 else FIRE_I[4]
        for sx in (-1, 1):
            for sy in (-1, 1):
                cx, cy = x + sx * s, y + sy * s
                pyxel.line(cx, cy, cx - sx * 4, cy, col)
                pyxel.line(cx, cy, cx, cy - sy * 4, col)
        label = w.action_name(hit)
        if label:
            label = tr(label)
            lx = x - lang.width(label) // 2
            lang.text(lx + 1, y + s + 4, label, BLACK)
            lang.text(lx, y + s + 3, label, FIRE_I[5])
        if w.hand is not None:
            draw_icon(self.icons, w.hand, x + s - 4, y - s - 12)

    def draw_cursor(self):
        w = self.world
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        if w.mode == "keys":
            pyxel.mouse(False)  # the keyboard has the target; moving the mouse takes it back
            return
        hint = None if self.inventory.open or self.camp.open or self.reader.open or self.journal.open else w.action_name(w.hover)
        if w.hand is None:
            pyxel.mouse(True)
        else:
            pyxel.mouse(False)
            draw_icon(self.icons, w.hand, mx - ICON // 2, my - ICON // 2)
        if hint:
            hint = tr(hint)
            lang.text(mx + 10, my + 6, hint, BLACK)
            lang.text(mx + 9, my + 5, hint, FIRE_I[5])

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
        for e in w.floor.enemies:  # stone guardians are felt through the rock, seen or not
            if e.alive and isinstance(e, Guardian):
                gx, gy = e.cell
                pyxel.rectb(ox + gx * s - 1, oy + gy * s - 1, s + 2, s + 2, BLUE_I[2])
        p = w.player
        px = ox + p.x / CELL * s
        pz = oy + p.z / CELL * s
        pyxel.circ(px, pz, 1, FIRE_I[5])
        yr = math.radians(p.yaw)
        pyxel.line(px, pz, px + math.sin(yr) * 5, pz - math.cos(yr) * 5, FIRE_I[4])


if __name__ == "__main__":
    App()
