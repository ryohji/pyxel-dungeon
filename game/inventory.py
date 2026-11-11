"""The inventory screen: each member's stats, skills, equipment and pack.

The game pauses while it is open. Clicking a slot (or choosing it with Tab
and pressing Space) swaps it with the item in the hand. Putting food or a
waterskin on the mouth slot eats or drinks it.
"""

import pyxel

from palette import BLACK, BLUE_I, EARTH_I, FIRE_I, MOSS_I, RED, STONE_I, WHITE
from party import PACK_SIZE, SLOTS
from tables import SKILLS, TUNE
from textures import ICON, draw_icon

X0, Y0, PW, PH = 6, 14, 308, 214
COL_W = 152
BOX = ICON + 2
SLOT_LABEL = {"right": "RIGHT", "left": "LEFT", "head": "HEAD", "body": "BODY", "mouth": "EAT"}
FOOTER = "I/Esc: close  Tab: next slot  Space/click: take, put, eat"


class Slot:
    def __init__(self, member, area, key, x, y):
        self.member = member
        self.area = area  # 'equip', 'pack' or 'mouth'
        self.key = key  # slot name or pack index
        self.x, self.y = x, y

    @property
    def thing(self):
        m = self.member
        if self.area == "equip":
            return m.equip[self.key]
        if self.area == "pack":
            return m.pack[self.key]
        return None

    def set(self, thing):
        if self.area == "equip":
            self.member.equip[self.key] = thing
        else:
            self.member.pack[self.key] = thing

    def contains(self, mx, my):
        return self.x <= mx < self.x + BOX and self.y <= my < self.y + BOX


