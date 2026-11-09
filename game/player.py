"""Free movement on a grid map: input, look, and wall sliding."""

import math

import pyxel
from pyxel.cube import Vec3

from dungeon import CELL

RADIUS = 22.0  # body radius
EYE_H = 58.0
WALK = 2.4  # units / frame  (1.44 m/s at 60 fps)
RUN = 4.2
STRIDE_WALK = 66.0  # units per footstep: an unhurried 2.2 steps / s
STRIDE_RUN = 78.0  # running: long strides at about 3.3 steps / s
GAIT_EASE = 0.08  # how fast walking and running blend into each other
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
        self.bob = 0.0  # one footstep per pi
        self.bob_amp = 1.8
        self.gait = 0.0  # 0 = walking, 1 = running, blended in between
        self.dip = 0.0  # eye lowered after a hard landing
        self.shake = (0.0, 0.0, 0.0)  # eye offset from screen shake
        self.drag_from = None
        self.can_run = lambda: True  # the world says no when the fighter is worn out

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
            target = 1.0 if pyxel.btn(pyxel.KEY_SHIFT) and self.can_run() else 0.0
            self.gait += (target - self.gait) * GAIT_EASE
            g = self.gait
            speed = WALK + (RUN - WALK) * g
            vx, vz = vx / length * speed, vz / length * speed
            ox, oz = self.x, self.z
            self.x, self.z = self._slide(self.x, self.z, vx, vz)
            stride = STRIDE_WALK + (STRIDE_RUN - STRIDE_WALK) * g
            self.bob += math.hypot(self.x - ox, self.z - oz) * math.pi / stride
            self.bob_amp = 1.8 + (3.4 - 1.8) * g
        else:
            self.gait = 0.0
            # settle the head at the nearest rest point of the bob cycle
            rest = round(self.bob / math.pi) * math.pi
            self.bob += (rest - self.bob) * 0.2

    # ------------------------------------------------------------ collision
    def _slide(self, x, z, vx, vz):
        return move_circle(x, z, vx, vz, RADIUS, self.solid)

    # ------------------------------------------------------------ view
    @property
    def eye(self):
        sx, sy, sz = self.shake
        bob = -abs(math.sin(self.bob)) * self.bob_amp  # the head dips once per step
        return Vec3(self.x + sx, EYE_H + bob - self.dip + sy, self.z + sz)

    @property
    def running(self):
        return self.gait > 0.5

    @property
    def cell(self):
        return int(self.x // CELL), int(self.z // CELL)

    @property
    def facing(self):
        return "NESW"[int(((self.yaw + 45) % 360) // 90)]


def move_circle(x, z, vx, vz, radius, solid):
    """Move a circle with wall sliding; sub-steps keep fast moves from tunneling."""
    steps = max(1, int(math.ceil(max(abs(vx), abs(vz)) / (radius * 0.5))))
    sx, sz = vx / steps, vz / steps
    for _ in range(steps):
        x, z = push_out(x + sx, z + sz, radius, solid)
    return x, z


def push_out(x, z, radius, solid):
    """Push a circle out of the solid cells it overlaps."""
    for _ in range(2):
        for gx in range(int((x - radius) // CELL), int((x + radius) // CELL) + 1):
            for gy in range(int((z - radius) // CELL), int((z + radius) // CELL) + 1):
                if not solid(gx, gy):
                    continue
                cx = min(max(x, gx * CELL), (gx + 1) * CELL)
                cz = min(max(z, gy * CELL), (gy + 1) * CELL)
                dx, dz = x - cx, z - cz
                dist2 = dx * dx + dz * dz
                if dist2 >= radius * radius:
                    continue
                dist = math.sqrt(dist2)
                if dist < 1e-6:
                    continue  # center inside a wall: leave it to the next pass
                push = (radius - dist) / dist
                x += dx * push
                z += dz * push
    return x, z
