"""A pause to read: relic lore, wall carvings, notes, what people at the camp say, the ending.

Space, Esc, Enter or a click closes it. The journal (J) shows every page
read so far again, one at a time: left/right or a click on either half
turns the page, J or Esc closes it.
"""

import textwrap

import pyxel

from palette import BLACK, FIRE_I, STONE_I, WHITE

X0, W_ = 30, 260
WRAP = 60


class Reader:
    def __init__(self):
        self.pages = []  # [(title, text)], shown one after another

    @property
    def open(self):
        return bool(self.pages)

    def show(self, title, text):
        self.pages.append((title, text))

    def update(self, clicked):
        if clicked or any(pyxel.btnp(k) for k in (pyxel.KEY_SPACE, pyxel.KEY_ESCAPE, pyxel.KEY_RETURN)):
            self.pages.pop(0)

    def draw(self, h):
        more = " (more)" if len(self.pages) > 1 else ""
        draw_page(*self.pages[0], h, "J: read again later   Space or click" + more)


class Journal:
    def __init__(self):
        self.open = False
        self.i = 0

    def show(self, entries):
        self.open = True
        self.i = len(entries) - 1  # the newest page first

    def update(self, entries, mx, clicked):
        if pyxel.btnp(pyxel.KEY_J) or pyxel.btnp(pyxel.KEY_ESCAPE):
            self.open = False
            return
        step = 0
        if pyxel.btnp(pyxel.KEY_LEFT) or pyxel.btnp(pyxel.KEY_A) or (clicked and mx < 160):
            step = -1
        if pyxel.btnp(pyxel.KEY_RIGHT) or pyxel.btnp(pyxel.KEY_D) or pyxel.btnp(pyxel.KEY_TAB) or (clicked and mx >= 160):
            step = 1
        if entries:
            self.i = max(0, min(len(entries) - 1, self.i + step))

    def draw(self, entries, h):
        if not entries:
            draw_page("JOURNAL", "Nothing written yet. Relic lore, carvings, notes and what people say are kept here.",
                      h, "J/Esc: close")
            return
        title, text = entries[self.i]
        draw_page(title, text, h, f"{self.i + 1}/{len(entries)}  <- ->: turn  J/Esc: close")


def draw_page(title, text, h, foot):
    lines = []
    for para in text.split("\\n"):
        lines += textwrap.wrap(para, WRAP) or [""]
    bh = 30 + len(lines) * 9 + 14
    y0 = max(8, (h - 30 - bh) // 2)
    pyxel.dither(0.92)
    pyxel.rect(X0, y0, W_, bh, BLACK)
    pyxel.dither(1.0)
    pyxel.rectb(X0, y0, W_, bh, FIRE_I[2])
    pyxel.text(X0 + 8, y0 + 7, title, FIRE_I[5])
    y = y0 + 22
    for line in lines:
        pyxel.text(X0 + 8, y, line, WHITE)
        y += 9
    pyxel.text(X0 + W_ - 8 - len(foot) * 4, y0 + bh - 10, foot, STONE_I[5])
