"""Saving and loading the game, done on its own: when the party leaves the camp and when it gets back.

The file is JSON with a version number, so that later versions can read
(or knowingly refuse) older saves. What is kept:
  the party (stats, skills, belongings, hunger), coins, requests, the
  relics' fates, who has heard what, the journal, the opened shafts, and
  for every floor visited: what lies on it, its doors and levers, the
  guardians broken for good, and the cells explored.
Enemies are not kept: the dead rise again on every delve.
"""

import json
import os

import pyxel

from objects import Item
from things import Thing

VERSION = 1
MEMBER_KEYS = ("stats", "hp", "stamina", "mana", "level", "xp", "food", "water")


def path():
    try:
        folder = pyxel.user_data_dir("ryohji", "pyxel-dungeon")
    except Exception:  # no user folder (or pyxel not started): keep it beside the game
        folder = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(folder, "save.json")


# ---------------------------------------------------------------- things
def thing_out(t):
    return None if t is None else {"kind": t.kind, "charges": t.charges, "fuel": t.fuel, "lost": t.lost}


def thing_in(d):
    if d is None:
        return None
    t = Thing(d["kind"], d["charges"], d["fuel"])
    t.lost = d.get("lost", False)
    return t


def cell_key(c):
    return f"{c[0]},{c[1]}"


def cell_of_key(k):
    x, y = k.split(",")
    return int(x), int(y)


# ---------------------------------------------------------------- the world
def dump(world):
    party = []
    for m in world.party.members:
        d = {k: getattr(m, k) for k in MEMBER_KEYS}
        d["equip"] = {slot: thing_out(t) for slot, t in m.equip.items()}
        d["pack"] = [thing_out(t) for t in m.pack]
        party.append(d)
    floors = {}
    for name, fl in world.floors.items():
        floors[name] = {
            "items": [dict(thing_out(it.thing), x=it.x, z=it.z, yaw=it.yaw) for it in fl.items if not it.moving],
            "doors": {cell_key(c): [door.target_open, door.lock] for c, door in fl.doors.items()},
            "switches": {cell_key(c): sw.on for c, sw in fl.switches.items()},
            "broken": sorted(fl.broken | {e.slot for e in fl.enemies if not e.alive and getattr(e, "slot", None) is not None}),
        }
    return {
        "version": VERSION,
        "party": party,
        "hand": thing_out(world.hand),
        "back": thing_out(world.back),
        "coins": world.coins,
        "quests": world.quests,
        "relic_log": [list(r) for r in world.relic_log],
        "heard": world.heard,
        "seen": sorted(world.seen),
        "journal": [list(e) for e in world.journal],
        "ending": world.ending,
        "shortcuts": world.shortcuts,
        "explored": {name: sorted(cell_key(c) for c in cells) for name, cells in world.explored.items()},
        "floors": floors,
    }


def restore(world, data):
    """Put a saved game into a fresh world (made with start="camp")."""
    if data.get("version") != VERSION:
        raise ValueError(f"save version {data.get('version')} is not {VERSION}")
    for m, d in zip(world.party.members, data["party"]):
        for k in MEMBER_KEYS:
            setattr(m, k, d[k])
        m.equip = {slot: thing_in(t) for slot, t in d["equip"].items()}
        m.pack = [thing_in(t) for t in d["pack"]]
    world.hand = thing_in(data["hand"])
    world.back = thing_in(data["back"])
    world.coins = data["coins"]
    world.quests = dict(data["quests"])
    world.relic_log = [tuple(r) for r in data["relic_log"]]
    world.heard = dict(data["heard"])
    world.seen = set(data["seen"])
    world.journal = [tuple(e) for e in data["journal"]]
    world.ending = data["ending"]
    world.shortcuts = list(data["shortcuts"])
    world.explored = {name: {cell_of_key(k) for k in cells} for name, cells in data["explored"].items()}
    world.floors.clear()
    for name, saved in data["floors"].items():
        fl = world.get_floor(name)
        fl.broken = set(saved["broken"])
        fl.respawn(len(world.restored), world.buried)
        for it in list(fl.items):
            fl.remove_item(it)
        for d in saved["items"]:
            fl.add_item(Item(thing_in(d), d["x"], d["z"], yaw=d["yaw"]))
        for k, (target_open, lock) in saved["doors"].items():
            door = fl.doors[cell_of_key(k)]
            door.target_open, door.lock = target_open, lock
            door.open = 1.0 if target_open else 0.0
            door.node.refresh()
        for k, on in saved["switches"].items():
            fl.switches[cell_of_key(k)].on = on
    world.floor = world.get_floor("floor1")
    world.player.solid = world.floor.solid
    world.surface = True
    world.delve = dict(log=len(world.relic_log), coins=world.coins, opened=None)


def write(world, file=None):
    file = file or path()
    tmp = file + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(dump(world), f, ensure_ascii=False)
    os.replace(tmp, file)  # never leave a half-written save behind


def read(file=None):
    """The saved game, or None when there is none (or it cannot be read)."""
    file = file or path()
    try:
        with open(file, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None
