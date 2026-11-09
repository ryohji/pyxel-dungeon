"""Procedural textures packed into one atlas image."""

import random

import pyxel

from palette import BLACK, EARTH_I, MOSS_I, STONE_I

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
ICONS = ("rock", "key_iron")


def make_icons():
    """16x16 icons for items held in the hand (color 0 is transparent)."""
    img = pyxel.Image(ICON * len(ICONS), ICON)
    img.cls(BLACK)
    # rock
    img.elli(2, 4, 12, 9, STONE_I[3])
    img.elli(3, 4, 10, 7, STONE_I[5])
    img.pset(6, 6, STONE_I[7])
    img.pset(7, 6, STONE_I[6])
    # iron key
    ox = ICON
    img.circb(ox + 4, 8, 3, STONE_I[6])
    img.rect(ox + 7, 7, 8, 2, STONE_I[6])
    img.rect(ox + 11, 9, 1, 3, STONE_I[6])
    img.rect(ox + 13, 9, 1, 2, STONE_I[6])
    img.pset(ox + 3, 6, STONE_I[7])
    return img


def icon_uv(kind):
    return ICONS.index(kind) * ICON, 0


def tile_image(atlas, name):
    """A copy of one atlas tile as its own image (box() textures every face with a whole image)."""
    img = pyxel.Image(TEX, TEX)
    img.blt(0, 0, atlas, TEX * TILE_INDEX[name], 0, TEX, TEX)
    return img
