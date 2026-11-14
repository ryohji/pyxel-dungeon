"""Views of P7 in Japanese for visual checks: messages, help, inventory, camp screens, reading, journal, runes, hit flash.

Usage: python shots_p7.py OUT_DIR
"""

import os
import sys

import pyxel

import main
from objects import cell_center
from tables import RELICS
from things import Thing

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)


def go(floor, cell, yaw, pitch=0.0):
    def setup(app):
        w = app.world
        w.floor = w.get_floor(floor)
        w.player.solid = w.floor.solid
        p = w.player
        p.x, p.z = cell_center(cell)
        p.yaw, p.pitch = yaw, pitch
        for e in w.floor.enemies:
            e.update = lambda floor, world, e=e: e.node.refresh()
    return setup


def both(*fs):
    def setup(app):
        for f in fs:
            f(app)
    return setup


def messages(app):
    w = app.world
    w.messages.add("松明を拾った。")
    w.messages.add("この階には石の守護者がいる（2 体）。M で位置が分かる。")
    w.messages.add("ルーンが不発: アルンの魔術師の技能が足りない。")


def help_(app):
    app.help.open = True


def inventory(app):
    app.world.hand = Thing("waterskin")
    app.inventory.open = True


def board(app):
    app.camp.show("board")


def counter(app):
    app.world.quests = {"ring": "accepted", "brenn": "accepted"}
    app.camp.show("counter")


def lore(app):
    from lang import loc
    app.world.read("王冠の欠片", loc(RELICS["relic_shard"], "text"))


def journal(app):
    from lang import loc
    w = app.world
    w.read("心臓石", loc(RELICS["relic_heart"], "text"))
    w.pages.clear()
    app.journal.show(w.journal)


def runes(app):
    app.runes.runes[:] = [2, "fire"]
    app.world.mode = "keys"


def flash(app):
    w = app.world
    w.flash = 5
    w.hitstop = 8


SCENES = [
    ("messages", both(go("floor1", (3, 3), 0), messages), 2),
    ("help", both(go("floor1", (3, 3), 0), help_), 2),
    ("inventory", both(go("floor1", (3, 3), 0), inventory), 2),
    ("board", both(go("camp", (5, 2), 0), board), 2),
    ("counter", both(go("camp", (5, 2), 0), counter), 2),
    ("lore", both(go("floor1", (3, 3), 0), lore), 2),
    ("journal", both(go("floor1", (3, 3), 0), journal), 2),
    ("runes_target", both(go("floor1", (6, 12), 90), runes), 3),
    ("flash", both(go("floor1", (6, 12), 90), flash), 1),
]


class ShotApp(main.App):
    START = "camp"

    def __init__(self):
        self.scene = 0
        self.wait = None
        super().__init__()

    def pointer(self):
        return 300, 20, False

    def update(self):
        if self.wait is None:
            self.help.open = False
            self.inventory.open = False
            self.camp.close()
            self.journal.open = False
            self.world.hand = None
            name, setup, frames = SCENES[self.scene]
            setup(self)
            self.wait = frames
        if not self.help.open:
            super().update()

    def draw(self):
        super().draw()
        self.wait -= 1
        if self.wait == 0:
            pyxel.screen.save(os.path.join(OUT, SCENES[self.scene][0] + ".png"), 2)
            self.reader.pages.clear()
            self.scene += 1
            self.wait = None
            if self.scene == len(SCENES):
                pyxel.quit()


ShotApp()
