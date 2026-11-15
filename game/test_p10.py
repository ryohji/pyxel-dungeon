"""Headless checks of P10: three weapons and the weapon rack, the heavy blow learned from a book
brought back, the smith's first recipe, and skills that stop at a habit of 5.

Run: python test_p10.py   (exits non-zero on failure)
"""

import json
import math

import pyxel

import lang
import save
from camp import CampScreen, carried, count
from enemies import Guardian
from objects import cell_center
from palette import PALETTE
from sound import NullSfx
from tables import HABIT_TOP, LEVELS, RECIPES, TUNE, WEAPONS
from textures import make_atlas
from things import Thing
from world import World

lang.current[0] = "en"
W, H = 320, 240
pyxel.init(W, H)
pyxel.colors[:] = PALETTE
atlas = make_atlas()
world = World(atlas, W, H, NullSfx(), start="camp")
p = world.player
arn = world.party.fighter
camp = CampScreen()


def check(cond, what):
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        raise SystemExit(1)


def row(label):
    return next(r for r in camp.rows(world) if r.label == label)


def skeletons(n, start=(20, 9), step=(1, 0)):
    """n skeletons standing in a row ahead of the player (who faces +x), fully healed and idle."""
    out = [e for e in world.floor.enemies if e.KIND == "skeleton"][:n]
    for i, e in enumerate(out):
        e.x, e.z = p.x + 100 + 60 * i * step[0], p.z + 60 * i * step[1]
        e.hp = 99
        e._set("idle")
    return out


def ready():
    arn.cooldown = 0
    arn.stamina = arn.max_stamina
    world.hitstop = 0


# 1. habits stop at 5
check(max(lv for lv, _, _ in LEVELS["fighter"]) == HABIT_TOP == 5, "skills.csv stops at a habit of 5")
world.award(arn, "fighter", 10 ** 6)
check(arn.level["fighter"] == HABIT_TOP, "no habit above 5, however much practice")

# 2. the weapon rack: the sword in hand, the spear on the rack
check(arn.equip["right"].kind == "sword" and world.armory == ["spear"], "Arn holds the sword; the spear is on the rack")
camp.show("arms")
row("a spear").action(world)
check(arn.equip["right"].kind == "spear" and world.armory == ["sword"], "took the spear; the sword went back on the rack")
check(world.weapon()["reach"] > WEAPONS["sword"]["reach"], "the spear reaches further")

