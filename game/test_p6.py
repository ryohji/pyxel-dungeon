"""Headless checks of P6: the requests before going down, notes, carrying on the back, delivering on return, buying.

Run: python test_p6.py   (exits non-zero on failure)
"""

import pyxel
from pyxel.cube import Vec3

from camp import CampScreen
from objects import cell_center
from palette import PALETTE
from sound import NullSfx
from tables import REQUESTS, SHOP, TUNE
from textures import make_atlas
from world import World

import lang

lang.current[0] = "en"  # these checks read the English lines
W, H = 320, 240
pyxel.init(W, H)
pyxel.colors[:] = PALETTE
sfx = NullSfx()
world = World(make_atlas(), W, H, sfx, start="camp")
p = world.player
party = world.party
arn = party.fighter
camp = CampScreen()


def check(cond, what):
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        raise SystemExit(1)


def place(cell, yaw, pitch=0.0):
    x, z = cell_center(cell)
    p.x, p.z, p.yaw, p.pitch = x, z, yaw, pitch


def tick(n=1, **keys):
    for _ in range(n):
        world.update(W // 2, H // 2, False, **keys)


def row(title):
    return next(r for r in camp.rows(world) if r.label == title)


def take(kind):
    """Pick up the item of this kind lying on the current floor."""
    it = next(i for i in world.floor.items if i.kind == kind)
    world._take(it)


# 1. the game starts at the camp
check(world.surface, "starting at the camp")

# 2. before going down: the requests are listed; one is taken, one taken and let go
camp.show("down")
labels = [r.label for r in camp.rows(world)]
check("The miller's ring" in labels and "Holt's lantern" not in labels, "the board's requests are listed, not the notes'")
row("The miller's ring").action(world)
check(world.quests == {"ring": "accepted"}, "took the miller's request")
check(row("* The miller's ring").right == "taken", "a taken request shows as taken")
row("The stone idol").action(world)
row("* The stone idol").action(world)
check("idol" not in world.quests, "a request taken by mistake can be let go")

# 3. down the stairs into the cellar
next(r for r in camp.rows(world) if r.first).action(world)
check(not camp.open, "going down closes the screen")
tick(40)
check(not world.surface and world.floor.name == "floor1" and p.cell == (1, 1) and world.travel is None,
      "down the camp stairs to floor 1")

# 4. a small find and a note with a request
take("ring")
check(world.hand is not None and world.hand.kind == "ring", "picked up the ring")
arn.give(world.hand)
world.hand = None
take("note_lantern")
check(world.quests.get("lantern") == "accepted" and world.hand is None, "the note gave a request")

# 5. carrying the idol on the back
take("idol")
check(world.back is not None and world.back.kind == "idol", "the idol rides on Arn's back")
check(not p.can_run() and p.speed_scale() == TUNE["carry_speed"], "no running, slower walking")
place((24, 13), 0)
x, z = cell_center((24, 13))
hit = world.pick(*world.project(Vec3(x, 0, z - 60)))
check(hit.kind == "floor" and world.action_name(hit) == "set down load", "pointing at the floor offers to set it down")
world.click(hit)
check(world.back is None and any(i.kind == "idol" for i in world.floor.items), "set the idol down")
take("idol")
check(world.back is not None, "lifted it again")
check("lift" in sfx.played, "the lift sound played")

# 6. back at the camp: what was asked for is handed over by itself; what was not yet asked for is kept
before = world.coins
world.arrive_surface()
check(world.coins == before + REQUESTS["ring"]["reward"] and world.quests["ring"] == "done", "paid for the ring")
check(not any(t is not None and t.kind == "ring" for t in arn.pack), "the ring was handed over")
check("coins" in sfx.played, "coins clinked")
check(world.back is None and world.store.get("idol") == 1 and world.quests.get("idol") is None,
      "the idol was not asked for yet: kept at the camp")
check(world.quests["lantern"] == "accepted", "the lantern is not carried yet")
world.report = None
camp.show("down")
check("The miller's ring" not in [r.label for r in camp.rows(world)], "a done request is gone from the list")
check(row("* Holt's lantern").action is None, "a note's request cannot be let go")
coins = world.coins
row("The stone idol").action(world)
check(world.quests["idol"] == "done" and world.coins == coins + REQUESTS["idol"]["reward"] and world.store["idol"] == 0,
      "taking the idol's request hands it over at once")

# 7. buying supplies
camp.show("supplies")
torch_price = next(r["price"] for r in SHOP if r["kind"] == "torch")
coins = world.coins
packs = sum(t is not None for m in party.members for t in m.pack)
row("Buy a torch").action(world)
check(world.coins == coins - torch_price, "paid for a torch")
check(sum(t is not None for m in party.members for t in m.pack) == packs + 1, "the torch went into a pack")
world.coins = 0
check(not row("Buy a torch").enabled, "cannot buy without coins")

print("all checks passed")
