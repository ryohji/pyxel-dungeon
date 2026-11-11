"""Procedural textures packed into one atlas image."""

import random

import pyxel

from palette import BLACK, BLUE_I, EARTH_I, FIRE_I, MOSS_I, STONE_I

TEX = 32
TILES = ("wall", "floor", "ceiling", "wall_moss", "door", "shaft")
TILE_INDEX = {name: i for i, name in enumerate(TILES)}


def tile_uv(name):
    """(u0, u1, v0, v1) of a tile, inset half a texel to avoid bleeding."""
    i = TILE_INDEX[name]
    n = len(TILES)
    eps = 0.5 / (TEX * n)
    return i / n + eps, (i + 1) / n - eps, 0.5 / TEX, 1 - 0.5 / TEX


def _bricks(img, ox, rnd, moss, dark=0):
    """Stone bricks; dark shifts every color down the ramp (for pit shafts)."""
    img.rect(ox, 0, TEX, TEX, STONE_I[max(0, 2 - dark)])
    for row in range(4):
        y = row * 8
        off = 0 if row % 2 == 0 else 8
        for col in range(-1, 3):
            x = col * 16 + off
            x0, x1 = max(0, x + 1), min(TEX, x + 16)
            if x1 <= x0:
                continue
            img.rect(ox + x0, y + 1, x1 - x0, 7, STONE_I[rnd.choice((4, 5, 5, 6)) - dark])
            for _ in range(3):
                img.pset(ox + x0 + rnd.randrange(x1 - x0), y + 1 + rnd.randrange(7), STONE_I[3 - dark])
    if moss:
        for _ in range(70):
            x = rnd.randrange(TEX)
            y = TEX - 1 - int(abs(rnd.gauss(0, 7)))
            if 0 <= y < TEX:
                img.pset(ox + x, y, MOSS_I[rnd.choice((0, 1, 1, 2))])


def make_atlas():
    rnd = random.Random(1)
    img = pyxel.Image(TEX * len(TILES), TEX)

    _bricks(img, TEX * TILE_INDEX["wall"], rnd, moss=False)
    _bricks(img, TEX * TILE_INDEX["wall_moss"], rnd, moss=True)
    _bricks(img, TEX * TILE_INDEX["shaft"], rnd, moss=False, dark=3)

    ox = TEX * TILE_INDEX["floor"]
    img.rect(ox, 0, TEX, TEX, EARTH_I[2])
    for (x, y, w, h) in ((1, 1, 14, 14), (17, 1, 14, 10), (17, 12, 14, 19), (1, 16, 14, 15)):
        img.rect(ox + x, y, w, h, EARTH_I[rnd.choice((4, 5))])
        for _ in range(4):
            img.pset(ox + x + rnd.randrange(w), y + rnd.randrange(h), EARTH_I[3])

    ox = TEX * TILE_INDEX["door"]
    img.rect(ox, 0, TEX, TEX, EARTH_I[2])
    for x in range(0, TEX, 8):  # vertical planks
        img.rect(ox + x + 1, 0, 6, TEX, EARTH_I[rnd.choice((4, 5))])
        for _ in range(5):
            img.pset(ox + x + 1 + rnd.randrange(6), rnd.randrange(TEX), EARTH_I[3])
    for y in (5, 24):  # iron bands with rivets
        img.rect(ox, y, TEX, 3, STONE_I[3])
        for x in range(2, TEX, 8):
            img.pset(ox + x, y + 1, STONE_I[6])

    ox = TEX * TILE_INDEX["ceiling"]
    img.rect(ox, 0, TEX, TEX, STONE_I[2])
    for _ in range(80):
        img.pset(ox + rnd.randrange(TEX), rnd.randrange(TEX), STONE_I[rnd.choice((1, 3))])
    return img


ICON = 16
ICONS = ("rock", "key_iron", "torch", "bread", "waterskin", "dagger", "sword", "buckler", "cap", "jerkin",
         "ring", "lantern", "note", "remains", "idol")


