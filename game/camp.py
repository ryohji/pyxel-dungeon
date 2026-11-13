"""The camp at the mouth of the dungeon: the request board and the counter.

Requests (data/requests.csv) come from the board, or from notes found in
the dungeon. Bring the item back, hand it over at the counter, get paid,
and buy supplies (data/shop.csv) with the coins. Both screens pause the
game; Tab picks a row, Space or a click acts on it, Esc closes.
"""

import textwrap

import pyxel

from palette import BLACK, FIRE_I, STONE_I, WHITE
from tables import ITEMS, RELICS, REQUESTS, SHOP
from things import Thing

X0, Y0, PW, PH = 6, 14, 308, 214
ROW_H = 10
LIST_Y = Y0 + 22


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
        world.messages.add(f"Request taken: {REQUESTS[rid]['title']}.")
        world.sfx.play("pickup")


def deliver(world, rid):
    """Hand over a request's item at the counter. Returns True when paid."""
    req = REQUESTS[rid]
    found = locate(world, req["item"])
    if world.quests.get(rid) != "accepted" or found is None:
        return False
    found[1]()
    world.quests[rid] = "done"
    world.coins += req["reward"]
    world.sfx.play("coins")
    world.messages.add(f"{req['title']}: done. +{req['reward']} coins.")
    return True


def restore(world, kind):
    """Give a relic to the scholar: the old kingdom's power comes back a little."""
    found = locate(world, kind)
    if found is None:
        return False
    thing = found[0]
    found[1]()
    world.messages.add(f"You give {thing.name} to Vesk.")
    world.settle_relic(thing, "restore")
    scholar = next((p for p in world.floor.people if p.name == "scholar"), None)
    if scholar is not None:
        world.talk(scholar)
        world.screen = None
    return True


def buy(world, kind, price):
    if world.coins < price:
        world.messages.add("Not enough coins.")
        world.sfx.play("fizzle")
        return False
    thing = Thing(kind)
    if not any(m.give(thing) for m in world.party.members if m.up):
        world.messages.add("No room in the packs.")
        return False
    world.coins -= price
    world.sfx.play("coins")
    world.messages.add(f"Bought {thing.name}.")
    return True


# ---------------------------------------------------------------- screens
class Row:
    def __init__(self, label, right, action, detail="", enabled=True, heading=False):
        self.label = label
        self.right = right
        self.action = action  # callable(world), or None
        self.detail = detail
        self.enabled = enabled
        self.heading = heading


class CampScreen:
    def __init__(self):
        self.kind = None  # 'board' or 'counter' while open
        self.sel = 0

    @property
    def open(self):
        return self.kind is not None

    def show(self, kind):
        self.kind = kind
        self.sel = 0

    def close(self):
        self.kind = None

    def rows(self, world):
        out = []
        if self.kind == "board":
            out.append(Row("REQUESTS", "", None, heading=True))
            for rid, req in REQUESTS.items():
                if req["source"] != "board":
                    continue
                state = world.quests.get(rid)
                right = {"accepted": "taken", "done": "done"}.get(state, f"{req['reward']} coins")
                out.append(Row(req["title"], right, (lambda w, rid=rid: accept(w, rid)) if state is None else None,
                               req["text"], enabled=state is None))
        elif self.kind == "scholar":
            out.append(Row("GIVE TO VESK, THE SCHOLAR", "", None, heading=True))
            for kind, relic in RELICS.items():
                found = locate(world, kind)
                if found is not None:
                    out.append(Row(f"Give {relic['name']}", "restore", lambda w, k=kind: restore(w, k),
                                   "Vesk will bring its power back. The dungeon will change at once."))
        else:
            out.append(Row("HAND OVER", "", None, heading=True))
            for rid, state in world.quests.items():
                req = REQUESTS[rid]
                if state == "done":
                    continue
                ready = locate(world, req["item"]) is not None
                out.append(Row(req["title"], f"{req['reward']} coins" if ready else "not carried",
                               (lambda w, rid=rid: deliver(w, rid)) if ready else None,
                               f"Bring back {ITEMS[req['item']]['name']}. {req['text']}", enabled=ready))
            if len(out) == 1:
                out.append(Row("(no requests taken)", "", None, enabled=False))
            out.append(Row("SUPPLIES", "", None, heading=True))
            for r in SHOP:
                name = ITEMS[r["kind"]]["name"]
                out.append(Row(f"Buy {name}", f"{r['price']} coins",
                               lambda w, k=r["kind"], p=r["price"]: buy(w, k, p),
                               enabled=world.coins >= r["price"]))
        out.append(Row("Close", "", lambda w: self.close()))
        return out

    def _row_at(self, rows, my):
        i = (my - LIST_Y) // ROW_H
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
                self.sel = pick[0]
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
                self.sel = pick[0]
            return self.sel
        return self._row_at(rows, my) if X0 <= mx < X0 + PW else None

    # ------------------------------------------------------------ draw
    def draw(self, world, mx, my):
        rows = self.rows(world)
        chosen = self.chosen(world, rows, mx, my)
        pyxel.dither(0.9)
        pyxel.rect(X0, Y0, PW, PH, BLACK)
        pyxel.dither(1.0)
        pyxel.rectb(X0, Y0, PW, PH, STONE_I[4])
        title = {"board": "THE REQUEST BOARD", "counter": "THE CAMP COUNTER", "scholar": "VESK'S TABLE"}[self.kind]
        pyxel.text(X0 + 8, Y0 + 7, title, FIRE_I[5])
        coins = f"Coins: {world.coins}"
        pyxel.text(X0 + PW - 8 - len(coins) * 4, Y0 + 7, coins, FIRE_I[4])
        for i, r in enumerate(rows):
            y = LIST_Y + i * ROW_H
            if r.heading:
                pyxel.text(X0 + 8, y + 2, r.label, STONE_I[5])
                continue
            if i == chosen:
                pyxel.rect(X0 + 4, y, PW - 8, ROW_H - 1, STONE_I[2])
            col = WHITE if r.enabled else STONE_I[4]
            pyxel.text(X0 + 14, y + 2, r.label, col)
            pyxel.text(X0 + PW - 10 - len(r.right) * 4, y + 2, r.right, FIRE_I[4] if r.enabled else STONE_I[4])
        if chosen is not None and rows[chosen].detail:
            y = Y0 + PH - 52
            for line in textwrap.wrap(rows[chosen].detail, 72)[:4]:
                pyxel.text(X0 + 8, y, line, STONE_I[6])
                y += 9
        pyxel.text(X0 + 8, Y0 + PH - 10, "Tab: next  Space/click: choose  Esc: close", STONE_I[5])
