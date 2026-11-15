"""The camp's screens: the way down, supplies, and Vesk's table.

The way down lists the requests (data/requests.csv) before the party goes
down: take one there, or let it go. Requests also come from notes found in
the dungeon. What was asked for is handed over by itself when the party
gets back (world.arrive_surface). Coins buy supplies (data/shop.csv).
The screens pause the game; Tab picks a row, Space or a click acts on it,
Esc closes.
"""

import pyxel

import lang

from palette import BLACK, FIRE_I, STONE_I, WHITE
from lang import loc, tr
from tables import ITEMS, RECIPES, RELICS, REQUESTS, SHOP, TUNE, WEAPONS
from things import Thing

X0, Y0, PW, PH = 6, 14, 308, 214
LIST_Y = Y0 + 22


def row_h():
    return lang.line(10)


# ---------------------------------------------------------------- errands
def locate(world, kind):
    """Where the party carries a thing of this kind: a (getter, remover) pair, or None."""
    if world.hand is not None and world.hand.kind == kind:
        return world.hand, lambda: setattr(world, "hand", None)
    if world.back is not None and world.back.kind == kind:
        return world.back, lambda: setattr(world, "back", None)
    for m in world.party.members:
        for i, t in enumerate(m.pack):
            if t is not None and t.kind == kind:
                return t, lambda m=m, i=i: m.pack.__setitem__(i, None)
        for slot, t in m.equip.items():
            if t is not None and t.kind == kind:
                return t, lambda m=m, slot=slot: m.equip.__setitem__(slot, None)
    return None


def accept(world, rid):
    if rid not in world.quests:
        world.quests[rid] = "accepted"
        world.messages.add(tr("Request taken: {title}.", title=loc(REQUESTS[rid], "title")))
        world.sfx.play("pickup")


def drop(world, rid):
    """Let a request from the board go again."""
    if world.quests.get(rid) == "accepted" and REQUESTS[rid]["source"] == "board":
        del world.quests[rid]
        world.messages.add(tr("Request dropped: {title}.", title=loc(REQUESTS[rid], "title")))
        world.sfx.play("pickup")


def deliver(world, rid):
    """Hand over a request's item (on getting back to the camp). Returns True when paid."""
    req = REQUESTS[rid]
    found = locate(world, req["item"])
    if world.quests.get(rid) != "accepted" or found is None:
        return False
    found[1]()
    world.quests[rid] = "done"
    world.coins += req["reward"]
    world.sfx.play("coins")
    world.messages.add(tr("{title}: done. +{reward} coins.", title=loc(req, "title"), reward=req["reward"]))
    return True


def restore(world, kind):
    """Give a relic to the scholar: the old kingdom's power comes back a little."""
    found = locate(world, kind)
    if found is None:
        return False
    thing = found[0]
    found[1]()
    world.messages.add(tr("You give {name} to Vesk.", name=thing.name))
    world.settle_relic(thing, "restore")
    world.talk("scholar")
    world.screen = None
    return True


def carried(world, kind):
    """How many things of this kind the party carries."""
    things = [world.hand, world.back] + [t for m in world.party.members for t in m.pack + list(m.equip.values())]
    return sum(t is not None and t.kind == kind for t in things)


def count(world, kind):
    """How many the party has: carried, and kept in the camp store."""
    return carried(world, kind) + world.store.get(kind, 0)


def owned(world, kind):
    return kind in world.armory or carried(world, kind) > 0


def wanted(world, material):
    """Whether the smith still has something to make from this material."""
    return any(r["material"] == material and not owned(world, r["kind"]) for r in RECIPES)


def store_materials(world):
    """Back at the camp: materials go from the packs into the store. When the smith has no more use
    for bones, the gravekeeper lays them to rest and pays a little. Returns lines for the report."""
    lines = []
    for material in sorted({r["material"] for r in RECIPES} | {"bone"}):
        n = 0
        while (found := locate(world, material)) is not None:
            found[1]()
            n += 1
        if n:
            world.store[material] = world.store.get(material, 0) + n
            lines.append(("plain", tr("Into the camp store: {name} x{n}.", name=loc(ITEMS[material], "name"), n=n)))
        kept = world.store.get(material, 0)
        if material == "bone" and kept and not wanted(world, material):
            pay = kept * TUNE["bone_coins"]
            world.store[material] = 0
            world.coins += pay
            lines.append(("good", tr("The gravekeeper laid {n} bones to rest: +{pay} coins.", n=kept, pay=pay)))
    return lines


