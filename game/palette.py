"""32-color dungeon palette and distance-banded shading tables."""

from pyxel.cube import Shading

# Ramps run dark -> bright. Index 0 is pure black.
STONE = [0x0E0D12, 0x1C1B24, 0x2B2A35, 0x3D3C48, 0x52515E, 0x6A6976, 0x85848F, 0xA3A2AB]
EARTH = [0x120C08, 0x23170F, 0x352317, 0x4A3120, 0x60412A, 0x785436, 0x926A45, 0xAE8358]
FIRE = [0x3A0E06, 0x6E1E0A, 0xA8380E, 0xD9621A, 0xF29A2E, 0xFFD25A]
MOSS = [0x1A2412, 0x2E3F1E, 0x4A6230]
BLUE = [0x101B33, 0x22355E, 0x3E5E96]
MISC = [0xF2EEE6, 0xC23B3B, 0x7A2F8F]

PALETTE = [0x000000] + STONE + EARTH + FIRE + MOSS + BLUE + MISC
assert len(PALETTE) == 32


def _ramp_indices():
    ramps, i = [], 1
    for ramp in (STONE, EARTH, FIRE, MOSS, BLUE):
        ramps.append(list(range(i, i + len(ramp))))
        i += len(ramp)
    return ramps


RAMPS = _ramp_indices()
STONE_I, EARTH_I, FIRE_I, MOSS_I, BLUE_I = RAMPS
WHITE, RED, PURPLE = 29, 30, 31
BLACK = 0


def build_band_shadings(n_bands):
    """Return one Shading per distance band (band 0 = brightest).

    Brightness is counted in half-steps along each color's ramp. Odd
    half-steps become 2x2 dither pairs. Each band darks one half-step,
    so bands should be spaced about half a cell apart.
    """
    ramp_of = {0: ([0], 0)}
    for ramp in RAMPS:
        for pos, c in enumerate(ramp):
            ramp_of[c] = (ramp, pos)
    shadings = []
    for band in range(n_bands):
        sh = Shading(PALETTE)
        for c in range(len(PALETTE)):
            ramp, pos = ramp_of.get(c, ([c], 0))
            for level in range(Shading.LEVEL_COUNT):
                # level 5 keeps the original color; one level = one half-step
                hs = pos * 2 + (level - 5) - band
                if hs < 0:
                    pair = (0, ramp[0]) if hs == -1 else (0, 0)
                else:
                    lo = min(hs // 2, len(ramp) - 1)
                    hi = min(lo + (hs % 2), len(ramp) - 1)
                    pair = (ramp[lo], ramp[hi])
                sh[c, level] = pair
        shadings.append(sh)
    return shadings
