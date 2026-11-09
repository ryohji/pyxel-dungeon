"""Procedural textures packed into one atlas image."""

import random

import pyxel

from palette import EARTH_I, MOSS_I, STONE_I

TEX = 32
TILES = ("wall", "floor", "ceiling", "wall_moss")
TILE_INDEX = {name: i for i, name in enumerate(TILES)}


def tile_uv(name):
    """(u0, u1, v0, v1) of a tile, inset half a texel to avoid bleeding."""
    i = TILE_INDEX[name]
    n = len(TILES)
    eps = 0.5 / (TEX * n)
    return i / n + eps, (i + 1) / n - eps, 0.5 / TEX, 1 - 0.5 / TEX


def _bricks(img, ox, rnd, moss):
    img.rect(ox, 0, TEX, TEX, STONE_I[2])
    for row in range(4):
        y = row * 8
        off = 0 if row % 2 == 0 else 8
        for col in range(-1, 3):
            x = col * 16 + off
            x0, x1 = max(0, x + 1), min(TEX, x + 16)
            if x1 <= x0:
                continue
            img.rect(ox + x0, y + 1, x1 - x0, 7, STONE_I[rnd.choice((4, 5, 5, 6))])
            for _ in range(3):
                img.pset(ox + x0 + rnd.randrange(x1 - x0), y + 1 + rnd.randrange(7), STONE_I[3])
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

    ox = TEX * TILE_INDEX["floor"]
    img.rect(ox, 0, TEX, TEX, EARTH_I[2])
    for (x, y, w, h) in ((1, 1, 14, 14), (17, 1, 14, 10), (17, 12, 14, 19), (1, 16, 14, 15)):
        img.rect(ox + x, y, w, h, EARTH_I[rnd.choice((4, 5))])
        for _ in range(4):
            img.pset(ox + x + rnd.randrange(w), y + rnd.randrange(h), EARTH_I[3])

    ox = TEX * TILE_INDEX["ceiling"]
    img.rect(ox, 0, TEX, TEX, STONE_I[2])
    for _ in range(80):
        img.pset(ox + rnd.randrange(TEX), rnd.randrange(TEX), STONE_I[rnd.choice((1, 3))])
    return img
