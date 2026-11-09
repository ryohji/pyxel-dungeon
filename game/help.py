"""The in-game help screen, drawn with Pyxel's built-in font."""

import pyxel

from palette import BLACK, FIRE_I, STONE_I, WHITE

LINE_H = 9

TITLE = "CONTROLS"
# (key, what it does); an empty key continues the previous line
HELP = [
    ("W A S D", "move (hold Shift to run)"),
    ("Q E / LEFT RIGHT", "turn"),
    ("UP DOWN", "look up / down (R levels the view)"),
    ("Right drag", "look around"),
    ("Left click", "act on what you point at: attack, take,"),
    ("", "pull, open, drink. Holding an item: put it"),
    ("", "down, use a key, fill a waterskin, or throw"),
    ("Tab", "choose the next target with the keyboard"),
    ("Space", "act on the target (Tab's or the mouse's,"),
    ("", "whichever you used last)"),
    ("I", "inventory: equip, eat, drink (pauses)"),
    ("M", "map"),
    ("F", "debug info (cost and fps)"),
    ("H", "open / close this help"),
]
NOTES = [
    "Mira casts bolts and heals on her own. Skills grow",
    "with use. Eat, drink and keep a torch burning.",
    "If the party falls, you restart at the floor's entrance.",
    "Turn off Japanese / IME input to play.",
]
FOOTER = "H, Esc or click to close"
HINT = "H: help"


class Help:
    def __init__(self):
        self.open = False

    def draw(self, w, h):
        x0, y0, bw = 10, 14, w - 20
        bh = 24 + LINE_H * (len(HELP) + len(NOTES)) + 20
        pyxel.dither(0.85)
        pyxel.rect(x0, y0, bw, bh, BLACK)
        pyxel.dither(1.0)
        pyxel.rectb(x0, y0, bw, bh, STONE_I[4])
        pyxel.text(x0 + 8, y0 + 7, TITLE, FIRE_I[5])
        y = y0 + 20
        for key, desc in HELP:
            pyxel.text(x0 + 8, y, key, FIRE_I[4])
            pyxel.text(x0 + 82, y, desc, WHITE)
            y += LINE_H
        y += 4
        for note in NOTES:
            pyxel.text(x0 + 8, y, note, STONE_I[6])
            y += LINE_H
        pyxel.text(x0 + bw - 8 - len(FOOTER) * 4, y0 + bh - 10, FOOTER, STONE_I[5])