def forge(world, recipe):
    """The smith makes a weapon from materials and coins; it goes to the weapon rack at the camp."""
    kind, material, need, price = recipe["kind"], recipe["material"], recipe["count"], recipe["coins"]
    if count(world, material) < need or world.coins < price:
        world.messages.add(tr("Not enough to make it."))
        world.sfx.play("fizzle")
        return False
    from_store = min(need, world.store.get(material, 0))
    world.store[material] = world.store.get(material, 0) - from_store
    for _ in range(need - from_store):
        locate(world, material)[1]()
    world.coins -= price
    world.armory.append(kind)
    world.sfx.play("coins")
    world.messages.add(tr("The smith made {name}. It is on the weapon rack.", name=loc(ITEMS[kind], "name")))
    return True


def wield(world, kind):
    """Arn takes a weapon from the rack; the one in his hand goes back on it."""
    f = world.party.fighter
    old = f.equip["right"]
    if old is not None and old.kind not in WEAPONS and not f.give(old):
        world.messages.add(tr("No room in the packs."))
        return False
    if old is not None and old.kind in WEAPONS:
        world.armory.append(old.kind)
    world.armory.remove(kind)
    f.equip["right"] = Thing(kind)
    world.sfx.play("pickup")
    world.messages.add(tr("Arn takes {name}.", name=loc(ITEMS[kind], "name")))
    return True


def buy(world, kind, price):
    if world.coins < price:
        world.messages.add(tr("Not enough coins."))
        world.sfx.play("fizzle")
        return False
    thing = Thing(kind)
    if not any(m.give(thing) for m in world.party.members if m.up):
        world.messages.add(tr("No room in the packs."))
        return False
    world.coins -= price
    world.sfx.play("coins")
    world.messages.add(tr("Bought {name}.", name=thing.name))
    return True


# ---------------------------------------------------------------- screens
class Row:
    def __init__(self, label, right, action, detail="", enabled=True, heading=False, first=False):
        self.label = label
        self.right = right
        self.action = action  # callable(world), or None
        self.detail = detail
        self.enabled = enabled
        self.heading = heading
        self.first = first  # chosen first when the screen opens


