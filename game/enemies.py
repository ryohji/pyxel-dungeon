"""Enemies: the skeleton guard's body, animation and behavior."""

import math
import random
from collections import deque

from pyxel.cube import Mat4, Node, Vec3

from dungeon import CELL
from objects import cell_of, facing_yaw
from palette import BLUE_I, EARTH_I, FIRE_I, STONE_I, WHITE
from player import move_circle
from tables import ENEMIES, TUNE



def line_of_sight(solid, x0, z0, x1, z1):
    """True when no solid cell lies on the segment (sampled every 20 units)."""
    dist = math.hypot(x1 - x0, z1 - z0)
    n = max(1, int(dist / 20))
    for i in range(1, n):
        t = i / n
        if solid(*cell_of(x0 + (x1 - x0) * t, z0 + (z1 - z0) * t)):
            return False
    return True


def find_path(solid, start, goal, limit=600):
    """Shortest 4-way path of cells from start to goal (excluding start), or None."""
    if start == goal:
        return []
    prev = {start: None}
    q = deque([start])
    while q and len(prev) < limit:
        cur = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = (cur[0] + dx, cur[1] + dy)
            if nxt in prev or solid(*nxt):
                continue
            prev[nxt] = cur
            if nxt == goal:
                path = [nxt]
                while prev[path[-1]] != start:
                    path.append(prev[path[-1]])
                return path[::-1]
            q.append(nxt)
    return None


