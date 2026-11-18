"""Saving and loading the game, done on its own: when the party leaves the camp and when it gets back.

The file is JSON with a version number, so that later versions can read
(or knowingly refuse) older saves. What is kept:
  the party (stats, skills, belongings, hunger), coins, requests, the
  relics' fates, who has heard what, the journal, the opened shafts, the
  weapon rack and the heavy blows learned, and
  for every floor visited: what lies on it, its doors and levers, the
  guardians broken for good, and the cells explored.
Enemies are not kept: the dead rise again on every delve.
"""

import json
import os
import time

import pyxel

from objects import Item, cell_center
from tables import HABIT_TOP, REQUESTS, note_kind
from things import Thing

VERSION = 1
LAYOUT = 2  # the maps' order: 2 put the catacombs on floor 3 and moved the King's hall to floor 4
MEMBER_KEYS = ("stats", "hp", "stamina", "mana", "level", "xp", "food", "water")


SLOTS = 3


def folder():
    try:
        return pyxel.user_data_dir("ryohji", "pyxel-dungeon")
    except Exception:  # no user folder (or pyxel not started): keep it beside the game
        return os.path.dirname(os.path.abspath(__file__))


def path(slot=1, where=None):
    """The file of a save slot (1..SLOTS)."""
    return os.path.join(where or folder(), f"save{slot}.json")


def migrate(where=None):
    """A save from before the slots (save.json) becomes slot 1."""
    where = where or folder()
    old = os.path.join(where, "save.json")
    if os.path.exists(old) and not os.path.exists(path(1, where)):
        try:
            os.replace(old, path(1, where))
        except OSError as e:
            print("could not move the old save:", e)


def delete(slot, where=None):
    try:
        os.remove(path(slot, where))
    except OSError:
        pass


def summary(data):
    """What a slot's save shows on the slot screen: deepest floor, coins, requests done, when saved."""
    explored = data.get("explored", {})
    if data.get("layout", 1) < 2 and "floor3" in explored:  # a save from before the catacombs
        explored = {("floor4" if k == "floor3" else k): v for k, v in explored.items()}
    floors = [int(name[5:]) for name, cells in explored.items() if cells and name[5:].isdigit()]
    return dict(floor=max(floors, default=0), coins=data.get("coins", 0),
                done=sum(state == "done" for state in data.get("quests", {}).values()),
                relics=len(data.get("relic_log", [])), saved=data.get("saved", ""))


# ---------------------------------------------------------------- things
def thing_out(t):
    return None if t is None else {"kind": t.kind, "charges": t.charges, "fuel": t.fuel, "lost": t.lost, "out": t.out}


def thing_in(d):
    if d is None:
        return None
    t = Thing(d["kind"], d["charges"], d["fuel"])
    t.lost = d.get("lost", False)
    t.out = d.get("out", False)
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
            "sconces": sorted(cell_key(fx.cell) for fx in fl.fixtures.values() if fx.kind == "sconce" and fx.lit),
            "burnt": sorted(cell_key(fx.cell) for fx in fl.fixtures.values() if fx.kind == "shelf" and fx.burnt),
            "placed": [[kind, x, y] for (x, y), kind in fl.d.items],  # the map's own items, as the map was then
            "broken": sorted(fl.broken | {e.slot for e in fl.enemies if not e.alive and getattr(e, "slot", None) is not None}),
        }
    return {
        "version": VERSION,
        "layout": LAYOUT,
        "saved": time.strftime("%Y-%m-%d %H:%M"),
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
        "armory": world.armory,
        "store": world.store,
        "techniques": sorted(world.techniques),
        "explored": {name: sorted(cell_key(c) for c in cells) for name, cells in world.explored.items()},
        "floors": floors,
    }


def restore(world, data):
    """Put a saved game into a fresh world (made with start="camp")."""
    if data.get("version") != VERSION:
        raise ValueError(f"save version {data.get('version')} is not {VERSION}")
    if data.get("layout", 1) < 2:
        data = moved_floor3(data)
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
    world.armory = list(data.get("armory", ["spear"]))  # saves from before P10 had no rack
    world.techniques = set(data.get("techniques", []))
    world.store = dict(data.get("store", {}))
    for m in world.party.members:  # skills now stop at HABIT_TOP
        m.level = {s: min(lv, HABIT_TOP) for s, lv in m.level.items()}
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
        for item in new_on_map(fl, saved.get("placed"), data):
            fl.add_item(item)
        for k, (target_open, lock) in saved["doors"].items():
            door = fl.doors[cell_of_key(k)]
            door.target_open, door.lock = target_open, lock
            door.open = 1.0 if target_open else 0.0
            door.node.refresh()
        for k, on in saved["switches"].items():
            fl.switches[cell_of_key(k)].on = on
        if "sconces" in saved:
            for fx in fl.fixtures.values():
                if fx.kind == "sconce":
                    fx.lit = cell_key(fx.cell) in saved["sconces"]
        for k in saved.get("burnt", []):
            fl.fixtures[cell_of_key(k)].burnt = True
    world.floor = world.get_floor("floor1")
    world.player.solid = world.floor.solid
    world.surface = True
    world.delve = dict(log=len(world.relic_log), coins=world.coins, opened=None)


def moved_floor3(data):
    """A save from before the catacombs: what it called floor 3 (the King's hall) is floor 4 now."""
    def rename(name):
        return "floor4" if name == "floor3" else name
    data = dict(data)
    data["floors"] = {rename(k): v for k, v in data["floors"].items()}
    data["explored"] = {rename(k): v for k, v in data["explored"].items()}
    data["shortcuts"] = [rename(n) for n in data["shortcuts"]]
    data["relic_log"] = [[k, how, rename(where)] for k, how, where in data["relic_log"]]
    data["journal"] = [[e[0], rename(e[1]), *e[2:]] if e[0] == "carving" else e for e in data["journal"]]
    return data


def new_on_map(fl, placed, data):
    """Items the map has gained since the game was saved (a later version of the game added them)."""
    if placed is not None:
        old = {(kind, x, y) for kind, x, y in placed}
        fresh = [(cell, kind) for cell, kind in fl.d.items if (kind, *cell) not in old]
    else:  # a save from before maps were remembered: add only kinds the saved game has never seen
        fresh = [(cell, kind) for cell, kind in fl.d.items if kind not in kinds_known(data)]
    return [Item(kind, *cell_center(cell)) for cell, kind in fresh]


def kinds_known(data):
    """Every kind of thing a saved game mentions: lying anywhere, carried, delivered, or settled."""
    things = [data["hand"], data["back"]]
    for m in data["party"]:
        things += list(m["equip"].values()) + m["pack"]
    for saved in data["floors"].values():
        things += saved["items"]
    known = {t["kind"] for t in things if t is not None}
    known |= {REQUESTS[rid]["item"] for rid in data["quests"] if rid in REQUESTS}
    known |= {note_kind(rid) for rid in data["quests"]}
    known |= {r[0] for r in data["relic_log"]}
    if data.get("techniques"):
        known.add("drill_book")  # read and learned
    return known


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
