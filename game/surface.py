"""The camp above the dungeon, as one menu screen over a picture of it at dusk.

Coming up from a delve, the first thing shown is what it brought back
(world.report). Then the menu: Vesk, the gravekeeper, the smith, supplies,
the weapon rack, belongings, the two journals, and the way down. 1-9, Tab
and Space, or the mouse choose.
The way down opens a screen (camp.py) with the requests and where to go down.
"""

import math

import pyxel

import lang
from lang import tr
from palette import BLACK, BLUE_I, EARTH_I, FIRE_I, MOSS_I, PURPLE, RED, STONE_I, WHITE

W, H = 320, 240
MENU = [  # (action, label, what it is for)
    ("scholar", "Vesk, the scholar", "Talk. Give Vesk a relic and its power comes back to the hill."),
    ("keeper", "The gravekeeper", "Talk. The gravekeeper tends the dead of the hill."),
    ("smith", "The smith", "Weapons made from what you bring back: bones, and later more."),
    ("supplies", "Supplies", "Buy torches, bread and water with the coins you earned."),
    ("arms", "The weapon rack", "Choose Arn's weapon: the sword, the spear, or what the smith made."),
    ("pack", "Belongings", "Equip, eat and drink, sort the packs."),
    ("talk", "What people said", "Read again what Vesk and the gravekeeper told you."),
    ("relic", "Relics", "The relics found so far: their lore, and what became of each."),
    ("down", "Into the dungeon", "See the requests and take some, then go down the stairs or a shaft you opened."),
]
NUM_KEYS = (pyxel.KEY_1, pyxel.KEY_2, pyxel.KEY_3, pyxel.KEY_4, pyxel.KEY_5, pyxel.KEY_6, pyxel.KEY_7, pyxel.KEY_8,
            pyxel.KEY_9)
MX, MY, MW = 8, 26, 150
REPORT_COLORS = {"good": FIRE_I[5], "relic": STONE_I[7], "bad": STONE_I[5], "plain": WHITE}  # the words
MARK_COLORS = {"good": FIRE_I[4], "relic": BLUE_I[2], "bad": RED, "plain": WHITE}  # the dot before them


def row_h():
    return lang.line(10) + 2


