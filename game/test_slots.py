"""Headless checks of the save slots: three files, an old save.json becoming slot 1, choosing a slot,
deleting one after a yes, and what each slot shows.

Run: python test_slots.py   (exits non-zero on failure)
"""

import json
import os
import shutil
import tempfile

import pyxel

import lang
import save
from lang import tr
from palette import PALETTE
from slots import SlotScreen
from sound import NullSfx
from textures import make_atlas
from world import World

lang.current[0] = "en"
W, H = 320, 240
pyxel.init(W, H)
pyxel.colors[:] = PALETTE
atlas = make_atlas()
folder = tempfile.mkdtemp()


def check(cond, what):
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        raise SystemExit(1)


try:
    # 1. a save from before the slots becomes slot 1
    world = World(atlas, W, H, NullSfx(), start="camp")
    world.coins = 77
    save.write(world, os.path.join(folder, "save.json"))
    screen = SlotScreen(folder)
    check(os.path.exists(save.path(1, folder)) and not os.path.exists(os.path.join(folder, "save.json")),
          "the old save.json is slot 1 now")
    check(screen.saves[0]["coins"] == 77 and screen.saves[1] is None and screen.saves[2] is None,
          "slot 1 holds it; slots 2 and 3 are empty")

    # 2. choosing: a saved slot goes on, an empty one begins anew
    slot, data = screen.choose(1)
    check(slot == 1 and data["coins"] == 77, "slot 1: go on with its save")
    check(screen.choose(3) == (3, None), "slot 3: a new game")
    check(save.summary(data)["floor"] == 0, "a game not yet down below shows no floor reached")

    # 3. each slot is its own file
    world.explored["floor2"] = {(1, 1)}
    world.quests["ring"] = "done"
    save.write(world, save.path(3, folder))
    screen.refresh()
    s = save.summary(screen.saves[2])
    check(s["floor"] == 2 and s["coins"] == 77 and s["done"] == 1 and s["saved"], f"what slot 3 shows ({s})")
    check(screen.saves[0].get("floors", {}).get("floor2") is None, "slot 1 is untouched")

    # 4. deleting a slot needs a yes
    screen.sel = 0
    screen.ask_delete(1)
    check(screen.asking == 1, "asked before deleting slot 1")
    screen.answer(False)
    check(screen.asking is None and screen.saves[0] is not None, "no: it is kept")
    screen.ask_delete(1)
    screen.answer(True)
    check(screen.saves[0] is None and not os.path.exists(save.path(1, folder)), "yes: slot 1 is empty")
    screen.ask_delete(2)
    check(screen.asking is None, "nothing to ask for an empty slot")

    # 5. an old save.json is not moved over a slot 1 that is already there
    save.write(world, save.path(1, folder))
    with open(os.path.join(folder, "save.json"), "w") as f:
        json.dump({"coins": 1}, f)
    SlotScreen(folder)
    check(save.read(save.path(1, folder))["coins"] == 77, "slot 1 is not overwritten by an old save.json")

    # 6. the lines fit the screen in both languages
    from slots import BW
    for code in ("en", "ja"):
        lang.current[0] = code
        for line, room in ((tr("1-3, click or Space: play.  X: delete the slot.  L: language"), W - 16),
                           (tr("Delete slot {n}? It cannot be undone.  Y: delete  N: keep", n=2), W - 16),
                           (tr("{coins} coins, {done} requests done, {relics} relics settled",
                               coins=9999, done=5, relics=6), BW - 28)):
            check(lang.width(line) <= room, f"fits ({code}, {lang.width(line)} of {room} px): {line}")
    lang.current[0] = "en"
finally:
    shutil.rmtree(folder)

print("all checks passed")