class Skeleton:
    KIND = "skeleton"  # its row in data/enemies.csv; apply_tables() sets the numbers below
    # NAME, MAX_HP, RADIUS, WALK, CHASE, SIGHT, LOST_AFTER (frames),
    # REACH (starts an attack within this distance), HIT_RANGE (the blow lands if the party is still this close),
    # WINDUP, STRIKE, RECOVER (frames), DAMAGE (min, max),
    # UNDEAD (light hurts it twice as much), STAGGER (a blow this heavy breaks off its swing)

    def __init__(self, x, z, yaw=0.0):
        self.x, self.z, self.yaw = x, z, yaw
        self.hp = self.MAX_HP
        self.state = "idle"
        self.t = 0  # frames in the current state
        self.walk_phase = 0.0
        self.walk_amount = 0.0
        self.flash = 0
        self.jolt = 0  # frames left shaking from a blow (only the look; the body stays put)
        self.knock = (0.0, 0.0)
        self.cooldown = 0
        self.path = []
        self.path_timer = 0
        self.last_seen = None
        self.lost = 0
        self.rnd = random.Random(int(x * 7 + z * 13))
        self.idle_turn = self.rnd.randint(120, 300)
        self.slow = 0  # frames of moving at half speed (frost)
        self.stun = 0  # frames of standing dazed (light)
        self.node = SkeletonNode(self)

    # ------------------------------------------------------------ queries
    @property
    def alive(self):
        return self.state not in ("dying", "dead")

    @property
    def cell(self):
        return cell_of(self.x, self.z)

    @property
    def center(self):
        return Vec3(self.x, 45, self.z)

    # ------------------------------------------------------------ damage
    @property
    def called(self):
        """Its name in the language in use."""
        from lang import loc
        return loc(ENEMIES[self.KIND], "name")

    def hurt(self, damage, from_x, from_z):
        """Take a hit. Returns True when this blow destroys it."""
        if not self.alive:
            return False
        self.hp -= damage
        self.flash = 6
        d = math.hypot(self.x - from_x, self.z - from_z) or 1.0
        self.knock = ((self.x - from_x) / d * 5, (self.z - from_z) / d * 5)
        if self.hp <= 0:
            self._set("dying")
            return True
        if self.state == "idle":
            self._set("chase")
        elif self.state == "attack" and self.t < self.WINDUP and damage >= self.STAGGER:
            self._set("chase")  # a heavy blow staggers the swing
            self.cooldown = 30
        return False

    def _set(self, state):
        self.state = state
        self.t = 0

    # ------------------------------------------------------------ behavior
    def update(self, floor, world):
        """One frame of thinking and moving. Raises sounds through floor.emit."""
        self.t += 1
        self.flash = max(0, self.flash - 1)
        self.cooldown = max(0, self.cooldown - 1)
        if self.state == "dead":
            return
        if self.state == "dying":
            if self.t == 1:
                floor.emit("collapse", (self.x, self.z))
            if self.t >= 40:
                self._set("dead")
            self.node.refresh()
            return

        self.slow = max(0, self.slow - 1)
        if self.stun > 0:  # dazed: the swing is lost, nothing else happens
            self.stun -= 1
            if self.state == "attack":
                self._set("chase")
                self.cooldown = 20
            self.walk_amount *= 0.85
            self.node.refresh()
            return

        # knockback from the last hit
        kx, kz = self.knock
        if abs(kx) + abs(kz) > 0.1:
            self.x, self.z = move_circle(self.x, self.z, kx, kz, self.RADIUS, floor.enemy_solid)
            self.knock = (kx * 0.7, kz * 0.7)

        p = world.player
        dist = math.hypot(p.x - self.x, p.z - self.z)
        sees = world.party.alive and dist < self.SIGHT and line_of_sight(floor.solid, self.x, self.z, p.x, p.z)
        if sees:
            self.last_seen = (p.x, p.z)
            self.lost = 0
        else:
            self.lost += 1

        moving = False
        if self.state == "idle":
            if sees:
                self._set("chase")
                floor.emit("alert", (self.x, self.z))
            elif self.t % self.idle_turn == 0:
                self.yaw += self.rnd.choice((-90, 90))
        elif self.state == "chase":
            if self.lost > self.LOST_AFTER or self.last_seen is None:
                self._set("idle")
            elif sees and dist < self.REACH and self.cooldown == 0:
                self._set("attack")
            else:
                moving = self._chase(floor, world, sees, dist)
        elif self.state == "attack":
            self._turn_toward(p.x, p.z, 6)
            if self.t == 1:
                floor.emit("enemy_swing", (self.x, self.z))
            if self.t == self.WINDUP + self.STRIKE // 2:
                if sees and dist < self.HIT_RANGE:
                    world.hit_party(self.rnd.randint(*self.DAMAGE), self)
            if self.t >= self.WINDUP + self.STRIKE + self.RECOVER:
                self._set("chase")
                self.cooldown = 24

        target = 1.0 if moving else 0.0
        self.walk_amount += (target - self.walk_amount) * 0.15
        self.node.refresh()

    def _chase(self, floor, world, sees, dist):
        p = world.player
        if sees and dist < CELL * 1.6:
            tx, tz = p.x, p.z
        else:
            self.path_timer -= 1
            goal = cell_of(*self.last_seen)
            if self.path_timer <= 0 or not self.path:
                self.path = find_path(floor.enemy_solid, self.cell, goal) or []
                self.path_timer = 20
            while self.path and self.path[0] == self.cell:
                self.path.pop(0)
            if not self.path:
                if sees:
                    tx, tz = p.x, p.z
                else:
                    tx, tz = self.last_seen
            else:
                gx, gy = self.path[0]
                tx, tz = (gx + 0.5) * CELL, (gy + 0.5) * CELL
        dx, dz = tx - self.x, tz - self.z
        d = math.hypot(dx, dz)
        if d < 4 or (sees and dist < 52):
            self._turn_toward(p.x, p.z, 8)
            return False
        self._turn_toward(tx, tz, 7)
        speed = self.CHASE * (0.45 if self.slow else 1.0)
        self.x, self.z = move_circle(self.x, self.z, dx / d * speed, dz / d * speed, self.RADIUS, floor.enemy_solid)
        self.walk_phase += speed * 0.075
        return True

    def _turn_toward(self, tx, tz, max_deg):
        want = facing_yaw(tx - self.x, tz - self.z)
        diff = (want - self.yaw + 180) % 360 - 180
        self.yaw += max(-max_deg, min(max_deg, diff))


