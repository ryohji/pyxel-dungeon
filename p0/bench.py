"""P0 bench: render a grid dungeon with Pyxel Cube and measure frame cost.

Usage:
  python bench.py [--mode cell|single|plane] [--radius R] [--bands 0|1]
                  [--frames N] [--interactive] [--shot PATH] [--size WxH]

  cell   : one Node per open cell, each drawing one merged Primitive.
           Distance falloff by swapping each cell node's Shading.
  single : one Node draws a Primitive per visible cell (no per-cell falloff).
  plane  : one Node calls plane() per face (Python loop per face).
"""

import math
import random
import sys
import time

import pyxel
from pyxel.cube import Camera, Mat4, Node, Primitive, Shading, Vec3

# ---------------------------------------------------------------- options
ARGS = {
    "mode": "cell",
    "radius": "6",
    "bands": "1",
    "frames": "600",
    "size": "320x240",
    "shot": "",
    "interactive": False,
    "fov": "70",
    "subdiv": "1",
}


def parse_args(argv):
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--interactive":
            ARGS["interactive"] = True
        elif a.startswith("--"):
            ARGS[a[2:]] = argv[i + 1]
            i += 1
        i += 1


parse_args(sys.argv[1:])
WEB = sys.platform == "emscripten"
MODE = ARGS["mode"]
RADIUS = float(ARGS["radius"])  # visible radius in cells
BANDS = ARGS["bands"] == "1"
FRAMES = int(ARGS["frames"])
W, H = (int(v) for v in ARGS["size"].split("x"))
INTERACTIVE = ARGS["interactive"]
SUBDIV = int(ARGS["subdiv"])  # split each face into SUBDIV x SUBDIV quads

CELL = 100.0  # 1 m
WALL_H = 100.0
EYE_H = 55.0

# ---------------------------------------------------------------- palette
# 32 colors: black + ramps (dark -> bright).
STONE = [0x0E0D12, 0x1C1B24, 0x2B2A35, 0x3D3C48, 0x52515E, 0x6A6976, 0x85848F, 0xA3A2AB]
EARTH = [0x120C08, 0x23170F, 0x352317, 0x4A3120, 0x60412A, 0x785436, 0x926A45, 0xAE8358]
FIRE = [0x3A0E06, 0x6E1E0A, 0xA8380E, 0xD9621A, 0xF29A2E, 0xFFD25A]
MOSS = [0x1A2412, 0x2E3F1E, 0x4A6230]
BLUE = [0x101B33, 0x22355E, 0x3E5E96]
MISC = [0xF2EEE6, 0xC23B3B, 0x7A2F8F]
PALETTE = [0x000000] + STONE + EARTH + FIRE + MOSS + BLUE + MISC
assert len(PALETTE) == 32

RAMPS = []
_i = 1
for ramp in (STONE, EARTH, FIRE, MOSS, BLUE):
    RAMPS.append(list(range(_i, _i + len(ramp))))
    _i += len(ramp)
STONE_I, EARTH_I, FIRE_I = RAMPS[0], RAMPS[1], RAMPS[2]


