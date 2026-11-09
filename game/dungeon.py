"""Grid dungeon: ASCII map loading and per-cell geometry.

World axes: +X right (east), +Y up, -Z forward (north).
Grid cell (gx, gy) covers x in [gx, gx+1) * CELL and z in [gy, gy+1) * CELL,
so grid rows grow southward (+Z).

Map characters:
  #  stone wall          M  mossy wall
  .  floor               ^ > v <  player start facing N / E / S / W
  (space) solid rock (treated as wall)
Lines starting with ';' are comments.
"""

from pyxel.cube import Primitive

from textures import tile_uv

CELL = 100.0  # 1 m
WALL_H = 100.0
SUBDIV = 4  # faces are split SUBDIV x SUBDIV to hide affine texture warping

WALL_TILES = {"#": "wall", "M": "wall_moss", " ": "wall"}
START_YAW = {"^": 0.0, ">": 90.0, "v": 180.0, "<": 270.0}


class Dungeon:
    def __init__(self, text):
        rows = [ln.rstrip("\n") for ln in text.splitlines() if not ln.startswith(";")]
        while rows and not rows[-1].strip():
            rows.pop()
        self.h = len(rows)
        self.w = max(len(r) for r in rows)
        self.cells = [list(r.ljust(self.w)) for r in rows]
        self.start = None
        for gy, row in enumerate(self.cells):
            for gx, ch in enumerate(row):
                if ch in START_YAW:
                    self.start = (gx, gy, START_YAW[ch])
                    row[gx] = "."
        if self.start is None:
            raise ValueError("map has no start (^ > v <)")

    @classmethod
    def load(cls, path):
        with open(path, encoding="utf-8") as f:
            return cls(f.read())

    def char(self, gx, gy):
        if 0 <= gx < self.w and 0 <= gy < self.h:
            return self.cells[gy][gx]
        return " "

    def is_wall(self, gx, gy):
        return self.char(gx, gy) in WALL_TILES

    def open_cells(self):
        for gy in range(self.h):
            for gx in range(self.w):
                if not self.is_wall(gx, gy):
                    yield gx, gy

    # ------------------------------------------------------------ geometry
    def cell_faces(self, gx, gy):
        """Faces of an open cell, relative to the cell's floor center.

        Each face is (center, normal, u_axis, half_w, half_h, tile).
        """
        h = CELL / 2
        faces = [
            ((0.0, 0.0, 0.0), (0, 1, 0), (1, 0, 0), h, h, "floor"),
            ((0.0, WALL_H, 0.0), (0, -1, 0), (1, 0, 0), h, h, "ceiling"),
        ]
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ch = self.char(gx + dx, gy + dy)
            if ch in WALL_TILES:
                n = (-dx, 0, -dy)
                u = _cross((0, 1, 0), n)
                faces.append(((dx * h, WALL_H / 2, dy * h), n, u, h, WALL_H / 2, WALL_TILES[ch]))
        return faces

    def cell_primitive(self, gx, gy):
        pos, uvs, idx = [], [], []
        n = SUBDIV
        for face in self.cell_faces(gx, gy):
            u0, u1, v0, v1 = tile_uv(face[5])
            p0, p1, p2, p3 = _face_quad(face)  # BL, BR, TR, TL
            base = len(pos) // 3
            for j in range(n + 1):
                t = j / n
                for i in range(n + 1):
                    s = i / n
                    for k in range(3):
                        b = p0[k] + (p1[k] - p0[k]) * s
                        top = p3[k] + (p2[k] - p3[k]) * s
                        pos.append(b + (top - b) * t)
                    uvs += [u0 + (u1 - u0) * s, v1 + (v0 - v1) * t]
            for j in range(n):
                for i in range(n):
                    a = base + j * (n + 1) + i
                    idx += [a, a + 1, a + n + 2, a, a + n + 2, a + n + 1]
        return Primitive(Primitive.MODE_TRIANGLES, pos, idx, uvs=uvs)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _face_quad(face):
    """Corners BL, BR, TR, TL, counter-clockwise seen from the front."""
    c, n, u, hw, hh, _ = face
    v = _cross(n, u)
    return [
        tuple(c[k] + u[k] * hw * su + v[k] * hh * sv for k in range(3))
        for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1))
    ]