# ---------------------------------------------------------------- drawing
def _swing(deg):
    """Rotate about X so that positive angles carry a hanging limb forward (+Z)."""
    return Mat4.from_euler(Vec3(-deg, 0, 0))


def _t(x, y, z):
    return Mat4.from_translation(Vec3(x, y, z))


def _ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


class SkeletonNode(Node):
    BONE = STONE_I[7]
    BONE_DARK = STONE_I[6]
    BLADE = STONE_I[5]
    HILT = EARTH_I[3]
    EYES = FIRE_I[4]

    def __init__(self, enemy):
        super().__init__()
        self.e = enemy
        self.refresh()

    def refresh(self):
        e = self.e
        self.transform = _t(*self.jolted()) * _t(e.x, 0, e.z) * Mat4.from_euler(Vec3(0, e.yaw, 0))

    def jolted(self):
        """Sideways shake while the action is stopped after a blow: big to small, side to side."""
        e = self.e
        if e.jolt <= 0:
            return 0.0, 0.0, 0.0
        size = TUNE["jolt_size"] * min(1.0, e.jolt / 6) * (1 if e.jolt % 2 else -1)
        yr = math.radians(e.yaw)
        return math.cos(yr) * size, 0.0, math.sin(yr) * size

    def _col(self, c):
        return WHITE if self.e.flash > 0 else c

    def on_draw(self):
        e = self.e
        if e.flash > 0:
            self.shaded(False)
        bone, dark = self._col(self.BONE), self._col(self.BONE_DARK)
        w = e.walk_amount
        ph = e.walk_phase

        # pose parameters
        lean = 0.0
        arm_r = None
        jaw = 0.0
        hip_y = 40.0 - abs(math.sin(ph)) * 2 * w
        fold = 0.0  # 0 standing .. 1 collapsed
        if e.state == "attack":
            if e.t < e.WINDUP:
                k = _ease(e.t / e.WINDUP)
                arm_r, lean, jaw = 165 * k, -8 * k, 3 * k
            elif e.t < e.WINDUP + e.STRIKE:
                k = (e.t - e.WINDUP) / e.STRIKE
                arm_r, lean, jaw = 165 - 150 * k, -8 + 22 * k, 3
            else:
                k = _ease((e.t - e.WINDUP - e.STRIKE) / e.RECOVER)
                arm_r, lean = 15 * (1 - k), 14 * (1 - k)
        if e.flash > 0:
            lean -= 12
        if e.state in ("dying", "dead"):
            fold = 1.0 if e.state == "dead" else _ease(e.t / 40)
            hip_y = 40 - 34 * fold
            lean = -75 * fold

        root = Mat4.IDENTITY
        # pelvis and legs
        self.box(_t(0, hip_y, 0), Vec3(16, 5, 8), bone)
        for side in (1, -1):
            swing = math.sin(ph + (0 if side > 0 else math.pi)) * 28 * w
            knee = -max(0.0, math.sin(ph + (math.pi / 2 if side > 0 else -math.pi / 2))) * 35 * w
            if fold:
                swing, knee = swing * (1 - fold) + 80 * fold, knee * (1 - fold) - 150 * fold
            thigh = _t(side * 5, hip_y, 0) * _swing(swing)
            self.box(thigh * _t(0, -10, 0), Vec3(4, 20, 4), bone)
            shin = thigh * _t(0, -20, 0) * _swing(knee)
            self.box(shin * _t(0, -10, 0), Vec3(3.5, 20, 3.5), dark)
            self.box(shin * _t(0, -20, 2), Vec3(5, 3, 10), dark)

        # spine, ribs, shoulders
        torso = root * _t(0, hip_y, 0) * _swing(lean)
        self.box(torso * _t(0, 9, 0), Vec3(3, 18, 3), dark)
        for y, width in ((13, 14), (18, 17), (23, 18)):
            self.box(torso * _t(0, y, 0), Vec3(width, 2, 10), bone)
        self.box(torso * _t(0, 18, 4.5), Vec3(2, 12, 1.5), bone)
        self.box(torso * _t(0, 28, 0), Vec3(24, 3, 4), bone)

        # skull: it rolls off when the bones collapse
        head = torso * _t(0, 30, 0)
        if fold:
            head = _t(10 * fold, hip_y + 30 * (1 - fold) - 2 * fold, -18 * fold) * Mat4.from_euler(Vec3(0, 0, 70 * fold))
        self.box(head * _t(0, 2, 0), Vec3(3, 4, 3), dark)
        self.box(head * _t(0, 9, 0), Vec3(11, 11, 12), bone)
        self.box(head * _t(0, 3.5 - jaw, 2), Vec3(9, 3, 8), dark)
        if e.state != "dead":
            self.shaded(False)
            for side in (1, -1):
                self.box(head * _t(side * 2.5, 9.5, 6.1), Vec3(2.5, 2.5, 1), self._col(self.EYES))
            self.shaded(e.flash == 0)

        # arms; the right hand holds a rusty blade
        for side in (1, -1):
            if side > 0 and arm_r is not None:
                a, elbow = arm_r, 15
            else:
                a, elbow = -math.sin(ph + (0 if side > 0 else math.pi)) * 22 * w, 20
            if fold:
                a, elbow = a * (1 - fold) - 40 * fold, elbow * (1 - fold) + 60 * fold
            upper = torso * _t(side * 12, 27, 0) * _swing(a)
            self.box(upper * _t(0, -8, 0), Vec3(3.5, 16, 3.5), bone)
            fore = upper * _t(0, -16, 0) * _swing(elbow)
            self.box(fore * _t(0, -7, 0), Vec3(3, 14, 3), dark)
            if side > 0:
                hand = fore * _t(0, -15, 0) * _swing(75)
                self.box(hand, Vec3(6, 2, 2), self._col(self.HILT))
                self.box(hand * _t(0, -15, 0), Vec3(1.5, 28, 4.5), self._col(self.BLADE))