class CampScreen:
    def __init__(self):
        self.kind = None  # 'down', 'supplies', 'smith', 'arms' or 'scholar' while open
        self.sel = 0

    @property
    def open(self):
        return self.kind is not None

    def show(self, kind):
        self.kind = kind
        self.sel = None  # the row marked first, once the rows are known

    def close(self):
        self.kind = None

    def rows(self, world):
        out = []
        if self.kind == "down":
            out.append(Row(tr("REQUESTS"), "", None, heading=True))
            for rid, req in REQUESTS.items():
                state = world.quests.get(rid)
                if state == "done" or (req["source"] != "board" and state is None):
                    continue
                need = tr("Bring back {name}.", name=loc(ITEMS[req["item"]], "name")) + " " + loc(req, "text")
                if state is None:
                    out.append(Row(loc(req, "title"), tr("{n} coins", n=req["reward"]),
                                   lambda w, rid=rid: accept(w, rid), tr("Space/click: take it.") + " " + need))
                elif req["source"] == "board":
                    out.append(Row("* " + loc(req, "title"), tr("taken"), lambda w, rid=rid: drop(w, rid),
                                   tr("Space/click: let it go.") + " " + need))
                else:  # found on a note: it stays taken
                    out.append(Row("* " + loc(req, "title"), tr("taken"), None, need))
            if len(out) == 1:
                out.append(Row(tr("(no requests left)"), "", None, enabled=False))
            out.append(Row(tr("GO DOWN"), "", None, heading=True))
            ways = [("floor1", tr("Floor 1: the cellar stairs"))]
            ways += [(name, tr("Floor {n}: the old shaft", n=name[5:])) for name in world.shortcuts]
            for name, label in ways:
                out.append(Row(label, "", lambda w, name=name: self.go_down(w, name),
                               tr("What was asked for is handed over by itself when you come back."), first=name == "floor1"))
        elif self.kind == "supplies":
            for r in SHOP:
                name = loc(ITEMS[r["kind"]], "name")
                out.append(Row(tr("Buy {name}", name=name), tr("{n} coins", n=r["price"]),
                               lambda w, k=r["kind"], p=r["price"]: buy(w, k, p),
                               enabled=world.coins >= r["price"]))
        elif self.kind == "smith":
            out.append(Row(tr("THE SMITH MAKES"), "", None, heading=True))
            for r in RECIPES:
                if owned(world, r["kind"]):
                    continue  # made already: no need for another
                have = count(world, r["material"])
                ok = have >= r["count"] and world.coins >= r["coins"]
                need = tr("{material} x{n} ({have} at hand) and {coins} coins", material=loc(ITEMS[r["material"]], "name"),
                          n=r["count"], have=have, coins=r["coins"])
                out.append(Row(loc(ITEMS[r["kind"]], "name"), tr("{n} coins", n=r["coins"]), lambda w, r=r: forge(w, r),
                               need + ". " + loc(WEAPONS[r["kind"]], "text"), enabled=ok))
            if len(out) == 1:
                out.append(Row(tr("(nothing more to make for now)"), "", None, enabled=False))
        elif self.kind == "arms":
            f = world.party.fighter
            held = f.equip["right"]
            out.append(Row(tr("IN ARN'S HAND"), "", None, heading=True))
            out.append(Row(held.name if held is not None else tr("(nothing)"), "", None,
                           loc(WEAPONS[held.kind], "text") if held is not None and held.kind in WEAPONS else "", enabled=False))
            out.append(Row(tr("ON THE WEAPON RACK"), "", None, heading=True))
            for kind in world.armory:
                w = WEAPONS[kind]
                out.append(Row(loc(ITEMS[kind], "name"), tr("reach {r}", r=w["reach"]), lambda wo, k=kind: wield(wo, k),
                               loc(w, "text"), first=True))
            if not world.armory:
                out.append(Row(tr("(empty)"), "", None, enabled=False))
        elif self.kind == "scholar":
            out.append(Row(tr("GIVE TO VESK, THE SCHOLAR"), "", None, heading=True))
            for kind, relic in RELICS.items():
                found = locate(world, kind)
                if found is not None:
                    out.append(Row(tr("Give {name}", name=loc(relic, "name")), tr("restore"), lambda w, k=kind: restore(w, k),
                                   tr("Vesk will bring its power back. The dungeon will change at once.")))
        out.append(Row(tr("Back") if self.kind == "down" else tr("Close"), "", lambda w: self.close()))
        return out

    def go_down(self, world, name):
        self.close()
        world.descend(name)

    def _row_at(self, rows, my):
        i = (my - LIST_Y) // row_h()
        return i if 0 <= i < len(rows) and not rows[i].heading else None

    def _choosable(self, rows):
        return [i for i, r in enumerate(rows) if not r.heading]

    # ------------------------------------------------------------ input
    def update(self, world, mx, my, clicked, space, tab, mouse_moved):
        rows = self.rows(world)
        pick = self._choosable(rows)
        if clicked or mouse_moved:
            world.mode = "mouse"
        if tab:
            if world.mode == "keys" and self.sel in pick:
                self.sel = pick[(pick.index(self.sel) + 1) % len(pick)]
            elif self.sel not in pick:
                self.sel = next((i for i in pick if rows[i].first), pick[0])
            world.mode = "keys"
        chosen = self.chosen(world, rows, mx, my)
        if chosen is None:
            return
        if space or (clicked and X0 <= mx < X0 + PW):
            action = rows[chosen].action
            if action is not None:
                action(world)

    def chosen(self, world, rows, mx, my):
        if world.mode == "keys":
            pick = self._choosable(rows)
            if self.sel not in pick:
                self.sel = next((i for i in pick if rows[i].first), pick[0])
            return self.sel
        return self._row_at(rows, my) if X0 <= mx < X0 + PW else None

    # ------------------------------------------------------------ draw
    def draw(self, world, mx, my):
        rows = self.rows(world)
        chosen = self.chosen(world, rows, mx, my)
        pyxel.dither(1.0)  # solid: Japanese letters need a calm background
        pyxel.rect(X0, Y0, PW, PH, BLACK)
        pyxel.dither(1.0)
        pyxel.rectb(X0, Y0, PW, PH, STONE_I[4])
        title = {"down": "BEFORE GOING DOWN", "supplies": "SUPPLIES", "smith": "THE SMITH",
                 "arms": "THE WEAPON RACK", "scholar": "VESK'S TABLE"}[self.kind]
        lang.text(X0 + 8, Y0 + 7, tr(title), FIRE_I[5])
        coins = tr("Coins: {n}", n=world.coins)
        lang.text(X0 + PW - 8 - lang.width(coins), Y0 + 7, coins, FIRE_I[4])
        for i, r in enumerate(rows):
            y = LIST_Y + i * row_h()
            if r.heading:
                lang.text(X0 + 8, y + 2, r.label, STONE_I[5])
                continue
            if i == chosen:
                pyxel.rect(X0 + 4, y, PW - 8, row_h() - 1, STONE_I[2])
            col = WHITE if r.enabled else STONE_I[4]
            lang.text(X0 + 14, y + 2, r.label, col)
            lang.text(X0 + PW - 10 - lang.width(r.right), y + 2, r.right, FIRE_I[4] if r.enabled else STONE_I[4])
        if chosen is not None and rows[chosen].detail:
            y = Y0 + PH - 52
            for line in lang.wrap(rows[chosen].detail, PW - 16)[:4]:
                lang.text(X0 + 8, y, line, STONE_I[6])
                y += lang.line(9)
        lang.text(X0 + 8, Y0 + PH - 12, tr("Tab: next  Space/click: choose  Esc: close"), STONE_I[5])