def build_band_shadings(n_bands):
    """Shading per distance band. Band 0 = brightest.

    Brightness is measured in half-steps along each color's ramp; odd
    half-steps become 2x2 dither pairs. Each band darkens by 2 half-steps.
    """
    ramp_of = {0: ([0], 0)}
    for ramp in RAMPS:
        for pos, c in enumerate(ramp):
            ramp_of[c] = (ramp, pos)
    shadings = []
    for band in range(n_bands):
        sh = Shading(pyxel.colors)
        for c in range(len(PALETTE)):
            ramp, pos = ramp_of.get(c, ([c], 0))
            for level in range(Shading.LEVEL_COUNT):
                # level 5 = original color; each level = 1 half-step
                hs = pos * 2 + (level - 5) - band * 2
                if hs < 0:
                    pair = (0, ramp[0]) if hs == -1 else (0, 0)
                else:
                    lo = min(hs // 2, len(ramp) - 1)
                    hi = min(lo + (hs % 2), len(ramp) - 1)
                    pair = (ramp[lo], ramp[hi])
                sh[c, level] = pair
        shadings.append(sh)
    return shadings


# ---------------------------------------------------------------- textures
TEX = 32


def make_atlas():
    img = pyxel.Image(TEX * 3, TEX)
    rnd = random.Random(1)
    # wall: stone bricks
    img.rect(0, 0, TEX, TEX, STONE_I[2])
    for row in range(4):
        y = row * 8
        off = 0 if row % 2 == 0 else 8
        for col in range(-1, 3):
            x = col * 16 + off
            shade = STONE_I[rnd.choice((4, 5, 5, 6))]
            img.rect(max(0, x + 1), y + 1, min(15, TEX - x - 1), 7, shade)
            for _ in range(3):
                img.pset(rnd.randrange(TEX), y + 1 + rnd.randrange(7), STONE_I[3])
    # floor: flagstones
    ox = TEX
    img.rect(ox, 0, TEX, TEX, EARTH_I[2])
    for (x, y, w, h) in ((1, 1, 14, 14), (17, 1, 14, 10), (17, 12, 14, 19), (1, 16, 14, 15)):
        img.rect(ox + x, y, w, h, EARTH_I[rnd.choice((4, 5))])
        for _ in range(4):
            img.pset(ox + x + rnd.randrange(w), y + rnd.randrange(h), EARTH_I[3])
    # ceiling: rough dark stone
    ox = TEX * 2
    img.rect(ox, 0, TEX, TEX, STONE_I[2])
    for _ in range(80):
        img.pset(ox + rnd.randrange(TEX), rnd.randrange(TEX), STONE_I[rnd.choice((1, 3))])
    return img


def tile_uv(tile):
    eps = 0.5 / (TEX * 3)
    u0 = tile / 3 + eps
    u1 = (tile + 1) / 3 - eps
    return u0, u1, 0.5 / TEX, 1 - 0.5 / TEX


# ---------------------------------------------------------------- map
def make_map(w=40, h=40, seed=7):
    rnd = random.Random(seed)
    grid = [[1] * w for _ in range(h)]
    rooms = []
    for _ in range(60):
        rw, rh = rnd.randint(3, 7), rnd.randint(3, 7)
        x, y = rnd.randint(1, w - rw - 2), rnd.randint(1, h - rh - 2)
        if any(x <= ox + ow and ox <= x + rw and y <= oy + oh and oy <= y + rh for ox, oy, ow, oh in rooms):
            continue
        rooms.append((x, y, rw, rh))
        for yy in range(y, y + rh):
            for xx in range(x, x + rw):
                grid[yy][xx] = 0
    centers = [(x + rw // 2, y + rh // 2) for x, y, rw, rh in rooms]
    for (ax, ay), (bx, by) in zip(centers, centers[1:]):
        for xx in range(min(ax, bx), max(ax, bx) + 1):
            grid[ay][xx] = 0
        for yy in range(min(ay, by), max(ay, by) + 1):
            grid[yy][bx] = 0
    return grid, centers


GRID, CENTERS = make_map()
GH, GW = len(GRID), len(GRID[0])


def is_wall(gx, gy):
    return gx < 0 or gy < 0 or gx >= GW or gy >= GH or GRID[gy][gx] == 1


# ---------------------------------------------------------------- geometry
UP = (0.0, 1.0, 0.0)


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def cell_faces(gx, gy):
    """Faces of one open cell as (center, normal, u_axis, half_w, half_h, tile)."""
    cx, cz = (gx + 0.5) * CELL, (gy + 0.5) * CELL
    h = CELL / 2
    faces = [
        ((cx, 0.0, cz), (0, 1, 0), (1, 0, 0), h, h, 1),  # floor
        ((cx, WALL_H, cz), (0, -1, 0), (1, 0, 0), h, h, 2),  # ceiling
    ]
    # grid y grows toward +z
    for dx, dy, n in ((1, 0, (-1, 0, 0)), (-1, 0, (1, 0, 0)), (0, 1, (0, 0, -1)), (0, -1, (0, 0, 1))):
        if is_wall(gx + dx, gy + dy):
            c = (cx + dx * h, WALL_H / 2, cz + dy * h)
            u = cross(UP, n)
            faces.append((c, n, u, h, WALL_H / 2, 0))
    return faces


def face_quad(face):
    c, n, u, hw, hh, tile = face
    v = cross(n, u)
    p = []
    for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        p.append((c[0] + u[0] * hw * su + v[0] * hh * sv,
                  c[1] + u[1] * hw * su + v[1] * hh * sv,
                  c[2] + u[2] * hw * su + v[2] * hh * sv))
    return p


def cell_primitive(gx, gy, origin):
    """Merged primitive of one cell. Faces are split into SUBDIV x SUBDIV
    quads to hide affine texture warping."""
    pos, uvs, idx = [], [], []
    n = SUBDIV
    for face in cell_faces(gx, gy):
        u0, u1, v0, v1 = tile_uv(face[5])
        p0, p1, p2, p3 = face_quad(face)  # BL, BR, TR, TL
        base = len(pos) // 3
        for j in range(n + 1):
            t = j / n  # bottom -> top
            for i in range(n + 1):
                s_ = i / n  # left -> right
                for k in range(3):
                    b = p0[k] + (p1[k] - p0[k]) * s_
                    tp = p3[k] + (p2[k] - p3[k]) * s_
                    pos.append(b + (tp - b) * t - (origin[k] if k != 1 else 0))
                uvs += [u0 + (u1 - u0) * s_, v1 + (v0 - v1) * t]
        for j in range(n):
            for i in range(n):
                a = base + j * (n + 1) + i
                b, c, d = a + 1, a + n + 2, a + n + 1
                idx += [a, b, c, a, c, d]
    return Primitive(Primitive.MODE_TRIANGLES, pos, idx, uvs=uvs)


# ---------------------------------------------------------------- nodes
class CellNode(Node):
    def __init__(self, gx, gy, atlas):
        super().__init__()
        self.gx, self.gy = gx, gy
        self.center = ((gx + 0.5) * CELL, 0.0, (gy + 0.5) * CELL)
        self.prim_ = cell_primitive(gx, gy, self.center)
        self.transform = Mat4.from_translation(Vec3(*self.center))
        self.atlas = atlas

    def on_draw(self):
        self.prim(Mat4.IDENTITY, self.prim_, self.atlas)


class SingleNode(Node):
    """Draws every visible cell's primitive from one on_draw."""

    def __init__(self, atlas):
        super().__init__()
        self.atlas = atlas
        self.cells = {}
        for gy in range(GH):
            for gx in range(GW):
                if not is_wall(gx, gy):
                    self.cells[(gx, gy)] = (cell_primitive(gx, gy, (0, 0, 0)), len(cell_faces(gx, gy)))
        self.visible_cells = []

    def on_draw(self):
        for key in self.visible_cells:
            self.prim(Mat4.IDENTITY, self.cells[key][0], self.atlas)


class PlaneNode(Node):
    """Calls plane() for every face of every visible cell."""

    def __init__(self, atlas):
        super().__init__()
        self.atlas = atlas
        self.cells = {}
        for gy in range(GH):
            for gx in range(GW):
                if not is_wall(gx, gy):
                    lst = []
                    for f in cell_faces(gx, gy):
                        c, n, u, hw, hh, tile = f
                        v = cross(n, u)
                        m = Mat4()
                        # columns u, v, n, c
                        m = mat_from_axes(u, v, n, c)
                        u0, u1, v0, v1 = tile_uv(tile)
                        lst.append((m, ((u0, v0), (u1, v0), (u0, v1), (u1, v1)), hw * 2, hh * 2))
                    self.cells[(gx, gy)] = lst
        self.visible_cells = []

    def on_draw(self):
        for key in self.visible_cells:
            for m, uvs, w, h in self.cells[key]:
                self.plane(m, self.atlas, uvs, w, h)


def mat_from_axes(u, v, n, c):
    yaw_pitch = Mat4.look_at(Vec3(0, 0, 0), Vec3(-n[0], -n[1], -n[2]), Vec3(*v) if abs(n[1]) < 0.5 else Vec3(0, 0, -1))
    # look_at gives a camera-style matrix whose -Z points at target; we want +Z = n.
    return Mat4.from_translation(Vec3(*c)) * Mat4.from_quat(yaw_pitch.rot)


# ---------------------------------------------------------------- camera path
def bfs_path(start, goal):
    from collections import deque

    prev = {start: None}
    q = deque([start])
    while q:
        cur = q.popleft()
        if cur == goal:
            break
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = cur[0] + dx, cur[1] + dy
            if not is_wall(nx, ny) and (nx, ny) not in prev:
                prev[(nx, ny)] = cur
                q.append((nx, ny))
    path, cur = [], goal
    while cur is not None:
        path.append(cur)
        cur = prev.get(cur)
    return path[::-1]


def tour():
    pts = []
    for a, b in zip(CENTERS, CENTERS[1:] + CENTERS[:1]):
        seg = bfs_path(a, b)
        pts += seg[:-1]
    return [((x + 0.5) * CELL, (y + 0.5) * CELL) for x, y in pts]


# ---------------------------------------------------------------- app
class App:
    def __init__(self):
        pyxel.init(W, H, title="P0 bench", fps=60)
        pyxel.colors[:] = PALETTE
        self.atlas = make_atlas()
        self.root = Node()
        self.cam = Camera()
        self.cam.fov = float(ARGS["fov"])
        self.cam.near = 5
        self.cam.far = CELL * (RADIUS + 1)
        self.cam.clear_color = 0
        self.root.camera = self.cam
        n_bands = max(1, int(RADIUS)) + 1 if BANDS else 1
        self.shadings = build_band_shadings(n_bands)
        self.root.shading = self.shadings[0]

        self.cell_nodes = {}
        if MODE == "cell":
            for gy in range(GH):
                for gx in range(GW):
                    if not is_wall(gx, gy):
                        node = CellNode(gx, gy, self.atlas)
                        self.root.add_child(node)
                        self.cell_nodes[(gx, gy)] = node
        elif MODE == "single":
            self.drawer = SingleNode(self.atlas)
            self.root.add_child(self.drawer)
        else:
            self.drawer = PlaneNode(self.atlas)
            self.root.add_child(self.drawer)

        self.path = tour()
        self.path_t = 0.0
        x, z = self.path[0]
        self.px, self.pz = x, z
        self.yaw = 0.0
        self.pitch = 0.0
        self.samples_u, self.samples_d = [], []
        self.faces_drawn = 0
        self.cells_drawn = 0
        self.frame = 0
        self.intervals = []
        self.last_draw = None
        if INTERACTIVE:
            pyxel.mouse(False)
        pyxel.run(self.update, self.draw)

    # --- movement
    def auto_move(self):
        speed = 2.0  # units/frame = 1.2 m/s at 60fps
        self.path_t = (self.path_t + speed / CELL) % len(self.path)
        i = int(self.path_t)
        f = self.path_t - i
        ax, az = self.path[i]
        bx, bz = self.path[(i + 1) % len(self.path)]
        self.px, self.pz = ax + (bx - ax) * f, az + (bz - az) * f
        cx, cz = self.path[(i + 2) % len(self.path)]
        target_yaw = math.degrees(math.atan2(cx - self.px, -(cz - self.pz)))
        d = (target_yaw - self.yaw + 180) % 360 - 180
        self.yaw += d * 0.08

    def manual_move(self):
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        self.yaw += (mx - W // 2) * 0.3
        self.pitch = max(-60, min(60, self.pitch - (my - H // 2) * 0.3))
        pyxel.set_mouse_pos(W // 2, H // 2)
        fwd = (math.sin(math.radians(self.yaw)), -math.cos(math.radians(self.yaw)))
        right = (-fwd[1], fwd[0])
        vx = vz = 0.0
        if pyxel.btn(pyxel.KEY_W):
            vx += fwd[0]; vz += fwd[1]
        if pyxel.btn(pyxel.KEY_S):
            vx -= fwd[0]; vz -= fwd[1]
        if pyxel.btn(pyxel.KEY_D):
            vx += right[0]; vz += right[1]
        if pyxel.btn(pyxel.KEY_A):
            vx -= right[0]; vz -= right[1]
        sp = 3.0
        self.px, self.pz = slide(self.px, self.pz, vx * sp, vz * sp, 20.0)

    def update(self):
        t0 = time.perf_counter()
        if INTERACTIVE:
            self.manual_move()
            if pyxel.btnp(pyxel.KEY_ESCAPE):
                pyxel.quit()
        else:
            self.auto_move()
        self.update_camera_and_visibility()
        self.root.update()
        self.samples_u.append(time.perf_counter() - t0)

    def update_camera_and_visibility(self):
        yr, pr = math.radians(self.yaw), math.radians(self.pitch)
        fwd = Vec3(math.sin(yr) * math.cos(pr), math.sin(pr), -math.cos(yr) * math.cos(pr))
        eye = Vec3(self.px, EYE_H, self.pz)
        self.cam.transform = Mat4.look_at(eye, eye + fwd)
        # headlamp: light travels along view direction
        for sh in self.shadings:
            sh.direction = fwd

        gx0, gy0 = int(self.px // CELL), int(self.pz // CELL)
        r = int(math.ceil(RADIUS))
        fx, fz = math.sin(yr), -math.cos(yr)
        visible = []
        for gy in range(gy0 - r, gy0 + r + 1):
            for gx in range(gx0 - r, gx0 + r + 1):
                if is_wall(gx, gy):
                    continue
                dx = (gx + 0.5) * CELL - self.px
                dz = (gy + 0.5) * CELL - self.pz
                dist = math.hypot(dx, dz)
                if dist > RADIUS * CELL:
                    continue
                # crude horizontal frustum test (keep cells near the player)
                if dist > CELL * 1.5 and (dx * fx + dz * fz) < dist * 0.3:
                    continue
                visible.append(((gx, gy), dist))
        self.cells_drawn = len(visible)
        if MODE == "cell":
            vis_keys = set()
            for key, dist in visible:
                vis_keys.add(key)
                node = self.cell_nodes[key]
                band = min(len(self.shadings) - 1, int(dist / CELL)) if BANDS else 0
                node.shading = self.shadings[band]
            for key, node in self.cell_nodes.items():
                node.visible = key in vis_keys
            self.faces_drawn = sum(len(cell_faces(*k)) for k, _ in visible)
        else:
            self.drawer.visible_cells = [k for k, _ in visible]
            self.faces_drawn = sum(len(cell_faces(*k)) for k, _ in visible)

    def draw(self):
        t0 = time.perf_counter()
        if self.last_draw is not None:
            self.intervals.append(t0 - self.last_draw)
        self.last_draw = t0
        self.root.draw(0, 0, W, H)
        dt = time.perf_counter() - t0
        self.samples_d.append(dt)
        pyxel.text(4, 4, f"{MODE} s{SUBDIV} r{RADIUS:g} cells{self.cells_drawn} faces{self.faces_drawn}", 30)
        u = self.samples_u[-1] * 1000 if self.samples_u else 0
        pyxel.text(4, 12, f"upd {u:4.1f}ms draw {dt*1000:4.1f}ms", 30)
        self.frame += 1
        if ARGS["shot"] and self.frame == 120:
            pyxel.screen.save(ARGS["shot"], 2)
        if not INTERACTIVE and self.frame == FRAMES:
            self.result = report(self)
            if not WEB:
                pyxel.quit()
        if getattr(self, "result", None):
            pyxel.rect(0, 18, W, 40, 0)
            y = 20
            for part in self.result.split(" | "):
                pyxel.text(4, y, part[:78], 30)
                y += 8
            pyxel.text(4, y, "DONE", 30)


def slide(px, pz, vx, vz, r):
    nx = px + vx
    if collides(nx, pz, r):
        nx = px
    nz = pz + vz
    if collides(nx, nz, r):
        nz = pz
    return nx, nz


def collides(x, z, r):
    for gx in range(int((x - r) // CELL), int((x + r) // CELL) + 1):
        for gy in range(int((z - r) // CELL), int((z + r) // CELL) + 1):
            if is_wall(gx, gy):
                cx = min(max(x, gx * CELL), (gx + 1) * CELL)
                cz = min(max(z, gy * CELL), (gy + 1) * CELL)
                if (x - cx) ** 2 + (z - cz) ** 2 < r * r:
                    return True
    return False


def report(app):
    def stats(xs):
        xs = sorted(xs[60:])  # skip warm-up
        n = len(xs)
        return sum(xs) / n * 1000, xs[int(n * 0.95)] * 1000, xs[-1] * 1000

    au, pu, mu = stats(app.samples_u)
    ad, pd, md = stats(app.samples_d)
    ai, pi, mi = stats(app.intervals)
    line = (f"RESULT mode={MODE} subdiv={SUBDIV} radius={RADIUS:g} bands={int(BANDS)} size={W}x{H} "
            f"update avg={au:.2f} p95={pu:.2f} max={mu:.2f} ms | "
            f"draw avg={ad:.2f} p95={pd:.2f} max={md:.2f} ms | "
            f"interval avg={ai:.2f} p95={pi:.2f} ms (fps {1000 / ai:.1f})")
    print(line, flush=True)
    return line


App()
