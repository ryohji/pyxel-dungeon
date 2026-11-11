"""Grid dungeon: ASCII map loading and per-cell geometry.

World axes: +X right (east), +Y up, -Z forward (north).
Grid cell (gx, gy) covers x in [gx, gx+1) * CELL and z in [gy, gy+1) * CELL,
so grid rows grow southward (+Z).

Map characters
  #  stone wall            M  mossy wall          S  wall with a switch
  F  wall with a fountain  B  wall with a request board  C  wall with a counter
  .  floor                 D  door                _  pressure plate
  O  pit                   X  stairs down         U  stairs up
  ^ > v <  player start facing N / E / S / W  (a floor cell)
  (space)  solid rock

Lines starting with ';' are comments. Lines starting with '@' set up
mechanisms (coordinates are gx,gy):
  @link SX,SY TX,TY MODE          switch/plate at S drives door at T;
                                  MODE is toggle, hold, or unlock
  @lock X,Y ITEM                  door at X,Y opens with ITEM
  @item X,Y ITEM                  item lying on the floor
  @enemy X,Y KIND [YAW]           enemy standing in a cell, facing YAW degrees
  @below FLOOR / @above FLOOR     floors reached by pits, X and U
  @lit                            always bright (no torch needed)
"""

from pyxel.cube import Primitive

from textures import tile_uv

CELL = 100.0  # 1 m
WALL_H = 100.0
SUBDIV = 4  # faces are split SUBDIV x SUBDIV to hide affine texture warping

WALL_TILES = {"#": "wall", "M": "wall_moss", "S": "wall", "F": "wall", "B": "wall", "C": "wall", " ": "wall"}
FLOOR_CHARS = set(".D_OXU")
START_YAW = {"^": 0.0, ">": 90.0, "v": 180.0, "<": 270.0}
SIDES = ((1, 0), (-1, 0), (0, 1), (0, -1))


def _xy(s):
    x, y = s.split(",")
    return int(x), int(y)


class Dungeon:
    def __init__(self, text, name=""):
        self.name = name
        self.links = []  # (source, target, mode)
        self.locks = {}  # door cell -> item kind
        self.items = []  # (cell, kind)
        self.enemies = []  # (cell, kind, yaw)
        self.below = self.above = None
        self.lit = False
        rows = []
        for ln in text.splitlines():
            if ln.startswith(";"):
                continue
            if ln.startswith("@"):
                self._meta(ln[1:].split(";")[0].split())
                continue
            rows.append(ln.rstrip("\n"))
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
                elif ch not in WALL_TILES and ch not in FLOOR_CHARS:
                    raise ValueError(f"{name}: unknown map char {ch!r} at {gx},{gy}")

    def _meta(self, words):
        cmd, args = words[0], words[1:]
        if cmd == "link":
            self.links.append((_xy(args[0]), _xy(args[1]), args[2]))
        elif cmd == "lock":
            self.locks[_xy(args[0])] = args[1]
        elif cmd == "item":
            self.items.append((_xy(args[0]), args[1]))
        elif cmd == "enemy":
            self.enemies.append((_xy(args[0]), args[1], float(args[2]) if len(args) > 2 else 0.0))
        elif cmd == "below":
            self.below = args[0]
        elif cmd == "above":
            self.above = args[0]
        elif cmd == "lit":
            self.lit = True
        else:
            raise ValueError(f"unknown map command @{cmd}")

    @classmethod
    def load(cls, path, name=""):
        with open(path, encoding="utf-8") as f:
            return cls(f.read(), name)

    def char(self, gx, gy):
        if 0 <= gx < self.w and 0 <= gy < self.h:
            return self.cells[gy][gx]
        return " "

    def is_wall(self, gx, gy):
        return self.char(gx, gy) in WALL_TILES

    def cells_of(self, chars):
        for gy in range(self.h):
            for gx in range(self.w):
                if self.cells[gy][gx] in chars:
                    yield gx, gy

    def open_cells(self):
        return self.cells_of(FLOOR_CHARS)

    def door_axis(self, gx, gy):
        """'x' when the door panel spans east-west (walls east and west)."""
        return "x" if self.is_wall(gx - 1, gy) and self.is_wall(gx + 1, gy) else "z"

    # ------------------------------------------------------------ geometry
    def cell_faces(self, gx, gy):
        """Faces of an open cell, relative to the cell's floor center.

        Each face is (center, normal, u_axis, half_w, half_h, tile).
        """
        h = CELL / 2
        ch = self.char(gx, gy)
        faces = []
        if ch not in "OX":
            faces.append(((0.0, 0.0, 0.0), (0, 1, 0), (1, 0, 0), h, h, "floor"))
        if ch != "U":
            faces.append(((0.0, WALL_H, 0.0), (0, -1, 0), (1, 0, 0), h, h, "ceiling"))
        for dx, dy in SIDES:
            n = (-dx, 0, -dy)
            u = _cross((0, 1, 0), n)
            other = self.char(gx + dx, gy + dy)
            if other in WALL_TILES:
                faces.append(((dx * h, WALL_H / 2, dy * h), n, u, h, WALL_H / 2, WALL_TILES[other]))
            # shafts: below the floor for pits and stairs down, above for stairs up
            if ch in "OX":
                faces.append(((dx * h, -WALL_H / 2, dy * h), n, u, h, WALL_H / 2, "shaft"))
            if ch == "U":
                faces.append(((dx * h, WALL_H * 1.5, dy * h), n, u, h, WALL_H / 2, "shaft"))
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