def make_icons():
    """16x16 icons for items in the hand and the pack (color 0 is transparent)."""
    img = pyxel.Image(ICON * len(ICONS), ICON)
    img.cls(BLACK)
    S, E = STONE_I, EARTH_I

    def at(kind):
        return ICONS.index(kind) * ICON

    o = at("rock")
    img.elli(o + 2, 4, 12, 9, S[3])
    img.elli(o + 3, 4, 10, 7, S[5])
    img.pset(o + 6, 6, S[7])
    img.pset(o + 7, 6, S[6])

    o = at("key_iron")
    img.circb(o + 4, 8, 3, S[6])
    img.rect(o + 7, 7, 8, 2, S[6])
    img.rect(o + 11, 9, 1, 3, S[6])
    img.rect(o + 13, 9, 1, 2, S[6])
    img.pset(o + 3, 6, S[7])

    o = at("torch")  # the flame is drawn on top while it burns
    img.line(o + 4, 14, o + 10, 6, E[3])
    img.line(o + 5, 14, o + 11, 6, E[2])
    img.rect(o + 9, 4, 4, 4, E[1])

    o = at("bread")
    img.elli(o + 1, 5, 14, 8, E[4])
    img.elli(o + 3, 5, 10, 5, E[6])
    for x in (5, 8, 11):
        img.line(o + x, 6, o + x + 1, 8, E[3])

    o = at("waterskin")
    img.elli(o + 2, 5, 11, 10, E[3])
    img.elli(o + 4, 6, 6, 5, E[4])
    img.rect(o + 11, 3, 3, 3, E[2])
    img.rect(o + 12, 1, 3, 2, S[5])

    o = at("dagger")
    img.line(o + 3, 12, o + 11, 4, S[6])
    img.line(o + 4, 12, o + 12, 4, S[7])
    img.line(o + 1, 12, o + 5, 16, FIRE_I[2])
    img.line(o + 1, 15, o + 2, 14, E[2])

    o = at("sword")
    img.line(o + 4, 11, o + 14, 1, S[6])
    img.line(o + 5, 11, o + 14, 2, S[7])
    img.line(o + 1, 9, o + 6, 14, FIRE_I[2])
    img.line(o + 1, 14, o + 3, 12, E[2])
    img.pset(o, 15, FIRE_I[3])

    o = at("buckler")
    img.circ(o + 8, 8, 6, E[3])
    img.circb(o + 8, 8, 6, S[5])
    img.circ(o + 8, 8, 2, S[6])
    img.pset(o + 7, 7, S[7])

    o = at("cap")
    img.elli(o + 2, 4, 12, 10, E[3])
    img.rect(o + 1, 9, 14, 3, E[2])
    img.line(o + 5, 5, o + 9, 5, E[5])

    o = at("jerkin")
    img.rect(o + 3, 3, 10, 11, E[3])
    img.rect(o + 1, 3, 3, 6, E[2])
    img.rect(o + 12, 3, 3, 6, E[2])
    img.line(o + 8, 3, o + 8, 13, E[1])
    img.rect(o + 6, 2, 4, 2, BLACK)

    o = at("ring")
    img.circb(o + 8, 9, 4, S[7])
    img.circb(o + 8, 9, 3, S[5])
    img.rect(o + 7, 3, 3, 3, BLUE_I[2])
    img.pset(o + 7, 3, STONE_I[7])

    o = at("lantern")
    img.rect(o + 5, 4, 7, 9, FIRE_I[2])
    img.rect(o + 6, 5, 5, 7, FIRE_I[4])
    img.rect(o + 7, 7, 3, 3, FIRE_I[5])
    img.rect(o + 4, 13, 9, 2, FIRE_I[1])
    img.circb(o + 8, 2, 2, FIRE_I[2])

    o = at("note")
    img.rect(o + 3, 2, 10, 12, S[7])
    for y in (5, 7, 9, 11):
        img.line(o + 5, y, o + 10, y, S[3])
    img.rect(o + 9, 2, 4, 3, S[5])

    o = at("remains")
    img.rect(o + 1, 6, 11, 7, E[2])
    img.rect(o + 2, 5, 8, 2, E[3])
    img.circ(o + 13, 8, 2, S[7])
    img.pset(o + 13, 8, BLACK)

    o = at("idol")
    img.rect(o + 4, 12, 8, 3, S[3])
    img.rect(o + 5, 5, 6, 7, S[5])
    img.rect(o + 5, 1, 6, 5, S[6])
    img.pset(o + 6, 3, FIRE_I[4])
    img.pset(o + 9, 3, FIRE_I[4])
    return img


def icon_uv(kind):
    for prefix in ("note", "remains"):
        if kind.startswith(prefix + "_"):
            kind = prefix
    return ICONS.index(kind) * ICON, 0


def draw_icon(icons, thing, x, y):
    """Blit a thing's icon at (x, y), with a flame on a lit torch."""
    u, v = icon_uv(thing.kind)
    pyxel.blt(x, y, icons, u, v, ICON, ICON, BLACK)
    if thing.kind == "torch" and thing.fuel > 0:
        flick = pyxel.frame_count // 4 % 2
        pyxel.rect(x + 9, y + 1 - flick, 4, 3 + flick, FIRE_I[4])
        pyxel.rect(x + 10, y + 2, 2, 2, FIRE_I[5])


def tile_image(atlas, name):
    """A copy of one atlas tile as its own image (box() textures every face with a whole image)."""
    img = pyxel.Image(TEX, TEX)
    img.blt(0, 0, atlas, TEX * TILE_INDEX[name], 0, TEX, TEX)
    return img
