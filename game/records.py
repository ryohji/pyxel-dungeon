"""What the party has read, kept as keys so it can be shown again in either language.

An entry is a tuple:
  ("talk", who, line)       what someone at the camp said: line is "intro" or "<relic>:<restore|bury>"
  ("relic", kind)           a relic's lore, read when it was first picked up
  ("carving", floor, x, y)  words cut into a wall
  ("book", floor, x, y)     a book read on a shelf of the catacombs' library
  ("note", request id)      a note found in the dungeon (a request)
  ("line", key)             another line of data/lines.csv (the sealed niche)
  ("end", how)              the ending

The journal sorts them into three books: what people said, the relics,
and the carvings and notes.
"""

import os

import lang
from dungeon import Dungeon
from lang import loc, tr
from objects import person_title
from tables import RELICS, REQUESTS, story

HERE = os.path.dirname(os.path.abspath(__file__))
BOOKS = (("talk", "WHAT PEOPLE SAID"), ("relic", "RELICS"), ("other", "CARVINGS AND NOTES"))
TALKERS = ("scholar", "keeper")  # the order people are listed in
LINE_TITLES = {"niche": "A SEALED NICHE"}
_maps = {}


def book(entry):
    return entry[0] if entry[0] in ("talk", "relic") else "other"


def _carving(floor, x, y):
    if floor not in _maps:
        _maps[floor] = Dungeon.load(os.path.join(HERE, "maps", f"{floor}.txt"), floor)
    d = _maps[floor]
    return (lang.ja() and d.texts_ja.get((x, y))) or d.texts.get((x, y), "")


def page(entry):
    """(title, text) of an entry, in the language in use."""
    cat = entry[0]
    if cat == "talk":
        who, line = entry[1], entry[2]
        if line == "intro":
            return person_title(who).upper(), story(who + "_intro")
        kind, how = line.split(":")
        return person_title(who).upper(), loc(RELICS[kind], f"{who}_{how}")
    if cat == "relic":
        relic = RELICS[entry[1]]
        return loc(relic, "name").upper(), loc(relic, "text")
    if cat == "carving":
        return tr("A CARVING"), _carving(*entry[1:])
    if cat == "book":
        return tr("AN OLD BOOK"), _carving(*entry[1:])
    if cat == "note":
        req = REQUESTS[entry[1]]
        return loc(req, "title").upper(), loc(req, "text")
    if cat == "line":
        return tr(LINE_TITLES.get(entry[1], "A CARVING")), story(entry[1])
    if cat == "end":
        return (tr("THE END") if entry[1] == "bury" else tr("THE HILL WAKES")), story("end_" + entry[1])
    raise ValueError(f"unknown record {entry!r}")


def fate(world, kind):
    """What became of a relic, for the relic book."""
    for k, how, where in world.relic_log:
        if k == kind:
            if how == "restore":
                return tr("Given to Vesk: its power is back in the hill.")
            return tr("Laid to rest on floor {n}.", n=where[5:])
    if world.carried(kind):
        return tr("Carried now. Bring it to the camp.")
    return tr("Left in the dungeon.")


def entries(journal, cat):
    """The entries of one book, in reading order (people's words grouped by who said them)."""
    out = [e for e in journal if book(e) == cat]
    if cat == "talk":
        out.sort(key=lambda e: TALKERS.index(e[1]) if e[1] in TALKERS else len(TALKERS))
    return out
