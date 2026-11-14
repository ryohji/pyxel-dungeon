"""A pause to read: relic lore, wall carvings, notes, what people at the camp say, the ending.

Space, Esc, Enter or a click closes it. The journal (J) shows what was read
again, sorted into three books (records.py): what people said, the relics
(with what became of each), and the carvings and notes. Tab or 1-3 picks a
book, left/right or a click on either half turns the page, J or Esc closes.
"""

import pyxel

import lang
import records
from lang import tr

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
        draw_page(*self.pages[0], h, tr("J: read again later   Space or click") + tr(more))


class Journal:
    """Three books of what was read: what people said, the relics, the carvings and notes."""

    def __init__(self):
        self.open = False
        self.book = "talk"
        self.i = 0

    def show(self, world, book=None):
        """Open a book (by default the one with the newest page) at its newest page."""
        if book is None:
            book = records.book(world.journal[-1]) if world.journal else "talk"
        self.open = True
        self._turn_to(world, book)

    def _turn_to(self, world, book):
        self.book = book
        self.i = max(0, len(records.entries(world.journal, book)) - 1)

    def update(self, world, mx, clicked):
        if pyxel.btnp(pyxel.KEY_J) or pyxel.btnp(pyxel.KEY_ESCAPE):
            self.open = False
            return
        names = [b for b, _ in records.BOOKS]
        for k, b in zip((pyxel.KEY_1, pyxel.KEY_2, pyxel.KEY_3), names):
            if pyxel.btnp(k):
                self._turn_to(world, b)
        if pyxel.btnp(pyxel.KEY_TAB):
            self._turn_to(world, names[(names.index(self.book) + 1) % len(names)])
            return
        if clicked and pyxel.mouse_y < TABS_Y + 12:  # a click on a book's tab
            for b, x0, x1 in self._tabs():
                if x0 <= mx < x1:
                    self._turn_to(world, b)
            return
        step = 0
        if pyxel.btnp(pyxel.KEY_LEFT) or pyxel.btnp(pyxel.KEY_A) or (clicked and mx < 160):
            step = -1
        if pyxel.btnp(pyxel.KEY_RIGHT) or pyxel.btnp(pyxel.KEY_D) or (clicked and mx >= 160):
            step = 1
        n = len(records.entries(world.journal, self.book))
        if n:
            self.i = max(0, min(n - 1, self.i + step))

    def _tabs(self):
        """(book, x from, x to) of the tabs along the top."""
        out, x = [], X0
        for b, title in records.BOOKS:
            w = lang.width(tr(title)) + 12
            out.append((b, x, x + w))
            x += w + 4
        return out

    def draw(self, world, h):
        pyxel.dither(0.7)  # the view behind steps back
        pyxel.rect(0, 0, 320, h, BLACK)
        pyxel.dither(1.0)
        for b, x0, x1 in self._tabs():
            here = b == self.book
            pyxel.rect(x0, TABS_Y, x1 - x0, 13, STONE_I[3] if here else BLACK)
            pyxel.rectb(x0, TABS_Y, x1 - x0, 13, FIRE_I[3] if here else STONE_I[3])
            lang.text(x0 + 6, TABS_Y + 3, tr(dict(records.BOOKS)[b]), FIRE_I[5] if here else STONE_I[5])
        entries = records.entries(world.journal, self.book)
        if not entries:
            draw_page(tr(dict(records.BOOKS)[self.book]), tr(EMPTY[self.book]), h, tr("Tab: next book  Esc: close"), top=TABS_Y + 18)
            return
        self.i = min(self.i, len(entries) - 1)
        entry = entries[self.i]
        title, text = records.page(entry)
        if entry[0] == "relic":
            text += "\\n" + records.fate(world, entry[1])
        draw_page(title, text, h, f"{self.i + 1}/{len(entries)}  " + tr("<- ->: turn  Tab: next book  Esc: close"),
                  top=TABS_Y + 18)


TABS_Y = 6
EMPTY = {
    "talk": "Nothing heard yet. What Vesk and the gravekeeper say at the camp is kept here.",
    "relic": "No relic found yet. A relic's lore, and what became of it, is kept here.",
    "other": "Nothing read yet. Carvings on the walls and notes found in the dungeon are kept here.",
}


def draw_page(title, text, h, foot, top=8):
    lines = []
    for para in text.split("\\n"):
        lines += lang.wrap(para, W_ - 16)
    step = lang.line(9)
    bh = 30 + len(lines) * step + 16
    y0 = max(top, (h - 30 - bh) // 2)
    pyxel.dither(1.0)  # solid: Japanese letters need a calm background
    pyxel.rect(X0, y0, W_, bh, BLACK)
    pyxel.dither(1.0)
    pyxel.rectb(X0, y0, W_, bh, FIRE_I[2])
    lang.text(X0 + 8, y0 + 7, title, FIRE_I[5])
    y = y0 + 22
    for line in lines:
        lang.text(X0 + 8, y, line, WHITE)
        y += step
    lang.text(X0 + W_ - 8 - lang.width(foot), y0 + bh - 12, foot, STONE_I[5])
