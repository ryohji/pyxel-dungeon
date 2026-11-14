"""Game numbers that are meant to be tuned, read from the CSV files in data/.

  members.csv  starting stats and skill levels of each party member
  skills.csv   for each skill and level: total xp needed, and the stats gained
  items.csv    what each kind of item is and does
  kit.csv      what each member starts with (slot: right, left, head, body, pack)
  spells.csv   the 16 rune spells (element x shape)
  requests.csv errands to bring things back: from the camp board, or from notes
  shop.csv     what the camp counter sells
  relics.csv   the five relics of the old kingdom: lore, and the camp's reactions
  lines.csv    other lines of story text (introductions, endings)
  enemies.csv  each kind of enemy: health, speed, reach, timing, damage
  tuning.csv   single numbers: hunger, stamina, damage bonuses, xp awards, ...

Edit the CSVs and restart the game, or press F5 in debug mode (F) to
reload them while it runs; no code changes needed.
"""

import csv
import os

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
STATS = ("hp", "stamina", "mana", "str", "dex", "wis", "vit")
SKILLS = ("fighter", "ninja", "priest", "wizard")


def _num(s):
    try:
        return int(s)
    except ValueError:
        try:
            return float(s)
        except ValueError:
            return s


def rows(name):
    with open(os.path.join(DATA, name), newline="", encoding="utf-8") as f:
        return [{k: _num(v.strip()) for k, v in row.items()} for row in csv.DictReader(f)]


MEMBERS = {r["name"]: r for r in rows("members.csv")}
ITEMS = {r["kind"]: r for r in rows("items.csv")}
KIT = rows("kit.csv")
TUNE = {r["key"]: r["value"] for r in rows("tuning.csv")}

# skill -> sorted [(level, xp needed, {stat: gain})]
LEVELS = {s: [] for s in SKILLS}
for r in rows("skills.csv"):
    LEVELS[r["skill"]].append((r["level"], r["xp"], {k: r[k] for k in STATS}))
for table in LEVELS.values():
    table.sort()


def xp_for(skill, level):
    """Total xp needed to reach level (0 for level 1 and below)."""
    for lv, xp, _ in LEVELS[skill]:
        if lv == level:
            return xp
    return 0

REQUESTS = {r["id"]: r for r in rows("requests.csv")}  # source: board, or note (found in the dungeon)
SHOP = rows("shop.csv")


def note_kind(request_id):
    """The item kind of the note that hands out a request found in the dungeon."""
    return "note_" + request_id

RELICS = {r["kind"]: r for r in rows("relics.csv")}  # lore, and what the two at the camp say about each
LINES = {r["key"]: r for r in rows("lines.csv")}


def story(key):
    """A line of story text from lines.csv, in the language in use."""
    from lang import loc
    return loc(LINES[key], "text")
ENEMIES = {r["kind"]: r for r in rows("enemies.csv")}


def reload():
    """Read every CSV again, updating the tables in place so modules holding them see the new numbers."""
    MEMBERS.clear(); MEMBERS.update({r["name"]: r for r in rows("members.csv")})
    ITEMS.clear(); ITEMS.update({r["kind"]: r for r in rows("items.csv")})
    KIT[:] = rows("kit.csv")
    TUNE.clear(); TUNE.update({r["key"]: r["value"] for r in rows("tuning.csv")})
    for table in LEVELS.values():
        table.clear()
    for r in rows("skills.csv"):
        LEVELS[r["skill"]].append((r["level"], r["xp"], {k: r[k] for k in STATS}))
    for table in LEVELS.values():
        table.sort()
    REQUESTS.clear(); REQUESTS.update({r["id"]: r for r in rows("requests.csv")})
    SHOP[:] = rows("shop.csv")
    RELICS.clear(); RELICS.update({r["kind"]: r for r in rows("relics.csv")})
    LINES.clear(); LINES.update({r["key"]: r for r in rows("lines.csv")})
    ENEMIES.clear(); ENEMIES.update({r["kind"]: r for r in rows("enemies.csv")})
