"""The rune panel at the bottom of the screen.

Pick one rune from each row in turn (power, element, shape) by clicking it
or with the number keys 1-4, then cast with Enter or the CAST button.
Backspace (or the < button) takes the last rune back. The game keeps
running while you choose.
"""

import pyxel

from palette import BLACK, BLUE_I, FIRE_I, MOSS_I, STONE_I, WHITE
from spells import ROW_NAMES, ROWS, SPELLS, describe

X, W_, H_ = 82, 156, 24
NUM_KEYS = (pyxel.KEY_1, pyxel.KEY_2, pyxel.KEY_3, pyxel.KEY_4)
GLYPH_COL = {"fire": FIRE_I[4], "frost": BLUE_I[2], "light": FIRE_I[5], "life": MOSS_I[2]}


def draw_glyph(rune, x, y, col=None):
    """A 9x9 sign for a rune, top-left at (x, y)."""
    c = col if col is not None else GLYPH_COL.get(rune, STONE_I[7])
    if isinstance(rune, int):  # power: rising bars
        for i in range(rune):
            h = 3 + i * 2
            pyxel.rect(x + i * 2 + 1 + (4 - rune), y + 9 - h, 1, h, c)
    elif rune == "fire":
        pyxel.tri(x + 4, y, x, y + 8, x + 8, y + 8, c)
        pyxel.tri(x + 4, y + 4, x + 2, y + 8, x + 6, y + 8, FIRE_I[5] if col is None else c)
    elif rune == "frost":
        pyxel.line(x + 4, y, x + 4, y + 8, c)
        pyxel.line(x, y + 2, x + 8, y + 6, c)
        pyxel.line(x, y + 6, x + 8, y + 2, c)
    elif rune == "light":
        pyxel.circ(x + 4, y + 4, 2, c)
        for dx, dy in ((0, -4), (0, 4), (-4, 0), (4, 0), (-3, -3), (3, 3), (-3, 3), (3, -3)):
            pyxel.pset(x + 4 + dx, y + 4 + dy, c)
    elif rune == "life":
        pyxel.rect(x + 3, y, 3, 9, c)
        pyxel.rect(x, y + 3, 9, 3, c)
    elif rune == "bolt":
        pyxel.line(x, y + 4, x + 8, y + 4, c)
        pyxel.line(x + 5, y + 1, x + 8, y + 4, c)
        pyxel.line(x + 5, y + 7, x + 8, y + 4, c)
    elif rune == "ward":
        pyxel.circb(x + 4, y + 4, 4, c)
        pyxel.pset(x + 4, y + 4, c)
    elif rune == "burst":
        for dx, dy in ((0, -4), (0, 4), (-4, 0), (4, 0), (-3, -3), (3, 3), (-3, 3), (3, -3)):
            pyxel.line(x + 4 + dx // 2, y + 4 + dy // 2, x + 4 + dx, y + 4 + dy, c)
    elif rune == "wall":
        pyxel.rectb(x, y + 1, 9, 7, c)
        pyxel.line(x, y + 4, x + 8, y + 4, c)
        pyxel.line(x + 4, y + 1, x + 4, y + 4, c)
        pyxel.line(x + 2, y + 4, x + 2, y + 7, c)
        pyxel.line(x + 6, y + 4, x + 6, y + 7, c)


class RunePanel:
    def __init__(self, h):
        self.y = h - 4 - H_
        self.runes = []
        self.flash = 0  # frames to light the panel after a cast

    # ------------------------------------------------------------ layout
    def buttons(self):
        """(kind, value, x, y, w, h) of everything clickable."""
        y = self.y + 11
        out = []
        if len(self.runes) < 3:
            for i, rune in enumerate(ROWS[len(self.runes)]):
                out.append(("rune", rune, X + 44 + i * 13, y, 11, 11))
        out.append(("back", None, X + 98, y, 11, 11))
        out.append(("cast", None, X + 113, y, 40, 11))
        return out

    def contains(self, mx, my):
        return X <= mx < X + W_ and self.y <= my < self.y + H_

    # ------------------------------------------------------------ input
    def update(self, world, mx, my, clicked):
        """Keys and clicks for the panel. Returns True when a click landed on it."""
        self.flash = max(0, self.flash - 1)
        if len(self.runes) < 3:
            for i, key in enumerate(NUM_KEYS):
                if pyxel.btnp(key):
                    self.runes.append(ROWS[len(self.runes)][i])
                    break
        if pyxel.btnp(pyxel.KEY_BACKSPACE) and self.runes:
            self.runes.pop()
        if pyxel.btnp(pyxel.KEY_RETURN):
            self.cast(world)
        if not (clicked and self.contains(mx, my)):
            return False
        for kind, value, x, y, w, h in self.buttons():
            if x <= mx < x + w and y <= my < y + h:
                if kind == "rune":
                    self.runes.append(value)
                elif kind == "back" and self.runes:
                    self.runes.pop()
                elif kind == "cast":
                    self.cast(world)
        return True

    def cast(self, world):
        if len(self.runes) < 3:
            world.messages.add(f"Choose a {ROW_NAMES[len(self.runes)]} rune first.")
            return
        result = world.cast(tuple(self.runes))
        if result != "wait":
            self.runes.clear()
            self.flash = 12 if result == "cast" else 0

    # ------------------------------------------------------------ draw
    def draw(self, world, mx, my):
        y = self.y
        caster = world.party.leader
        frame = FIRE_I[4] if self.flash % 4 >= 2 else STONE_I[3]
        pyxel.rect(X, y, W_, H_, BLACK)
        pyxel.rectb(X, y, W_, H_, frame)
        name, cost = describe(self.runes)
        if name:
            col = WHITE if caster.mana >= cost else STONE_I[5]
            text = f"{name}  {cost} MP"
        else:
            col = STONE_I[5]
            text = f"{ROW_NAMES[len(self.runes)]} rune: 1-4"
        pyxel.text(X + 3, y + 3, text, col)
        mp = f"{int(caster.mana)}/{caster.max_mana}"
        pyxel.text(X + W_ - 3 - len(mp) * 4, y + 3, mp, BLUE_I[2])
        for i in range(3):
            bx = X + 3 + i * 13
            pyxel.rectb(bx, y + 11, 11, 11, STONE_I[2])
            if i < len(self.runes):
                draw_glyph(self.runes[i], bx + 1, y + 12)
        ready = not caster.cooldown and caster.up
        for kind, value, x, by, w, h in self.buttons():
            over = x <= mx < x + w and by <= my < by + h and world.mode == "mouse"
            pyxel.rect(x, by, w, h, STONE_I[2] if over else STONE_I[1])
            if kind == "rune":
                draw_glyph(value, x + 1, by + 1)
            elif kind == "back":
                pyxel.text(x + 4, by + 3, "<", STONE_I[6])
            else:
                ok = len(self.runes) == 3 and ready
                pyxel.text(x + 12, by + 3, "CAST", FIRE_I[5] if ok else STONE_I[4])