# 3. in the dungeon: the spear's reach, and no use with a load on the back
world.descend()
for _ in range(40):
    world.update(W // 2, H // 2, False)
world.floor.enemies[:] = [e for e in world.floor.enemies if e.KIND == "skeleton"]
p.yaw = 90.0  # facing +x
(e,) = skeletons(1)
e.x = p.x + 170  # beyond a sword, within a spear
ready()
world.attack(e)
check(e.hp < 99, "the spear hits at 170")
check(arn.cooldown >= WEAPONS["spear"]["cooldown"] - 4 * TUNE["swing_cooldown_per_level"], "and it is slow")
world.back = Thing("idol")
e.hp = 99
ready()
world.attack(e)
check(e.hp == 99 and any("spear is no use" in t for t, _ in world.messages.visible()), "with a load, the spear does not reach")
world.back = None

# 4. the heavy blow: not before the book is brought back
ready()
world.heavy_blow()
check(any("no heavy blow" in t for t, _ in world.messages.visible()), "no heavy blow before the book")
world.party.fighter.give(Thing("drill_book"))
world.arrive_surface()
check("heavy" in world.techniques and count(world, "drill_book") == 0, "the book brought back: the heavy blow learned")
check(any("heavy blow" in line for _, line in world.report), "the report says so")
world.report = None
world.descend()
for _ in range(40):
    world.update(W // 2, H // 2, False)
world.floor.enemies[:] = [e for e in world.floor.enemies if e.KIND == "skeleton"]
p.yaw = 90.0

# spear: runs through a line
line = skeletons(2)
line[1].x = p.x + 240
ready()
world.heavy_blow()
check(all(e.hp < 99 for e in line), "the spear's heavy blow runs through both in the line")
check(arn.stamina == arn.max_stamina - TUNE["tech_stamina"], "it costs stamina")

# sword: sweeps everything in front
world.armory.remove("sword")
world.armory.append("spear")
arn.equip["right"] = Thing("sword")
pair = skeletons(2)
pair[0].x, pair[0].z = p.x + 90, p.z - 50
pair[1].x, pair[1].z = p.x + 90, p.z + 50
ready()
world.heavy_blow()
check(all(e.hp < 99 for e in pair), "the sword's heavy blow sweeps both in front")

# 5. the smith: a maul from three bones and coins
TUNE["bone_drop"] = 1.0
(e,) = skeletons(1)
e.x = p.x + 80
e.hp = 1
ready()
world.attack(e)
check(any(it.kind == "bone" for it in world.floor.items), "a fallen skeleton leaves a bone")
arn.give(Thing("bone"))
world.arrive_surface()
check(world.store.get("bone") == 1 and carried(world, "bone") == 0, "bones brought back go into the camp store")
check(any("camp store" in line for _, line in world.report), "the report says so")
world.report = None
recipe = next(r for r in RECIPES if r["kind"] == "maul")
camp.show("smith")
check(not row("a bone maul").enabled, "not enough bones yet")
for _ in range(recipe["count"] - 1):
    arn.give(Thing("bone"))
world.coins = recipe["coins"] + 5
check(row("a bone maul").enabled, "three bones and the coins: it can be made")
row("a bone maul").action(world)
check("maul" in world.armory and count(world, "bone") == 0 and world.coins == 5, "the smith made the maul (store first)")
check(not any(r.label == "a bone maul" for r in camp.rows(world)), "a maul already made is not offered again")
camp.show("arms")
row("a bone maul").action(world)
check(arn.equip["right"].kind == "maul", "Arn takes the maul")

# 6. the maul breaks stone, and is heavy with a load
world.descend()
for _ in range(40):
    world.update(W // 2, H // 2, False)
world.relic_log.append(("relic_seal", "restore", "camp"))
g = world.floor.wake_guardian()
g.x, g.z = p.x + 80, p.z
g.hp = 999
p.yaw = 90.0
amounts = []
orig = world._damage_enemy
world._damage_enemy = lambda enemy, amount, *a, **k: amounts.append(amount)
world.rnd.seed(1)
ready()
world.attack(g)
world._damage_enemy = orig
check(amounts and amounts[0] >= 2 * (7 + arn.bonus("str", "str_per_damage", "fighter")) - 1, f"the maul hits stone twice as hard ({amounts})")
world.back = Thing("idol")
check(math.isclose(p.speed_scale(), TUNE["carry_speed"] * WEAPONS["maul"]["load_speed"]), "the maul slows a loaded Arn more")
world.back = None

# 7. with the maul made, bones are of no more use to the smith: the gravekeeper takes them
world.descend()
arn.give(Thing("bone"))
arn.give(Thing("bone"))
coins = world.coins
world.arrive_surface()
check(count(world, "bone") == 0 and world.coins == coins + 2 * TUNE["bone_coins"], "spare bones laid to rest for coins")
check(any("laid 2 bones to rest" in line for _, line in world.report), "the report says so")
world.report = None

# 8. the rack and the heavy blow are saved
data = json.loads(json.dumps(save.dump(world)))
other = World(atlas, W, H, NullSfx(), start="camp")
save.restore(other, data)
check(other.armory == world.armory and other.techniques == {"heavy"}, "the rack and the heavy blow come back")
data.pop("armory")
data.pop("techniques")
data["party"][0]["level"]["fighter"] = 6
older = World(atlas, W, H, NullSfx(), start="camp")
save.restore(older, data)
check(older.armory == ["spear"] and older.party.fighter.level["fighter"] == HABIT_TOP, "an older save gets the spear, and its habits capped")

# 9. things a later version adds to a map show up in an older save
data = json.loads(json.dumps(save.dump(world)))
check("drill_book" not in [d["kind"] for d in data["floors"]["floor2"]["items"]] if "floor2" in data["floors"] else True,
      "the book was taken")
data["floors"]["floor2"] = dict(items=[], doors={}, switches={}, broken=[],
                                placed=[[k, x, y] for (x, y), k in world.get_floor("floor2").d.items if k != "drill_book"])
again = World(atlas, W, H, NullSfx(), start="camp")
save.restore(again, data)
check([it.kind for it in again.floors["floor2"].items] == ["drill_book"], "an item new on the map is put there")
data["floors"]["floor2"]["placed"] = [[k, x, y] for (x, y), k in world.get_floor("floor2").d.items]
again = World(atlas, W, H, NullSfx(), start="camp")
save.restore(again, data)
check(again.floors["floor2"].items == [], "one that was on the map when saved is not put back")
old = json.loads(json.dumps(data))
del old["floors"]["floor2"]["placed"]
old["techniques"] = []
for m in old["party"]:
    m["pack"] = [t for t in m["pack"] if t is None or t["kind"] != "drill_book"]
again = World(atlas, W, H, NullSfx(), start="camp")
save.restore(again, old)
check("drill_book" in [it.kind for it in again.floors["floor2"].items], "a save from before P10 finds the drill book on floor 2")

print("all checks passed")
