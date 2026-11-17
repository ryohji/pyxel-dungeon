"""Headless checks of P8: the camp menu, the delve and its report, falling and the load left behind,
the shaft as a shortcut, the dead rising again, saving and loading, and the journal's three books.

Run: python test_p8.py   (exits non-zero on failure)
"""

import json
import os
import tempfile

import pyxel

import lang
import records
import save
from objects import cell_center
from palette import PALETTE
from sound import NullSfx
from camp import CampScreen
from surface import SurfaceScreen
from tables import RELICS, REQUESTS
from textures import make_atlas
from things import Thing
from world import WIPE_FRAMES, World

lang.current[0] = "en"  # these checks read the English lines
W, H = 320, 240
pyxel.init(W, H)
pyxel.colors[:] = PALETTE
atlas = make_atlas()
world = World(atlas, W, H, NullSfx(), start="camp")
p = world.player
menu = SurfaceScreen()
camp = CampScreen()


def check(cond, what):
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        raise SystemExit(1)


def tick(n=1, **keys):
    for _ in range(n):
        world.update(W // 2, H // 2, False, **keys)


def take(kind):
    it = next(i for i in world.floor.items if i.kind == kind)
    world._take(it)


def climb(cell):
    """Walk onto a cell from its side and wait for the trip up."""
    x, z = cell_center(cell)
    p.x, p.z = x + 100, z
    world.arrived_on = None
    tick()
    p.x, p.z = x, z
    for _ in range(200):
        tick()
        if world.surface:
            return


# 1. the menu at the camp
check(world.surface and world.report is None, "a new game starts at the camp")
check([a for a, _, _ in menu.rows(world)] == ["scholar", "keeper", "smith", "supplies", "arms", "pack", "talk", "relic", "down"],
      "no board or counter in the menu")
check(menu.choose(world, "down") == "down" and menu.choose(world, "pack") == "pack", "the menu opens the way down and the packs")
menu.choose(world, "scholar")
check(world.pages and ("talk", "scholar", "intro") in world.journal, "Vesk talks, and it goes in the journal")
world.pages.clear()

# 2. down the stairs; a request done on the way back
world.quests["ring"] = "accepted"
camp.show("down")
next(r for r in camp.rows(world) if r.first).action(world)
check(not world.surface and world.floor.name == "floor1" and p.cell == (1, 1), "into the dungeon at floor 1's stairs")
check(world.want_save, "leaving the camp asks for a save")
world.want_save = False
tick(40)
check(world.travel is None, "the fade from the dark is over")
take("ring")
coins = world.coins
climb((1, 1))
check(world.surface and world.report, "back at the camp, with a report")
check(world.quests["ring"] == "done" and world.coins == coins + REQUESTS["ring"]["reward"], "the ring was handed over by itself")
check(any("done" in line for _, line in world.report) and any("Coins earned" in line for _, line in world.report),
      f"the report says so ({world.report})")
check(world.hand is None, "the ring is gone from the hand")
world.report = None

# 3. the dead rise again; a broken guardian stays broken
world.descend()
skeleton = next(e for e in world.floor.enemies if e.KIND == "skeleton")
skeleton.hp = 0
skeleton._set("dead")
world.relic_log.append(("relic_seal", "restore", "camp"))
guardian = world.floor.wake_guardian()
guardian.hp = 0
guardian._set("dead")
world.descend()
check(all(e.alive for e in world.floor.enemies if e.KIND == "skeleton"), "the skeletons stand again")
check(not any(e.KIND == "guardian" and getattr(e, "slot", None) == 0 for e in world.floor.enemies),
      "the broken guardian does not")

# 4. falling: the load stays where the party fell, the party wakes at the camp
tick(40)
world.back = Thing("idol")
world.hand = Thing("rock")
p.x, p.z = cell_center((3, 10))
for m in world.party.members:
    m.hp = 1
world.hit_party(50, skeleton)
world.hit_party(50, skeleton)
check(world.wipe is not None, "the party fell")
tick(WIPE_FRAMES + world.hitstop + 2)
check(world.surface and world.back is None and world.hand is None, "carried back to the camp, empty-handed")
check(all(m.hp == m.max_hp for m in world.party.members), "rested")
lost = [it for it in world.floors["floor1"].items if it.thing.lost]
check(sorted(it.kind for it in lost) == ["idol", "rock"] and all(it.cell == (3, 10) for it in lost),
      "the idol and the rock lie where the party fell")
check(any("Left where you fell" in line for _, line in world.report), "the report says what was left")
world.report = None
world.descend()
tick(40)
world._take(next(it for it in world.floor.items if it.kind == "idol" and it.thing.lost))
check(world.back.kind == "idol" and not world.back.lost, "taken back: no longer marked as lost")

# 5. the shaft on floor 4: climbing it opens a way down from the camp
world.back = None
world.floor = world.get_floor("floor4")
p.solid = world.floor.solid
climb((7, 1))
check(world.surface and world.shortcuts == ["floor4"], "climbed the shaft: it is open now")
check(any("shaft from floor 4" in line for _, line in world.report), "the report tells of the shaft")
world.report = None
camp.show("down")
ways = [r for r in camp.rows(world) if r.label.startswith("Floor")]
check(len(ways) == 2 and ways[0].first, "the way down offers the stairs (first) and the shaft")
ways[1].action(world)
check(world.floor.name == "floor4" and p.cell == (7, 1) and world.arrived_on == (7, 1), "down the shaft to floor 4")
tick(40)
check(not world.surface, "standing on the rope does not pull you straight back up")

# 6. saving and loading
world.read(("relic", "relic_shard"))
world.read(("carving", "floor1", 0, 3))
world.coins = 77
world.floors["floor1"].doors[(3, 6)].target_open = True
data = json.loads(json.dumps(save.dump(world)))  # as it would go through the file
check(data["version"] == save.VERSION, "the save has a version")
other = World(atlas, W, H, NullSfx(), start="camp")
save.restore(other, data)
check(other.surface and other.coins == 77 and other.quests == world.quests, "coins and requests come back")
check(other.shortcuts == ["floor4"] and other.relic_log == world.relic_log, "the shaft and the relics' fates come back")
check(other.journal == world.journal, "the journal comes back")
check(other.floors["floor1"].doors[(3, 6)].target_open, "an opened door stays open")
check(sorted(it.kind for it in other.floors["floor1"].items if it.thing.lost) == ["rock"], "the rock still lies where it fell")
check(other.party.fighter.level == world.party.fighter.level, "skills come back")
check(0 in other.floors["floor1"].broken, "the broken guardian stays broken")
folder = tempfile.mkdtemp()
file = os.path.join(folder, "save.json")
save.write(world, file)
check(save.read(file)["coins"] == 77, "written to a file and read back")
check(save.read(os.path.join(folder, "none.json")) is None, "no save: nothing to load")
data["version"] = 0
try:
    save.restore(World(atlas, W, H, NullSfx(), start="camp"), data)
    check(False, "an old save is refused")
except ValueError:
    check(True, "an old save is refused")

# 7. the journal's three books, and what became of each relic
check([e[0] for e in records.entries(world.journal, "talk")] == ["talk"], "what people said")
check(records.entries(world.journal, "relic") == [("relic", "relic_shard")], "the relics")
check(records.entries(world.journal, "other")[0][0] == "carving", "the carvings and notes")
check(records.page(("relic", "relic_shard"))[1] == RELICS["relic_shard"]["text"], "a relic's page is its lore")
check(records.fate(world, "relic_seal").startswith("Given to Vesk"), "a restored relic's fate")
check(records.fate(world, "relic_heart") == "Left in the dungeon.", "a relic not yet found")
lang.current[0] = "ja"
check(records.page(("talk", "scholar", "intro"))[0] == "学者ヴェスク", "a page comes out in the language in use")
lang.current[0] = "en"

print("all checks passed")
