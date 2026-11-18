"""The save slots, shown when the game starts: pick a slot to go on with it, or an empty one to begin afresh.

Each slot is its own save file (save.py). The game saves to the chosen slot by
itself. X (or Delete) empties a slot after a yes, so that it can begin again.
"""

import pyxel

import lang
import save
from lang import tr
from palette import BLACK, FIRE_I, STONE_I, WHITE
from surface import draw_camp

W, H = 320, 240
BX, BY, BW = 40, 48, 240
SLOT_KEYS = (pyxel.KEY_1, pyxel.KEY_2, pyxel.KEY_3)


def box_h():
    return 2 * lang.line(10) + 10


class SlotScreen:
    def __init__(self, where=None):
        self.where = where  # the folder of the save files (None: the user's)
        self.sel = 0
        self.asking = None  # the slot (1..) whose deletion awaits a yes
        self.t = 0
        self.last_mouse = None
        save.migrate(where)
        self.refresh()

    def refresh(self):
        self.saves = [save.read(save.path(n, self.where)) for n in range(1, save.SLOTS + 1)]

    # ------------------------------------------------------------ choices (kept apart from the keys, for tests)
    def choose(self, slot):
        """Returns (slot, saved data or None for a new game)."""
        return slot, self.saves[slot - 1]

    def ask_delete(self, slot):
        if self.saves[slot - 1] is not None:
            self.asking = slot

    def answer(self, yes):
        if yes and self.asking is not None:
            save.delete(self.asking, self.where)
            self.refresh()
        self.asking = None

    # ------------------------------------------------------------ input
    def _slot_at(self, mx, my):
        i = (my - BY) // (box_h() + 6)
        inside = BX <= mx < BX + BW and 0 <= (my - BY) % (box_h() + 6) < box_h()
        return i + 1 if inside and 0 <= i < save.SLOTS else None

    def update(self, mx, my, clicked):
        """Returns (slot, data) once a slot is chosen, else None."""
        self.t += 1
        if pyxel.btnp(pyxel.KEY_L):
            lang.switch()
        if self.asking is not None:
            if pyxel.btnp(pyxel.KEY_Y) or pyxel.btnp(pyxel.KEY_RETURN):
                self.answer(True)
            elif pyxel.btnp(pyxel.KEY_N) or pyxel.btnp(pyxel.KEY_ESCAPE) or clicked:
                self.answer(False)
            return None
        if pyxel.btnp(pyxel.KEY_DOWN) or pyxel.btnp(pyxel.KEY_S) or pyxel.btnp(pyxel.KEY_TAB):
            self.sel = (self.sel + 1) % save.SLOTS
        if pyxel.btnp(pyxel.KEY_UP) or pyxel.btnp(pyxel.KEY_W):
            self.sel = (self.sel - 1) % save.SLOTS
        at = self._slot_at(mx, my)
        if at is not None and (mx, my) != self.last_mouse:  # the mouse moved onto a slot
            self.sel = at - 1
        self.last_mouse = (mx, my)
        for i, k in enumerate(SLOT_KEYS):
            if pyxel.btnp(k):
                return self.choose(i + 1)
        if clicked and at is not None:
            return self.choose(at)
        if pyxel.btnp(pyxel.KEY_SPACE) or pyxel.btnp(pyxel.KEY_RETURN):
            return self.choose(self.sel + 1)
        if pyxel.btnp(pyxel.KEY_X) or pyxel.btnp(pyxel.KEY_DELETE) or pyxel.btnp(pyxel.KEY_BACKSPACE):
            self.ask_delete(self.sel + 1)
        return None

    # ------------------------------------------------------------ draw
    def draw(self, mx, my):
        draw_camp(self.t)
        title = "PYXEL DUNGEON"
        th = 18 + lang.line(10)
        pyxel.rect(BX, BY - 10 - th, BW, th, BLACK)
        pyxel.rectb(BX, BY - 10 - th, BW, th, FIRE_I[3])
        lang.text(BX + (BW - lang.width(title)) // 2, BY - 5 - th, title, FIRE_I[5])
        sub = tr("Choose a save slot")
        lang.text(BX + (BW - lang.width(sub)) // 2, BY - 15 - th + 18 + 2, sub, STONE_I[6])
        for n in range(1, save.SLOTS + 1):
            y = BY + (n - 1) * (box_h() + 6)
            chosen = n == self.sel + 1
            pyxel.rect(BX, y, BW, box_h(), STONE_I[2] if chosen else BLACK)
            pyxel.rectb(BX, y, BW, box_h(), FIRE_I[4] if chosen else STONE_I[4])
            lang.text(BX + 8, y + 5, str(n), FIRE_I[4])
            data = self.saves[n - 1]
            if data is None:
                lang.text(BX + 20, y + 5, tr("(empty)"), STONE_I[6])
                lang.text(BX + 20, y + 5 + lang.line(10), tr("Begin a new game"), WHITE)
                continue
            s = save.summary(data)
            where = tr("Floor {n} reached", n=s["floor"]) if s["floor"] else tr("Not yet below the camp")
            lang.text(BX + 20, y + 5, where, WHITE)
            if s["saved"]:
                lang.text(BX + BW - 8 - lang.width(s["saved"]), y + 5, s["saved"], STONE_I[5])
            line = tr("{coins} coins, {done} requests done, {relics} relics settled",
                      coins=s["coins"], done=s["done"], relics=s["relics"])
            lang.text(BX + 20, y + 5 + lang.line(10), line, STONE_I[7])
        foot = tr("1-3, click or Space: play.  X: delete the slot.  L: language")
        if self.asking is not None:
            foot = tr("Delete slot {n}? It cannot be undone.  Y: delete  N: keep", n=self.asking)
        fy = BY + save.SLOTS * (box_h() + 6) + 6
        pyxel.rect(8, fy - 3, W - 16, lang.line(10) + 6, BLACK)
        lang.text((W - lang.width(foot)) // 2, fy, foot, FIRE_I[5] if self.asking else STONE_I[6])