class SurfaceScreen:
    def __init__(self):
        self.sel = 0
        self.t = 0

    # ------------------------------------------------------------ choices
    def rows(self, world):
        """(action, label, detail) of what can be chosen now."""
        return [(a, tr(label), tr(detail)) for a, label, detail in MENU]

    def _row_at(self, rows, mx, my):
        x, y, w = self._box(rows)
        i = (my - y) // row_h()
        return i if x <= mx < x + w and 0 <= i < len(rows) else None

    def _box(self, rows):
        return MX, MY, MW

    def update(self, world, mx, my, clicked, space, tab, moved):
        """Returns what the app should open ('down', 'supplies', 'smith', 'arms', 'pack', 'talk', ...) or None."""
        self.t += 1
        if world.report is not None:  # what this delve brought back: any key or a click goes on
            if clicked or space or pyxel.btnp(pyxel.KEY_RETURN) or pyxel.btnp(pyxel.KEY_ESCAPE):
                world.report = None
            return None
        rows = self.rows(world)
        if clicked or moved:
            world.mode = "mouse"
        if tab:
            world.mode = "keys"
            self.sel = (self.sel + 1) % len(rows)
        if pyxel.btnp(pyxel.KEY_DOWN):
            world.mode = "keys"
            self.sel = (self.sel + 1) % len(rows)
        if pyxel.btnp(pyxel.KEY_UP):
            world.mode = "keys"
            self.sel = (self.sel - 1) % len(rows)
        choice = None
        for i, k in enumerate(NUM_KEYS[:len(rows)]):
            if pyxel.btnp(k):
                choice = i
        if world.mode == "mouse":
            at = self._row_at(rows, mx, my)
            if at is not None:
                self.sel = at
            if clicked and at is not None:
                choice = at
        if (space or pyxel.btnp(pyxel.KEY_RETURN)) and choice is None:
            choice = self.sel
        if choice is None:
            return None
        self.sel = min(self.sel, len(rows) - 1)
        return self.choose(world, rows[choice][0])

    def choose(self, world, action):
        if action in ("scholar", "keeper"):
            world.talk(action)
        else:
            return action
        world.sfx.play("pickup")
        return None

    # ------------------------------------------------------------ draw
    def draw(self, world, mx, my):
        draw_camp(self.t)
        lang.text(MX + 2, 8, tr("THE CAMP"), WHITE)
        coins = tr("Coins: {n}", n=world.coins)
        pyxel.rect(W - 14 - lang.width(coins), 5, lang.width(coins) + 8, 13, BLACK)
        lang.text(W - 10 - lang.width(coins), 8, coins, FIRE_I[5])
        if world.report is not None:
            self.draw_report(world)
            return
        self.draw_menu(world, self.rows(world), mx, my)

    def draw_menu(self, world, rows, mx, my):
        x, y, w = self._box(rows)
        self._panel(x, y - 3, w, len(rows) * row_h() + 6)
        sel = self.sel if world.mode == "keys" else self._row_at(rows, mx, my)
        for i, (action, label, _) in enumerate(rows):
            ry = y + i * row_h()
            if i == sel:
                pyxel.rect(x + 3, ry, w - 6, row_h() - 1, STONE_I[2])
            lang.text(x + 6, ry + 2, str(i + 1), FIRE_I[4])
            lang.text(x + 16, ry + 2, label, WHITE)
        if sel is not None:
            detail = rows[sel][2]
            lines = lang.wrap(detail, W - 28)[:2]
            bh = len(lines) * lang.line(9) + 8
            self._panel(8, H - 10 - bh, W - 16, bh)
            for k, line in enumerate(lines):
                lang.text(14, H - 6 - bh + k * lang.line(9), line, STONE_I[7])

    def draw_report(self, world):
        lines = []
        for kind, text in world.report:
            for k, part in enumerate(lang.wrap(text, W - 52 - 30)):
                lines.append((kind, part, k == 0))
        step = lang.line(9)
        bh = 34 + len(lines) * step + 18
        x0, y0, bw = 26, max(24, (H - bh) // 2), W - 52
        self._panel(x0, y0, bw, bh, FIRE_I[3])
        title = tr("BACK AT THE CAMP")
        lang.text(x0 + (bw - lang.width(title)) // 2, y0 + 8, title, FIRE_I[5])
        if any(kind in ("good", "relic") for kind, _ in world.report):  # well done: a few sparks round the title
            for i in range(6):
                a = self.t * 0.05 + i * math.pi / 3
                sx = x0 + bw // 2 + math.cos(a) * (lang.width(title) // 2 + 14)
                sy = y0 + 12 + math.sin(a) * 6
                if (self.t // 6 + i) % 3:
                    pyxel.pset(sx, sy, FIRE_I[5] if i % 2 else WHITE)
        y = y0 + 30
        for kind, text, first in lines:
            if first:
                pyxel.rect(x0 + 10, y + 3, 3, 3, MARK_COLORS[kind])
            lang.text(x0 + 18, y, text, REPORT_COLORS[kind])
            y += step
        foot = tr("Space or click: to the camp")
        lang.text(x0 + bw - 8 - lang.width(foot), y0 + bh - 12, foot, STONE_I[5])

    @staticmethod
    def _panel(x, y, w, h, frame=STONE_I[4]):
        pyxel.rect(x, y, w, h, BLACK)
        pyxel.rectb(x, y, w, h, frame)


# ---------------------------------------------------------------- the picture
SKY = (BLUE_I[1], BLUE_I[2], PURPLE, FIRE_I[2], FIRE_I[3], FIRE_I[4], FIRE_I[5])
HORIZON = 150


def draw_camp(t):
    """The camp at dusk: a warm sky, the hill with the cellar's mouth, tents, a fire, two people."""
    # the sky, from deep blue to the glow over the horizon (dithered between bands)
    for y in range(HORIZON):
        k = y / HORIZON * (len(SKY) - 1)
        i = int(k)
        pyxel.line(0, y, W - 1, y, SKY[i])
        if i + 1 < len(SKY):
            pyxel.dither(k - i)
            pyxel.line(0, y, W - 1, y, SKY[i + 1])
            pyxel.dither(1.0)
    pyxel.circ(196, 142, 16, FIRE_I[5])  # the setting sun
    pyxel.circ(196, 142, 11, WHITE)
    for sx, sy in ((30, 18), (64, 34), (120, 12), (176, 26), (250, 10), (300, 30), (210, 48)):
        if (t // 20 + sx) % 7:
            pyxel.pset(sx, sy, STONE_I[7])  # the first stars
    # far hills, then the near ground
    for x in range(W):
        far = 138 + 6 * math.sin(x * 0.027) + 4 * math.sin(x * 0.083 + 1)
        pyxel.line(x, far, x, H, BLUE_I[1])
        near = 168 + 5 * math.sin(x * 0.019 + 2) + 2 * math.sin(x * 0.11)
        pyxel.line(x, near, x, H, MOSS_I[1])
    # the hill over the dungeon, and the cellar's mouth in its side
    for x in range(160, W):
        top = 112 + ((x - 262) / 70) ** 2 * 40
        pyxel.line(x, top, x, H, MOSS_I[2] if x < 250 else MOSS_I[1])
    pyxel.rect(246, 150, 34, 36, STONE_I[4])
    pyxel.rect(250, 154, 26, 32, BLACK)
    pyxel.circ(263, 156, 13, STONE_I[4])
    pyxel.circ(263, 157, 9, BLACK)
    pyxel.rect(254, 157, 18, 29, BLACK)
    for y in range(160, 186, 6):  # steps going down into the dark
        pyxel.line(255, y, 271, y, STONE_I[2])
    pyxel.rect(234, 166, 4, 20, EARTH_I[2])  # a post with a lantern
    lit = FIRE_I[5] if t // 9 % 5 else FIRE_I[4]
    pyxel.rect(231, 162, 10, 5, EARTH_I[3])
    pyxel.rect(233, 167, 6, 6, lit)
    # tents
    for x, col, shade in ((170, EARTH_I[6], EARTH_I[4]), (204, EARTH_I[5], EARTH_I[3])):
        pyxel.tri(x, 200, x + 30, 200, x + 15, 172, col)
        pyxel.tri(x + 15, 172, x + 30, 200, x + 22, 200, shade)
        pyxel.tri(x + 12, 200, x + 18, 200, x + 15, 186, BLACK)
    # the old request board, its notes now read before going down
    pyxel.rect(146, 186, 2, 22, EARTH_I[2])
    pyxel.rect(162, 186, 2, 22, EARTH_I[2])
    pyxel.rect(143, 180, 24, 14, EARTH_I[4])
    for i, (nx, ny) in enumerate(((146, 182), (154, 183), (159, 181), (149, 188))):
        pyxel.rect(nx, ny, 5, 4, (STONE_I[7], WHITE, EARTH_I[7])[i % 3])
    # the fire, and its light on the ground
    fx, fy = 214, 214
    pyxel.dither(0.3)
    pyxel.elli(fx - 30, fy - 6, 60, 16, FIRE_I[3])
    pyxel.dither(1.0)
    pyxel.line(fx - 9, fy + 3, fx + 9, fy - 1, EARTH_I[2])
    pyxel.line(fx - 9, fy - 1, fx + 9, fy + 3, EARTH_I[3])
    flick = (t // 4) % 3
    pyxel.tri(fx - 7, fy, fx + 7, fy, fx + flick - 1, fy - 14 - flick, FIRE_I[3])
    pyxel.tri(fx - 4, fy, fx + 4, fy, fx - flick + 1, fy - 9, FIRE_I[5])
    for i in range(3):  # sparks rising
        k = (t * 0.7 + i * 23) % 40
        pyxel.pset(fx + math.sin(k * 0.3 + i) * 4, fy - 14 - k, FIRE_I[5] if k < 25 else FIRE_I[3])
    # the smith's corner: an anvil, a glowing forge, the smith in a leather apron
    pyxel.rect(64, 196, 18, 14, STONE_I[3])
    pyxel.rect(67, 192, 12, 5, STONE_I[2])
    glow = FIRE_I[4] if t // 7 % 3 else FIRE_I[5]
    pyxel.rect(70, 199, 8, 5, glow)
    pyxel.rect(88, 204, 12, 3, STONE_I[5])  # the anvil
    pyxel.rect(92, 207, 4, 6, STONE_I[4])
    pyxel.rect(106, 200, 9, 14, EARTH_I[2])
    pyxel.rect(107, 193, 7, 7, EARTH_I[6])
    pyxel.rect(106, 205, 9, 9, EARTH_I[4])
    # Vesk (blue robe) and the gravekeeper (grey), sitting by the fire
    for x, robe, hood in ((190, BLUE_I[2], BLUE_I[1]), (236, STONE_I[3], STONE_I[2])):
        pyxel.rect(x - 4, 202, 9, 12, robe)
        pyxel.rect(x - 3, 195, 7, 7, EARTH_I[6])
        pyxel.rect(x - 4, 194, 9, 4, hood)
