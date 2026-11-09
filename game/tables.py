"""Game numbers that are meant to be tuned, read from the CSV files in data/.

  members.csv  starting stats and skill levels of each party member
  skills.csv   for each skill and level: total xp needed, and the stats gained
  items.csv    what each kind of item is and does
  kit.csv      what each member starts with (slot: right, left, head, body, pack)
  tuning.csv   single numbers: hunger, stamina, damage bonuses, xp awards, ...

Edit the CSVs and restart the game; no code changes needed.
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
