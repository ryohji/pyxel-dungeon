"""Headless checks of P6 so far: the camp, requests, notes, carrying on the back, delivering, buying.

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


# 1. the game starts in the camp, which is lit without a torch
check(world.floor.name == "camp", "starting in the camp")
party.mage.equip["left"] = None
tick()
check(world.floor.view.dark == 0, "the camp is lit")

# 2. the board: Tab finds it, Space opens it, a request is taken
place((5, 1), 0, 10)
tick(tab=True)
check(world.target is not None and world.target.kind == "board", "Tab chose the board")
tick(attack_key=True)
check(world.screen == "board", "Space opened the board")
camp.show(world.screen)
world.screen = None
row("The miller's ring").action(world)
check(world.quests == {"ring": "accepted"}, "took the miller's request")
check(row("The miller's ring").action is None, "a taken request cannot be taken twice")

# 3. down the stairs into the cellar
place((2, 1), 270)
p.x -= 100
for _ in range(120):
    tick()
    if world.travel is None and world.floor.name == "floor1":
        break
check(world.floor.name == "floor1" and p.cell == (1, 1), "down the camp stairs to floor 1")

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

# 6. a wipe restores what was carried, the coins and the requests
world._remember_entry()
back, coins = world.back, world.coins
world.back, world.coins, world.quests = None, 0, {}
world._restart_floor()
check(world.back is not None and world.back.kind == back.kind and world.coins == coins
      and world.quests.get("lantern") == "accepted", "a restart brings back the load, coins and requests")

# 7. the counter: hand over, get paid; nothing for what was not asked
world.floor = world.get_floor("camp")
camp.show("counter")
labels = [r.label for r in camp.rows(world)]
check("The miller's ring" in labels and "The stone idol" not in labels, "the counter lists only taken requests")
before = world.coins
row("The miller's ring").action(world)
check(world.coins == before + REQUESTS["ring"]["reward"] and world.quests["ring"] == "done", "paid for the ring")
check(not any(t is not None and t.kind == "ring" for t in arn.pack), "the ring was handed over")
check("coins" in sfx.played, "coins clinked")
check(row("Holt's lantern").action is None, "the lantern is not carried yet")
camp.show("board")
row("The stone idol").action(world)
camp.show("counter")
row("The stone idol").action(world)
check(world.back is None and world.quests["idol"] == "done", "the idol was delivered off Arn's back")

# 8. buying supplies
torch_price = next(r["price"] for r in SHOP if r["kind"] == "torch")
coins = world.coins
packs = sum(t is not None for m in party.members for t in m.pack)
row("Buy a torch").action(world)
check(world.coins == coins - torch_price, "paid for a torch")
check(sum(t is not None for m in party.members for t in m.pack) == packs + 1, "the torch went into a pack")
world.coins = 0
check(not row("Buy a torch").enabled, "cannot buy without coins")

print("all checks passed")