# ---------------------------------------------------------------- guardians
class Guardian(Skeleton):
    """A stone guardian of the old kingdom: slow, tough, hits hard. Wakes as relics are restored."""

    KIND = "guardian"

    def __init__(self, x, z, yaw=0.0):
        super().__init__(x, z, yaw)
        self.node = GuardianNode(self)


class GuardianNode(SkeletonNode):
    BONE = STONE_I[4]
    BONE_DARK = STONE_I[3]
    BLADE = STONE_I[6]
    HILT = STONE_I[2]
    EYES = BLUE_I[2]
    SCALE = 1.35

    def refresh(self):
        e = self.e
        self.transform = _t(*self.jolted()) * _t(e.x, 0, e.z) * Mat4.from_euler(Vec3(0, e.yaw, 0)) * Mat4.from_scale(Vec3(self.SCALE, self.SCALE, self.SCALE))


def apply_tables():
    """Set each enemy kind's numbers from data/enemies.csv (again after a reload)."""
    for cls in (Skeleton, Guardian):
        r = ENEMIES[cls.KIND]
        cls.NAME = r["name"]
        cls.MAX_HP = r["max_hp"]
        cls.RADIUS = float(r["radius"])
        cls.WALK, cls.CHASE = float(r["walk"]), float(r["chase"])
        cls.REACH, cls.HIT_RANGE = float(r["reach"]), float(r["hit_range"])
        cls.WINDUP, cls.STRIKE, cls.RECOVER = r["windup"], r["strike"], r["recover"]
        cls.DAMAGE = (r["damage_min"], r["damage_max"])
        cls.UNDEAD = bool(r["undead"])
        cls.STAGGER = r["stagger"]
        cls.SIGHT = float(r["sight"])
        cls.LOST_AFTER = int(r["lost_after_sec"] * 60)


apply_tables()
