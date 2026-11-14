"""Headless checks of the old kingdom: relics, lore, carvings, niches, the scholar, world changes, the ending.

Run: python test_story.py   (exits non-zero on failure)
"""

import pyxel
from pyxel.cube import Vec3

from camp import CampScreen, restore
from enemies import Guardian
from objects import cell_center
from palette import PALETTE
from sound import NullSfx
from tables import LINES, RELICS
from textures import make_atlas
from things import Thing
from world import World

import lang

lang.current[0] = "en"  # these checks read the English lines
W, H = 320, 240
pyxel.init(W, H)
pyxel.colors[:] = PALETTE
sfx = NullSfx()
world = World(make_atlas(), W, H, sfx)
p = world.player
camp = CampScreen()


def check(cond, what):
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        raise SystemExit(1)


def place(cell, yaw, pitch=0.0):
    x, z = cell_center(cell)
    p.x, p.z, p.yaw, p.pitch = x, z, yaw, pitch


def tick(n=1):
    for _ in range(n):
        world.update(W // 2, H // 2, False)


def point_at_wall(cell, side, y=50):
    """Pick the face of a wall cell from the open cell on `side` (dx, dy)."""
    x, z = cell_center(cell)
    return world.pick(*world.project(Vec3(x + side[0] * 51, y, z + side[1] * 51)))


def undead(fl):
    return sum(e.alive and getattr(e, "UNDEAD", False) for e in fl.enemies)


# 1. the maps of the old kingdom load
f3 = world.get_floor("floor3")
check(any(isinstance(e, Guardian) for e in f3.enemies), "a stone guardian keeps the king's hall")
check(sum(fx.kind == "niche" for name in ("floor1", "floor2", "floor3")
          for fx in world.get_floor(name).fixtures.values()) == 3, "one seal niche on each floor")
check(len(RELICS) == 5 and sum(it.kind in RELICS for name in ("floor1", "floor2", "floor3")
                               for it in world.get_floor(name).items) == 5, "five relics lie in the dungeon")
world.floors = {"floor1": world.floor}

# 2. a carving speaks
place((1, 3), 270)
hit = point_at_wall((0, 3), (1, 0))
check(hit.kind == "carving", f"pointing at the carving (got {hit.kind})")
world.click(hit)
check(world.pages and world.pages[-1][0] == "A CARVING", "the carving's words are shown")
world.pages.clear()

# 3. a relic's lore, the first time only
fl = world.floor
shard = next(it for it in fl.items if it.kind == "relic_shard")
world._take(shard)
check(world.hand.kind == "relic_shard" and world.pages[-1][1] == RELICS["relic_shard"]["text"], "the shard tells its story")
world.pages.clear()

# 4. laying it in the niche: buried, darker, an undead falls
place((22, 2), 90)
mira_torch = world.party.mage.equip["left"]
tick()
dark0 = fl.view.dark
before = undead(fl)
hit = point_at_wall((23, 2), (-1, 0))
check(hit.kind == "niche" and world.action_name(hit) == "lay to rest", f"the niche offers rest (got {hit.kind})")
world.click(hit)
tick()
check(world.hand is None and world.relic_log == [("relic_shard", "bury", "floor1")], "the shard is buried")
check(fl.view.dark == dark0 + 1, f"the dark deepens ({dark0} -> {fl.view.dark})")
check(undead(fl) == before - 1, "a skeleton crumbled")
check(fl.fixtures[(23, 2)].contents == ["relic_shard"], "the niche holds the shard")

# 5. the scholar: talking, giving a relic, guardians wake, lamps relight
world.floor = world.get_floor("camp")
scholar = next(pp for pp in world.floor.people if pp.name == "scholar")
world.hand = Thing("relic_seal")
world.talk(scholar)
check(world.pages[0][1] == LINES["scholar_intro"]["text"], "Vesk introduces himself")
check(any(RELICS["relic_shard"]["scholar_bury"] == t for _, t in world.pages), "and grumbles about the buried shard")
check(world.screen == "scholar", "carrying a relic opens his table")
world.pages.clear()
camp.show("scholar")
check(any(r.label == "Give a bronze seal" for r in camp.rows(world)), "he offers to take the seal")
guardians = sum(isinstance(e, Guardian) for e in world.floors["floor1"].enemies)
restore(world, "relic_seal")
check(world.hand is None and world.relic_log[-1][:2] == ("relic_seal", "restore"), "the seal is restored")
check(sum(isinstance(e, Guardian) for e in world.floors["floor1"].enemies) == guardians + 1,
      "a guardian woke on floor 1")
world.floor = world.floors["floor1"]
tick()
check(fl.view.dark == dark0, "restored lamps undo the buried dark")

# 6. a floor first visited later reflects what was settled
f2 = world.get_floor("floor2")
check(f2.woken == 1 and any(not e.alive for e in f2.enemies), "floor 2 has one guardian awake and one skeleton fallen")

# 7. a wipe takes back what was settled after entering the floor
world._remember_entry()
world.relic_log.append(("relic_heart", "restore", "camp"))
world._restart_floor()
check(len(world.relic_log) == 2, "a restart forgets relics settled since entering")

# 8. the keeper speaks; a heavy relic is laid to rest from Arn's back
keeper = next(pp for pp in world.get_floor("camp").people if pp.name == "keeper")
world.pages.clear()
world.talk(keeper)
check(world.pages[0][1] == LINES["keeper_intro"]["text"] and len(world.pages) == 3, "the gravekeeper speaks of both relics")
world.pages.clear()
world.floor = world.floors["floor1"]
world.back = Thing("relic_tablet")
place((22, 2), 90)
world.click(point_at_wall((23, 2), (-1, 0)))
check(world.back is None and world.relic_log[-1][:2] == ("relic_tablet", "bury"), "the tablet laid to rest off Arn's back")

# 9. the last relics settle the ending
world.hand = Thing("relic_chronicle")
world.click(point_at_wall((23, 2), (-1, 0)))
check(world.ending is None, "no ending with one relic left")
world.floor = world.floors["camp"]
world.hand = Thing("relic_heart")
world.pages.clear()
restore(world, "relic_heart")
check(world.ending == "bury" and any(t == LINES["end_bury"]["text"] for _, t in world.pages), "three buried to two: the hill sleeps")

print("all checks passed")
