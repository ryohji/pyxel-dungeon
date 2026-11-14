"""Headless checks of P7: enemy numbers from CSV, hit stop, the development keys.

Run: python test_p7.py   (exits non-zero on failure)
"""

import pyxel

import devtools
import tables
from enemies import Guardian, Skeleton
from palette import PALETTE
from sound import NullSfx
from textures import make_atlas
from world import World

import lang

lang.current[0] = "en"  # these checks read the English lines
W, H = 320, 240
pyxel.init(W, H)
pyxel.colors[:] = PALETTE
world = World(make_atlas(), W, H, NullSfx())


def check(cond, what):
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        raise SystemExit(1)


def tick(n=1, **keys):
    for _ in range(n):
        world.update(W // 2, H // 2, False, **keys)


# 1. enemy numbers come from data/enemies.csv
check(Skeleton.MAX_HP == tables.ENEMIES["skeleton"]["max_hp"] and Guardian.DAMAGE[1] == tables.ENEMIES["guardian"]["damage_max"],
      "enemy numbers are read from enemies.csv")

# 2. a blow stops the action for a moment and shakes only the struck enemy
fl = world.floor
sk = next(e for e in fl.enemies if isinstance(e, Skeleton))
x, z = sk.x, sk.z
world._damage_enemy(sk, 4, sk.x - 50, sk.z, world.party.fighter, "fighter")
stop = world.hitstop
check(stop >= tables.TUNE["hitstop_base"], f"the hit stops the action ({stop} frames)")
t0 = sk.t
tick(1, attack_key=True)
check(sk.t == t0 and world.held[1], "the enemy is frozen, and Space pressed meanwhile is kept")
check(sk.jolt > 0, "the enemy shakes")
tick(stop)
check(world.hitstop == 0 and sk.jolt == 0 and not any(world.held), "the action goes on and the held key was used")

# 3. a killing blow stops longer and flashes
world._damage_enemy(sk, 99, sk.x - 50, sk.z)
check(world.hitstop >= tables.TUNE["hitstop_kill"] and world.flash > 0, "a kill stops longer and flashes")
tick(world.hitstop + 1)

# 4. development: warp, no harm, reload
devtools.warp(world, "floor3")
check(world.floor.name == "floor3" and not world.floor.solid(*world.player.cell), "warped to floor 3")
world.no_harm = True
hp = world.party.fighter.hp
world.hit_party(9, sk)
check(world.party.fighter.hp == hp, "no harm while the switch is on")
old = tables.ENEMIES["skeleton"]
devtools.reload(world)
check(tables.ENEMIES["skeleton"] is not old and Skeleton.MAX_HP == tables.ENEMIES["skeleton"]["max_hp"],
      "reload reads the tables again")
check(devtools.floor_names() == ["camp", "floor1", "floor2", "floor3"], "the floors in order")

# 5. Japanese
from lang import TEXT, loc, tr
from tables import ITEMS, RELICS
from things import Thing
lang.current[0] = "ja"
check(Thing("torch").name == "松明" and tr("You take {name}.", name=Thing("torch").name) == "松明を拾った。",
      "item names and lines come out in Japanese")
check(loc(RELICS["relic_heart"], "text").startswith("ゆっくり"), "relic lore in Japanese")
world.messages.add(tr("It is locked."))
check(world.messages.lines[-1][0] == "鍵がかかっている。", "a message in Japanese")
devtools.warp(world, "floor1")
carving = world.floor.fixtures[(0, 3)]
check(carving.text_ja.startswith("すり減った"), "a carving has its Japanese words")
check(all(len(lang.wrap(loc(r, "text"), 244)) > 1 for r in RELICS.values()), "long Japanese lines wrap")
check(all(lang.width(line) <= 244 for r in RELICS.values() for line in lang.wrap(loc(r, "text"), 244)),
      "wrapped lines fit the width")
check(all(r["name_ja"] for r in ITEMS.values()), "every item has a Japanese name")
import glob
import re
keys = set()
for f in glob.glob("*.py"):
    if not f.startswith(("test_", "shots")):
        keys |= {m.group(1) for m in re.finditer(r'tr\(\s*"((?:[^"\\]|\\.)*)"', open(f, encoding="utf-8").read())}
missing = sorted(k for k in keys if k not in TEXT and not k.endswith(" "))
check(not missing, f"every line in the code has a Japanese version (missing: {missing})")
lang.current[0] = "en"
check(Thing("torch").name == "a torch", "and back to English")

print("all checks passed")
