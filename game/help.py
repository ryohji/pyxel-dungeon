"""The in-game help screen, in English (Pyxel's built-in font) or Japanese (the M+ font)."""

import pyxel

import lang

from palette import BLACK, FIRE_I, STONE_I, WHITE

LINE_H = 9

TITLE = "CONTROLS"
# (key, what it does); an empty key continues the previous line
HELP = [
    ("W A S D", "move (hold Shift to run)"),
    ("Q E / LEFT RIGHT", "turn (UP DOWN look, R levels)"),
    ("Right drag", "look around"),
    ("Left click", "act on what you point at: attack, take,"),
    ("", "pull, open, drink. Holding an item: put it"),
    ("", "down, use a key, fill a waterskin, or throw"),
    ("Tab", "choose the next target with the keyboard"),
    ("Space", "act on the target (Tab's or the mouse's,"),
    ("", "whichever you used last)"),
    ("1 2 3 4", "runes: power, then element, then shape"),
    ("Enter", "cast them (Backspace takes one back)"),
    ("I", "inventory: equip, eat, drink (pauses)"),
    ("J", "journal: read lore, carvings, notes again"),
    ("L", "language: Japanese / English"),
    ("M  F", "map, debug info"),
    ("H", "open / close this help"),
]
NOTES = [
    "Fire Frost Light Life x Bolt Ward Burst Wall. Power needs",
    "skill. Skills grow with use. Eat, drink, keep a torch lit.",
    "Take requests at the camp board, bring things back to the counter.",
    "Turn off Japanese / IME input to play.",
]
FOOTER = "H, Esc or click to close"

TITLE_JA = "操作"
HELP_JA = [
    ("W A S D", "移動（Shift を押しながらで走る）"),
    ("Q E / ← →", "向きを変える（↑↓ で上下、R で水平）"),
    ("右ドラッグ", "見回す"),
    ("左クリック", "指した物に働きかける（攻撃、拾う、"),
    ("", "レバー、扉、水を飲む）。物を持っていれば、"),
    ("", "床に置く・鍵を使う・水袋を満たす・投げる"),
    ("Tab / Space", "対象を選ぶ / 対象に働きかける"),
    ("1 2 3 4", "ルーン（強さ→属性→形の順）"),
    ("Enter", "唱える（Backspace で 1 つ戻す）"),
    ("I", "持ち物（装備、食べる、飲む。一時停止）"),
    ("J", "覚え書き（読んだ物をもう一度読む）"),
    ("L  M  F", "言語の切り替え、地図、開発用の表示"),
    ("H", "このヘルプを開く / 閉じる"),
]
NOTES_JA = [
    "掲示板で依頼を受け、持ち帰って受付に渡す。",
    "食べて、飲んで、松明を絶やさないこと。",
]
FOOTER_JA = "H、Esc、クリックで閉じる"
HINT = "H: help"


class Help:
    def __init__(self):
        self.open = False

    def draw(self, w, h):
        if lang.ja():
            title, rows, notes, footer, step, key_w = TITLE_JA, HELP_JA, NOTES_JA, FOOTER_JA, 12, 70
        else:
            title, rows, notes, footer, step, key_w = TITLE, HELP, NOTES, FOOTER, LINE_H, 74
        x0, y0, bw = 10, 6, w - 20
        bh = 24 + step * (len(rows) + len(notes)) + 20
        pyxel.dither(1.0)  # solid: Japanese letters need a calm background
        pyxel.rect(x0, y0, bw, bh, BLACK)
        pyxel.dither(1.0)
        pyxel.rectb(x0, y0, bw, bh, STONE_I[4])
        lang.text(x0 + 8, y0 + 7, title, FIRE_I[5])
        y = y0 + 20
        for key, desc in rows:
            lang.text(x0 + 8, y, key, FIRE_I[4])
            lang.text(x0 + 8 + key_w, y, desc, WHITE)
            y += step
        y += 4
        for note in notes:
            lang.text(x0 + 8, y, note, STONE_I[6])
            y += step
        lang.text(x0 + bw - 8 - lang.width(footer), y0 + bh - 12, footer, STONE_I[5])
