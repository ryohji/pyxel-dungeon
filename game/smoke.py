"""Smoke test: drive the game with scripted input and save screenshots.

Usage: python smoke.py OUT_DIR
"""

import os
import sys

import pyxel

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)

# frame -> set of keys held; screenshots at the listed frames
SCRIPT = [
    (0, 40, {pyxel.KEY_W}),
    (40, 70, {pyxel.KEY_E}),
    (70, 160, {pyxel.KEY_W, pyxel.KEY_SHIFT}),
    (160, 190, {pyxel.KEY_A}),
    (190, 230, {pyxel.KEY_W, pyxel.KEY_Q}),
    (230, 260, {pyxel.KEY_UP}),
]
SHOTS = {1, 60, 150, 229, 260}
held = set()
real_btn, real_btnp = pyxel.btn, pyxel.btnp


def fake_btn(key, *a, **k):
    return key in held


def fake_btnp(key, *a, **k):
    return key == pyxel.KEY_F and pyxel.frame_count == 1 or (key == pyxel.KEY_TAB and pyxel.frame_count == 200)


pyxel.btn, pyxel.btnp = fake_btn, fake_btnp
real_run = pyxel.run


def run(update, draw):
    def u():
        f = pyxel.frame_count
        held.clear()
        for a, b, keys in SCRIPT:
            if a <= f < b:
                held.update(keys)
        update()

    def d():
        draw()
        f = pyxel.frame_count
        if f in SHOTS:
            pyxel.screen.save(os.path.join(OUT, f"f{f:03d}.png"), 2)
        if f >= max(SHOTS):
            pyxel.quit()

    real_run(u, d)


pyxel.run = run
sys.argv = [os.path.join(os.path.dirname(__file__), "main.py")]
import main  # noqa: E402,F401
