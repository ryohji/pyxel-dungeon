"""Headless checks of P4: stats from the CSVs, growth, needs, light, inventory, Tab targets.

Run: python test_p4.py   (exits non-zero on failure)
"""

import pyxel
from pyxel.cube import Vec3

from inventory import Inventory
from objects import Item, cell_center
from palette import PALETTE
from sound import NullSfx
from tables import LEVELS, MEMBERS, TUNE
from textures import make_atlas, make_icons
from things import Thing
from view import MAX_DARK
from world import FALL_FRAMES, STAIRS_HOLD, World

import lang

lang.current[0] = "en"  # these checks read the English lines
W, H = 320, 240
pyxel.init(W, H)
pyxel.colors[:] = PALETTE
sfx = NullSfx()
world = World(make_atlas(), W, H, sfx, peaceful=True)
p = world.player
party = world.party
arn, mira = party.fighter, party.mage


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


# 1. stats and starting kit come from the CSVs
check(arn.max_hp == MEMBERS["Arn"]["hp"] and arn.stats["str"] == MEMBERS["Arn"]["str"], "Arn's stats from members.csv")
check(arn.equip["right"].kind == "sword" and mira.equip["left"].kind == "torch", "starting kit from kit.csv")
check(arn.defense == 2, f"the jerkin gives armor (defense {arn.defense})")

# 2. experience raises a skill level and the stats it grants
lv, need, gains = next(t for t in LEVELS["fighter"] if t[0] == arn.level["fighter"] + 1)
hp0, str0 = arn.max_hp, arn.stats["str"]
world.award(arn, "fighter", need)
check(arn.level["fighter"] == lv, f"fighter level {lv} reached")
check(arn.max_hp == hp0 + gains["hp"] and arn.stats["str"] == str0 + gains["str"], "stats grew as skills.csv says")
check("levelup" in sfx.played and any("level" in t for t, _ in world.messages.visible()), "level-up announced")

# 3. armor softens blows
hp = arn.hp
world.hit_party(5, None)
check(arn.hp == hp - (5 - arn.defense), f"a 5-point blow did {hp - arn.hp}")
arn.hp = arn.max_hp

# 4. hunger and thirst drain; eating and drinking from the inventory
place((3, 3), 180)
food0, water0 = arn.food, arn.water
tick(3600)  # one minute
check(abs((food0 - arn.food) - TUNE["food_per_min"]) < 0.01, f"food fell {food0 - arn.food:.2f} in a minute")
check(abs((water0 - arn.water) - TUNE["water_per_min"]) < 0.01, f"water fell {water0 - arn.water:.2f} in a minute")
inv = Inventory(make_icons())
slots = inv.slots(party)
bread = next(s for s in slots if s.member is arn and s.thing is not None and s.thing.kind == "bread")
mouth = next(s for s in slots if s.member is arn and s.area == "mouth")
inv.use(world, bread)
check(world.hand.kind == "bread" and bread.thing is None, "took the bread out of the pack")
arn.food = 30
inv.use(world, mouth)
check(arn.food == 30 + 40 and world.hand is None and "eat" in sfx.played, "Arn ate the bread")
skin = next(s for s in slots if s.member is arn and s.thing is not None and s.thing.kind == "waterskin")
inv.use(world, skin)
arn.water = 10
inv.use(world, mouth)
check(arn.water == 45 and world.hand.charges == 2, f"drank from the waterskin (charges {world.hand.charges})")
helm = Thing("cap")
held = world.hand
world.hand = helm
inv.use(world, next(s for s in slots if s.member is arn and s.area == "equip" and s.key == "right"))
check(world.hand is helm and arn.equip["right"].kind == "sword", "a cap does not go in the hand")
inv.use(world, next(s for s in slots if s.member is arn and s.area == "equip" and s.key == "head"))
check(arn.equip["head"] is helm and arn.defense == 3, "the cap goes on the head")
world.hand = held

# 5. a fountain refills the waterskin and quenches thirst
place((5, 14), 180, -20)
x, z = cell_center((5, 14))
hit = world.pick(*world.project(Vec3(x, 25, z + 52)))
check(hit.kind == "fountain", f"pointing at the fountain (got {hit.kind})")
world.click(hit)
check(world.hand.charges == 3, "filled the waterskin")
arn.give(world.hand)
world.hand = None
mira.water = 5
world.click(hit)
check(mira.water == 100 and arn.water == 100, "drank from the fountain")

# 6. the torch burns down and the dark closes in
torch = mira.equip["left"]
tick()
check(world.floor.view.dark == 0, "full light with a fresh torch")
torch.fuel = 1
tick(2)
check(torch.fuel == 0 and world.floor.view.dark == MAX_DARK, "darkness when the torch burns out")
mira.equip["left"] = Thing("torch")
tick()
check(world.floor.view.dark == 0, "a new torch lights the way")

# 7. worn out: no running
arn.stamina = 0
check(not p.can_run(), "too tired to run")
arn.stamina = arn.max_stamina
check(p.can_run(), "rested enough to run")

# 8. Tab picks a target, Space acts on it; the mouse takes over when it moves
place((5, 3), 90)
fl = world.floor
lever = fl.switches[(6, 3)]
tick(tab=True)
check(world.mode == "keys" and world.target is not None and world.target.kind == "switch",
      f"Tab chose the lever (got {world.target and world.target.kind})")
tick(attack_key=True)
check(lever.on, "Space pulled the lever")
place((3, 2), 0)
for it in list(fl.items):
    if it.cell == (3, 1):
        fl.remove_item(it)
x, z = cell_center((3, 1))
left, right = Item("bread", x - 30, z), Item("rock", x + 30, z)
fl.add_item(left)
fl.add_item(right)
tick(tab=True)
first = world.target.obj
tick(tab=True)
second = world.target.obj
tick(tab=True)
check({first, second} == {left, right} and world.target.obj is first, "Tab cycles through the targets")
tick(attack_key=True)
check(world.hand is not None and world.hand.kind == first.kind, f"Space took {first.kind}")
world.update(10, 10, False, mouse_moved=True)
check(world.mode == "mouse" and world.target is world.hover, "moving the mouse takes the target back")
world.update(W // 2, H // 2, False, tab=True)
check(world.mode == "keys", "Tab takes it again")
tick(attack_key=True)
check(world.hand is None, "Space with an item in hand acted on the target (put down / swapped)")

# 9. the stairs take a walking pace
place((20, 3), 0)
p.z -= 100
sfx.played.clear()
frames = 0
while world.travel is None and frames < 200:
    tick()
    frames += 1
check(world.travel is not None and "stairs_down" in sfx.played, "on the stairs")
frames = 0
while world.travel is not None:
    tick()
    frames += 1
check(frames == FALL_FRAMES * 2 + STAIRS_HOLD, f"stairs took {frames} frames ({frames / 60:.2f} s)")

print("all checks passed")
