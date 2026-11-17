"""Headless checks of P11: the catacombs on floor 3. Coffins that open in the dark, sconces that keep
them shut, moths that put out flames, the library that burns, the Lord of the Tombs whose hall must be
lit, the seal that quiets the coffins, the gravekeeper's forebear and his gate, and wax torches.

Run: python test_p11.py   (exits non-zero on failure)
"""

import json
import math

import pyxel

import lang
import save
from camp import CampScreen
from enemies import Lord, Moth
from objects import cell_center
from palette import PALETTE
from sound import NullSfx
from tables import REQUESTS, TUNE
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
party = world.party
camp = CampScreen()


def check(cond, what):
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        raise SystemExit(1)


def tick(n=1):
    for _ in range(n):
        world.update(W // 2, H // 2, False)


def place(cell, yaw=0.0):
    p.x, p.z = cell_center(cell)
    p.yaw = yaw


def torches():
    return [t for m in party.members for t in (m.equip["right"], m.equip["left"]) if t is not None and t.is_torch]


def fixture(cell):
    return world.floor.fixtures[cell]


def said(words):
    return any(words in t for t, _ in world.messages.visible())


def calm():
    """No moths or Lord about, for checks of the coffins alone."""
    world.floor.enemies[:] = [e for e in world.floor.enemies if not isinstance(e, (Moth, Lord))]


# 1. the floors in order: the catacombs under floor 2, the King's hall below them
check(world.get_floor("floor2").d.below == "floor3" and world.get_floor("floor3").d.below == "floor4",
      "floor 2 -> the catacombs (3) -> the King's hall (4)")
world.descend("floor3")  # (the developer's way in; the gate is not open yet)
tick(40)
fl = world.floor
check(any(isinstance(e, Moth) for e in fl.enemies) and any(isinstance(e, Lord) for e in fl.enemies),
      "moths and the Lord of the Tombs are here")
calm()

# 2. coffins open only in the dark, and not near a burning sconce
place((6, 2), 90)
tick(20)
check(not fixture((5, 1)).open, "with a torch burning, the coffins stay shut")
for t in torches():
    t.out = True
check(party.light == 0, "the torch put out: the party is in the dark")
before = len(fl.enemies)
tick(20)
check(any(fixture(c).open for c in ((5, 1), (5, 3), (7, 1), (7, 3))) and len(fl.enemies) > before,
      "in the dark, a coffin opens and its dead climb out")
check(said("coffin lid"), "the player is told")
calm()
fl.enemies[:] = [e for e in fl.enemies if not getattr(e, "risen", False)]
check(not fl.near_flame((9, 3), TUNE["sconce_reach"]), "the gallery's sconce is cold")

# 3. sconces: light one from a torch, light a torch from one
sconce = fixture((9, 1))
world._use_sconce(sconce)
check(not sconce.lit and said("No flame"), "no flame to light it with")
entry = fixture((2, 0))
check(entry.lit, "the entrance sconce burns from the start")
world._use_sconce(entry)
check(all(not t.out for t in torches()), "a torch lit again at the burning sconce")
world._use_sconce(sconce)
check(sconce.lit, "the gallery sconce lit from the torch")
for fx in fl.fixtures.values():
    if fx.kind == "coffin":
        fx.open = False
for t in torches():
    t.out = True
place((9, 2), 90)
tick(30)
check(not any(fixture(c).open for c in ((7, 1), (7, 3), (9, 3), (11, 1), (11, 3))),
      "in the dark but by a burning sconce: the coffins near it stay shut")
for t in torches():
    t.out = False

# 4. moths fly to a flame and put it out
place((5, 2), 90)
party.mage.cooldown = 10 ** 6  # Mira holds her bolts (she would shoot the moths down)
moth = Moth(*cell_center((10, 2)))
fl._add_enemy(moth)
moth._set("chase")
for _ in range(200):
    tick()
    if not sconce.lit:
        break
check(not sconce.lit, "a moth swarm put out the gallery sconce")
for _ in range(900):
    tick()
    if party.light == 0:
        break
check(party.light == 0 and said("smother it"), "and then the party's torch")
world._damage_enemy(moth, 5, p.x, p.z)
check(not moth.alive, "a blow scatters it for good")
party.mage.cooldown = 0
for t in torches():
    t.out = False

# 5. the library: too dark to read without a flame; a torch kept there too long sets a shelf alight
shelf = fixture((17, 0))
world.journal.clear()
for t in torches():
    t.out = True
place((17, 1), 0)
world._use_fixture(type("H", (), {"obj": shelf})())
check(said("Too dark") and not world.journal, "too dark to read")
for t in torches():
    t.out = False
world._use_fixture(type("H", (), {"obj": shelf})())
check(("book", "floor3", 17, 0) in world.journal, "a book read by torchlight goes in the journal")
world.pages.clear()
tick(TUNE["library_burn_sec"] * 60 + 60)
check(any(fx.kind == "shelf" and fx.burnt for fx in fl.fixtures.values()) and said("catches fire"),
      "a torch kept in the library too long: a shelf burns")
fl.heat = 0
burnt = sum(fx.burnt for fx in fl.fixtures.values() if fx.kind == "shelf")
for t in torches():
    t.out = True
party.add_ward("light", 10 ** 5, 1)
place((17, 1), 0)
world._use_fixture(type("H", (), {"obj": fixture((19, 0))})())
check(("book", "floor3", 19, 0) in world.journal, "a Light ward is enough to read by")
tick(TUNE["library_burn_sec"] * 60 + 60)
check(sum(fx.burnt for fx in fl.fixtures.values() if fx.kind == "shelf") == burnt and fl.heat == 0,
      "but it is no flame: the books do not burn")
check(party.light > 0 and party.flame == 0, "the party has light, but no flame")
moth = Moth(*cell_center((18, 2)))
check(moth._pick_goal(fl, world) is None or moth._pick_goal(fl, world)[0] != "party", "moths are not drawn to a Light ward")
party.wards.pop("light")
for t in torches():
    t.out = False
place((14, 9), 180)
tick(2)

# 6. the Lord of the Tombs: blades bite as far as its hall is lit
fl.respawn(0, [])
fl.enemies[:] = [e for e in fl.enemies if isinstance(e, Lord)]
lord = next(e for e in fl.enemies if isinstance(e, Lord))
check(len(lord.sconces) == 4 and lord.lit() == 0, "four sconces in its hall, all cold")
hp = lord.hp
world._damage_enemy(lord, 20, p.x, p.z)
check(lord.hp == hp and said("like smoke"), "with no sconce burning, the blow passes through")
lord.sconces[0].lit = lord.sconces[1].lit = True
world._damage_enemy(lord, 20, p.x, p.z)
check(lord.hp == hp - 10, "two of four burning: half the blow lands")
for sc in lord.sconces:
    sc.lit = True
lord._set("chase")
lord.douse_timer = 0
for _ in range(900):
    lord.update(fl, world)
    if lord.lit() < 4:
        break
check(lord.lit() == 3 and said("puts out a sconce"), "the Lord walks to a sconce and puts it out")
world._damage_enemy(lord, 999, p.x, p.z)
for _ in range(50):
    lord.update(fl, world)
check(not lord.alive and said("catacombs grow quiet"), "the Lord falls")
fl.respawn(0, [])
check(not any(isinstance(e, Lord) for e in fl.enemies), "and does not rise on the next delve")

# 7. the seal laid in the catacombs' niche: the coffins sleep
calm()
for t in torches():
    t.out = True
for fx in fl.fixtures.values():
    if fx.kind == "coffin":
        fx.open = False
    if fx.kind == "sconce":
        fx.lit = False
world.back = None
world.hand = Thing("relic_seal")
niche = fixture((0, 9))
place((1, 9), 270)
world._use_fixture(type("H", (), {"obj": niche})())
check(fl.sealed, "the seal laid in the niche")
place((5, 9), 90)
tick(40)
check(not any(fx.open for fx in fl.fixtures.values() if fx.kind == "coffin"), "in the dark, the sealed coffins stay shut")
for t in torches():
    t.out = False

# 8. the gravekeeper's forebear: brought home, he opens the gate to the catacombs
check(REQUESTS["ancestor"]["item"] == "remains_ancestor", "the request is on the board")
world.quests["ancestor"] = "accepted"
world._take(next(it for it in fl.items if it.kind == "remains_ancestor"))
check(world.back is not None and world.back.kind == "remains_ancestor", "his bones ride on Arn's back")
world.arrive_surface()
check(world.quests["ancestor"] == "done" and "floor3" in world.shortcuts, "handed over: the gate is open")
check(any("old gate" in line for _, line in world.report), "the report says so")
world.report = None
camp.show("down")
gate = next(r for r in camp.rows(world) if "gate" in r.label)
gate.action(world)
check(world.floor.name == "floor3" and p.cell == world.floor.d.gate[0], "down through the gate into the catacombs")
tick(40)

# 9. corpse wax: the smith makes wax torches, again and again
world.party.fighter.give(Thing("corpse_wax"))
world.party.fighter.give(Thing("corpse_wax"))
world.arrive_surface()
world.report = None
check(world.store.get("corpse_wax") == 2, "the wax goes into the camp store")
world.coins = 100
camp.show("smith")
for _ in range(2):
    next(r for r in camp.rows(world) if r.label == "a wax torch").action(world)
waxed = [t for m in party.members for t in m.pack if t is not None and t.kind == "wax_torch"]
check(len(waxed) == 2 and world.store["corpse_wax"] == 0, "two wax torches made, into the packs")
check(waxed[0].fuel > Thing("torch").fuel and waxed[0].light > 0, "a wax torch burns longer, and gives light")

# 10. stairs lead to the matching stairs, though the maps do not line up
world.floor = world.get_floor("floor2")
p.solid = world.floor.solid
place(next(world.floor.d.cells_of("X")), 0)
world.arrived_on = None
for _ in range(200):
    tick()
    if world.travel is None and world.floor.name == "floor3":
        break
check(world.floor.name == "floor3" and p.cell == next(world.floor.d.cells_of("U")), "down from floor 2: on the catacombs' stairs up")
p.x += 1
world.arrived_on = None
for _ in range(200):
    tick()
    if world.travel is None and world.floor.name == "floor2":
        break
check(world.floor.name == "floor2" and p.cell == next(world.floor.d.cells_of("X")), "and back up: on floor 2's stairs down")
for name, ch in (("floor3", "X"), ("floor4", "U")):
    d = world.get_floor(name).d
    check(not d.is_wall(*next(d.cells_of(ch))), f"{name}'s {ch} is open floor")

# 11. fire magic lights sconces (and burns shelves), and a fire ward lights torches again
world.descend("floor3")
tick(80)
fl = world.floor
fl.enemies.clear()
mage = world.party.leader
def ready():
    mage.mana, mage.cooldown = 99, 0
gallery = fixture((9, 1))
gallery.lit = False
place((9, 2), 0)
ready()
check(world.cast((1, "fire", "burst")) == "cast" and gallery.lit and said("fire catches"), "a fire burst lights the sconce beside it")
gallery.lit = False
place((9, 2), 0)
p.z += 20
ready()
world.cast((1, "fire", "bolt"))
tick(40)
check(gallery.lit, "a fire bolt at a cold sconce lights it")
for t in torches():
    t.out = True
ready()
world.cast((1, "fire", "ward"))
check(all(not t.out for t in torches()) and said("lights the torch again"), "a fire ward lights the torches again")
shelf = fixture((19, 0))
place((19, 1), 0)
ready()
world.cast((1, "fire", "bolt"))
tick(40)
check(shelf.burnt, "a fire bolt at a shelf burns its books")

# 12. saving: burning sconces, burnt shelves, a torch put out; and an older save's floor 3 is floor 4 now
world.descend("floor3")
tick(5)
fixture((9, 1)).lit = True
torches()[0].out = True
data = json.loads(json.dumps(save.dump(world)))
other = World(atlas, W, H, NullSfx(), start="camp")
save.restore(other, data)
f3 = other.floors["floor3"]
def lit(floor):
    return {c for c, fx in floor.fixtures.items() if fx.kind == "sconce" and fx.lit}


check(f3.fixtures[(9, 1)].lit and lit(f3) == lit(world.floors["floor3"]), "the sconces come back as they were")
check(any(fx.kind == "shelf" and fx.burnt for fx in f3.fixtures.values()), "a burnt shelf stays burnt")
check(any(t.out for m in other.party.members for t in m.equip.values() if t is not None), "a torch put out stays out")
old = json.loads(json.dumps(data))
old.pop("layout")
old["floors"] = {"floor3": old["floors"].pop("floor4", dict(items=[], doors={}, switches={}, broken=[]))}
old["shortcuts"] = ["floor3"]
old["relic_log"] = [["relic_heart", "bury", "floor3"]]
older = World(atlas, W, H, NullSfx(), start="camp")
save.restore(older, old)
check(older.shortcuts == ["floor4"] and older.relic_log == [("relic_heart", "bury", "floor4")],
      "an older save: its floor 3 (the King's hall) is floor 4 now")

print("all checks passed")
