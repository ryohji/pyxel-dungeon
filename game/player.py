"""Free movement on a grid map: input, look, and wall sliding."""

import math

import pyxel
from pyxel.cube import Vec3

from dungeon import CELL

RADIUS = 22.0  # body radius
EYE_H = 58.0
WALK = 2.4  # units / frame  (1.44 m/s at 60 fps)
RUN = 4.2
TURN_KEY = 3.0  # deg / frame
MOUSE_SENS = 0.35  # deg / pixel while dragging
PITCH_LIMIT = 40.0


class Player:
    def __init__(self, start, solid):
        """start = (gx, gy, yaw); solid(gx, gy) tells whether a cell blocks movement."""
        gx, gy, yaw = start
        self.solid = solid
        self.x = (gx + 0.5) * CELL
        self.z = (gy + 0.5) * CELL
        self.yaw = yaw
        self.pitch = 0.0
        self.bob = 0.0
        self.drag_from = None

    # ------------------------------------------------------------ input
    def update(self):
        self._look()
        self._move()

    def _look(self):
        if pyxel.btn(pyxel.KEY_LEFT) or pyxel.btn(pyxel.KEY_Q):
            self.yaw -= TURN_KEY
        if pyxel.btn(pyxel.KEY_RIGHT) or pyxel.btn(pyxel.KEY_E):
            self.yaw += TURN_KEY
        if pyxel.btn(pyxel.KEY_UP):
            self.pitch = min(PITCH_LIMIT, self.pitch + TURN_KEY * 0.6)
        if pyxel.btn(pyxel.KEY_DOWN):
            self.pitch = max(-PITCH_LIMIT, self.pitch - TURN_KEY * 0.6)
        # drag with the right mouse button to look around (works on the Web too)
        if pyxel.btn(pyxel.MOUSE_BUTTON_RIGHT):
            mx, my = pyxel.mouse_x, pyxel.mouse_y
            if self.drag_from is not None:
                self.yaw += (mx - self.drag_from[0]) * MOUSE_SENS
                self.pitch -= (my - self.drag_from[1]) * MOUSE_SENS
                self.pitch = max(-PITCH_LIMIT, min(PITCH_LIMIT, self.pitch))
            self.drag_from = (mx, my)
        else:
            self.drag_from = None
        self.yaw %= 360.0
        if pyxel.btnp(pyxel.KEY_HOME) or pyxel.btnp(pyxel.KEY_R):
            self.pitch = 0.0

    def _move(self):
        yr = math.radians(self.yaw)
        fx, fz = math.sin(yr), -math.cos(yr)
        rx, rz = -fz, fx
        vx = vz = 0.0
        if pyxel.btn(pyxel.KEY_W):
            vx += fx; vz += fz
        if pyxel.btn(pyxel.KEY_S):
            vx -= fx; vz -= fz
        if pyxel.btn(pyxel.KEY_D):
            vx += rx; vz += rz
        if pyxel.btn(pyxel.KEY_A):
            vx -= rx; vz -= rz
        length = math.hypot(vx, vz)
        if length > 0:
            speed = RUN if pyxel.btn(pyxel.KEY_SHIFT) else WALK
            vx, vz = vx / length * speed, vz / length * speed
            ox, oz = self.x, self.z
            self.x, self.z = self._slide(self.x, self.z, vx, vz)
            self.bob += math.hypot(self.x - ox, self.z - oz) * 0.09
        else:
            # settle the head at the nearest rest point of the bob cycle
            rest = round(self.bob / math.pi) * math.pi
            self.bob += (rest - self.bob) * 0.2

    # ------------------------------------------------------------ collision
    def _slide(self, x, z, vx, vz):
        """Move with wall sliding; sub-steps keep fast moves from tunneling."""
        steps = max(1, int(math.ceil(max(abs(vx), abs(vz)) / (RADIUS * 0.5))))
        sx, sz = vx / steps, vz / steps
        for _ in range(steps):
            x, z = self._resolve(x + sx, z + sz)
        return x, z

    def _resolve(self, x, z):
        """Push a circle out of the wall cells it overlaps."""
        for _ in range(2):
            for gx in range(int((x - RADIUS) // CELL), int((x + RADIUS) // CELL) + 1):
                for gy in range(int((z - RADIUS) // CELL), int((z + RADIUS) // CELL) + 1):
                    if not self.solid(gx, gy):
                        continue
                    cx = min(max(x, gx * CELL), (gx + 1) * CELL)
                    cz = min(max(z, gy * CELL), (gy + 1) * CELL)
                    dx, dz = x - cx, z - cz
                    dist2 = dx * dx + dz * dz
                    if dist2 >= RADIUS * RADIUS:
                        continue
                    dist = math.sqrt(dist2)
                    if dist < 1e-6:
                        continue  # center inside a wall: leave it to the next pass
                    push = (RADIUS - dist) / dist
                    x += dx * push
                    z += dz * push
        return x, z

    # ------------------------------------------------------------ view
    @property
    def eye(self):
        return Vec3(self.x, EYE_H + math.sin(self.bob * 2) * 1.6, self.z)

    @property
    def cell(self):
        return int(self.x // CELL), int(self.z // CELL)

    @property
    def facing(self):
        return "NESW"[int(((self.yaw + 45) % 360) // 90)]