class Inventory:
    def __init__(self, icons):
        self.icons = icons
        self.open = False
        self.sel = 0

    def slots(self, party):
        out = []
        for col, m in enumerate(party.members):
            x = X0 + 4 + col * COL_W
            y = Y0 + 100
            for i, s in enumerate(SLOTS):
                out.append(Slot(m, "equip", s, x + i * (BOX + 10), y))
            out.append(Slot(m, "mouth", None, x + 4 * (BOX + 10) + 6, y))
            for i in range(PACK_SIZE):
                out.append(Slot(m, "pack", i, x + (i % 4) * (BOX + 2), y + 38 + (i // 4) * (BOX + 2)))
        return out

    # ------------------------------------------------------------ input
    def update(self, world, mx, my, clicked, space, tab, mouse_moved):
        slots = self.slots(world.party)
        if clicked or mouse_moved:
            world.mode = "mouse"
        if tab:
            if world.mode == "keys":
                self.sel = (self.sel + 1) % len(slots)
            world.mode = "keys"
        chosen = self.chosen(world, slots, mx, my)
        if chosen is not None and (space or (clicked and chosen.contains(mx, my))):
            self.use(world, chosen)

    def chosen(self, world, slots, mx, my):
        if world.mode == "keys":
            return slots[self.sel % len(slots)]
        return next((s for s in slots if s.contains(mx, my)), None)

    def use(self, world, slot):
        m = slot.member
        hand = world.hand
        if not m.up:
            world.messages.add(f"{m.name} is down.")
            return
        if slot.area == "mouth":
            if hand is None:
                world.messages.add("Hold food or drink over the mouth.")
                return
            result = m.consume(hand)
            if result is None:
                world.messages.add("That is not something to eat.")
                return
            text, used_up = result
            world.messages.add(text)
            if text != "It is empty.":
                world.sfx.play("eat" if hand.row["food"] else "drink")
            if used_up:
                world.hand = None
            return
        if hand is not None and not hand.fits(slot.key if slot.area == "equip" else "pack"):
            world.messages.add(f"{hand.name.capitalize()} does not go there.")
            return
        if hand is None and slot.thing is None:
            return
        world.hand, taken = slot.thing, hand
        slot.set(taken)
        world.sfx.play("pickup")

    # ------------------------------------------------------------ draw
    def draw(self, world, mx, my):
        pyxel.dither(0.9)
        pyxel.rect(X0, Y0, PW, PH, BLACK)
        pyxel.dither(1.0)
        pyxel.rectb(X0, Y0, PW, PH, STONE_I[4])
        pyxel.line(X0 + COL_W + 2, Y0 + 4, X0 + COL_W + 2, Y0 + PH - 16, STONE_I[2])
        for col, m in enumerate(world.party.members):
            self._member(m, X0 + 4 + col * COL_W, Y0 + 4)
        slots = self.slots(world.party)
        chosen = self.chosen(world, slots, mx, my)
        for s in slots:
            self._slot(s, s is chosen)
        info = None
        if chosen is not None:
            thing = chosen.thing
            info = describe(thing) if thing is not None else SLOT_LABEL.get(chosen.key if chosen.area == "equip" else chosen.area, "")
        if world.hand is not None:
            info = "In hand: " + describe(world.hand)
            if world.mode == "keys" and chosen is not None:
                draw_icon(self.icons, world.hand, chosen.x + 8, chosen.y - 8)
        if info:
            pyxel.text(X0 + 6, Y0 + PH - 22, info, FIRE_I[5])
        load = f"On Arn's back: {world.back.name}" if world.back is not None else ""
        coins = f"Coins: {world.coins}"
        pyxel.text(X0 + 6, Y0 + PH - 32, load, STONE_I[6])
        pyxel.text(X0 + PW - 6 - len(coins) * 4, Y0 + PH - 32, coins, FIRE_I[4])
        pyxel.text(X0 + 6, Y0 + PH - 10, FOOTER, STONE_I[5])

    def _member(self, m, x, y):
        pyxel.text(x, y, f"{m.name}", WHITE if m.up else STONE_I[4])
        pyxel.text(x + 28, y, m.role, STONE_I[5])
        rows = [("HP", m.hp, m.max_hp, RED), ("ST", m.stamina, m.max_stamina, MOSS_I[2])]
        if m.max_mana:
            rows.append(("MP", m.mana, m.max_mana, BLUE_I[2]))
        rows += [("FOOD", m.food, 100, EARTH_I[5]), ("WATER", m.water, 100, BLUE_I[2])]
        yy = y + 10
        for label, v, top, col in rows:
            pyxel.text(x, yy, label, STONE_I[6])
            pyxel.rect(x + 24, yy + 1, 70, 4, STONE_I[1])
            low = label in ("FOOD", "WATER") and v < TUNE["hungry_below"]
            pyxel.rect(x + 24, yy + 1, round(70 * max(0, v) / top), 4, RED if low else col)
            pyxel.text(x + 98, yy, f"{int(v)}/{int(top)}" if label not in ("FOOD", "WATER") else f"{int(v)}", WHITE)
            yy += 8
        yy = y + 54
        pyxel.text(x, yy, "STR {str:<3}DEX {dex:<3}WIS {wis:<3}VIT {vit}".format(**m.stats), STONE_I[6])
        yy += 9
        for i, s in enumerate(SKILLS):
            sx = x + (i % 2) * 72
            sy = yy + (i // 2) * 8
            pyxel.text(sx, sy, f"{s.capitalize():8}{m.level[s]}", FIRE_I[4])
            nxt = next_xp(m, s)
            if nxt:
                done = (m.xp[s] - nxt[0]) / max(1, nxt[1] - nxt[0])
                pyxel.rect(sx + 44, sy + 2, 20, 1, STONE_I[2])
                pyxel.rect(sx + 44, sy + 2, round(20 * min(1, done)), 1, FIRE_I[3])
        pyxel.text(x, y + 126, "PACK", STONE_I[5])

    def _slot(self, s, chosen):
        pyxel.rect(s.x, s.y, BOX, BOX, STONE_I[1])
        pyxel.rectb(s.x, s.y, BOX, BOX, FIRE_I[5] if chosen else STONE_I[3])
        if s.area == "mouth":
            pyxel.elli(s.x + 4, s.y + 7, 10, 5, EARTH_I[2])
            pyxel.line(s.x + 5, s.y + 9, s.x + 12, s.y + 9, BLACK)
        thing = s.thing
        if thing is not None:
            draw_icon(self.icons, thing, s.x + 1, s.y + 1)
        if s.area != "pack":
            label = SLOT_LABEL[s.key if s.area == "equip" else "mouth"]
            pyxel.text(s.x + BOX // 2 - len(label) * 2, s.y - 7, label, STONE_I[4])


def next_xp(m, skill):
    """(xp at the current level, xp for the next), or None at the top level."""
    from tables import LEVELS, xp_for
    cur = xp_for(skill, m.level[skill])
    for lv, need, _ in LEVELS[skill]:
        if lv == m.level[skill] + 1:
            return cur, need
    return None


def describe(thing):
    """One line about a thing: its name and what it does."""
    r = thing.row
    parts = [thing.name]
    if r["damage_max"]:
        parts.append(f"hits {r['damage_min']}-{r['damage_max']}")
    if r["throw_max"] >= 4:
        parts.append(f"thrown {r['throw_min']}-{r['throw_max']}")
    if r["defense"]:
        parts.append(f"armor {r['defense']}")
    if r["food"]:
        parts.append(f"food +{r['food']}")
    if r["water"]:
        parts.append(f"{thing.charges}/{r['charges']} drinks")
    if thing.kind == "torch":
        parts.append(f"{thing.fuel // 3600} min left" if thing.fuel > 0 else "")
    return ", ".join(p for p in parts if p)
