"""Enemies: the skeleton guard, the stone guardian, the moths that put out flames, and the Lord of the Tombs."""

import math
import random
from collections import deque

from pyxel.cube import Mat4, Node, Vec3

from dungeon import CELL
from objects import cell_of, facing_yaw
from palette import BLUE_I, EARTH_I, FIRE_I, MOSS_I, STONE_I, WHITE
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


# ---------------------------------------------------------------- moths
class Moth(Skeleton):
    """A swarm of grey moths: it never bites, but flies to every flame and smothers it.
    Burning sconces first, then the party's torch."""

    KIND = "moth"
    DOUSE_REST = 300  # frames it flutters about after putting out a flame

    def __init__(self, x, z, yaw=0.0):
        super().__init__(x, z, yaw)
        self.home = (x, z)
        self.goal = None  # ('sconce', Sconce) or ('party', None)
        self.rest = 0
        self.node = MothNode(self)

    @property
    def center(self):
        return Vec3(self.x, 72, self.z)

    def hurt(self, damage, from_x, from_z):
        if not self.alive:
            return False
        self.hp -= damage
        self.flash = 6
        if self.hp <= 0:
            self._set("dying")
            return True
        self.rest = max(self.rest, 40)  # scattered for a moment
        return False

    def _pick_goal(self, floor, world):
        best, best_d = None, self.SIGHT
        for sc in floor.lit_sconces():
            x, z = floor.sconce_point(sc)
            d = math.hypot(x - self.x, z - self.z)
            if d < best_d:
                best, best_d = ("sconce", sc), d
        p = world.player
        if world.party.light > 0 and not world.travel:
            d = math.hypot(p.x - self.x, p.z - self.z) * 1.5  # a still flame on the wall draws them first
            if d < best_d:
                best = ("party", None)
        return best

    def _goal_point(self, floor, world):
        kind, sc = self.goal
        if kind == "party":
            return world.player.x, world.player.z
        return floor.sconce_point(sc)

    def update(self, floor, world):
        self.t += 1
        self.flash = max(0, self.flash - 1)
        if self.state == "dead":
            return
        if self.state == "dying":
            if self.t >= 30:
                self._set("dead")
            self.node.refresh()
            return
        self.walk_phase += 0.5
        if self.stun > 0:
            self.stun -= 1
            self.node.refresh()
            return
        if self.rest > 0:
            self.rest -= 1
            hx, hz = self.home
            a = self.t * 0.05
            self._fly_to(floor, hx + math.cos(a) * 40, hz + math.sin(a) * 40, self.WALK)
            self.node.refresh()
            return
        if self.goal is None or self.t % 30 == 0:
            self.goal = self._pick_goal(floor, world)
            if self.goal is not None and self.state == "idle":
                self._set("chase")
        if self.goal is None:
            self.node.refresh()
            return
        kind, sc = self.goal
        if (kind == "sconce" and not sc.lit) or (kind == "party" and world.party.light <= 0):
            self.goal = None
            return
        tx, tz = self._goal_point(floor, world)
        if kind == "party" and world.party.flame <= 0 and math.hypot(tx - self.x, tz - self.z) < 90:
            # a Light ward cannot be put out: they flutter round it, as moths do round a lamp
            if not world.moths_told:
                world.moths_told = True
                world.messages.add(tr_("Moths flutter round the magic light. They cannot put it out."))
            a = self.t * 0.08 + id(self) % 7
            self._fly_to(floor, tx + math.cos(a) * 55, tz + math.sin(a) * 55, self.CHASE * 0.6)
            self.node.refresh()
            return
        if math.hypot(tx - self.x, tz - self.z) < 45:
            if kind == "sconce":
                sc.lit = False
                floor.emit("fizzle", (tx, tz), 0.8)
                if math.hypot(tx - world.player.x, tz - world.player.z) < 600:
                    world.messages.add(tr_("Moths swarm over a sconce and smother its flame."))
            else:
                world.douse_torches()
            self.home = (self.x, self.z)
            self.goal = None
            self.rest = self.DOUSE_REST
            return
        goal_cell = cell_of(tx, tz)
        if line_of_sight(floor.solid, self.x, self.z, tx, tz):
            nx, nz = tx, tz
        else:
            self.path_timer -= 1
            if self.path_timer <= 0 or not self.path:
                self.path = find_path(floor.enemy_solid, self.cell, goal_cell) or []
                self.path_timer = 20
            while self.path and self.path[0] == self.cell:
                self.path.pop(0)
            if not self.path:
                nx, nz = tx, tz
            else:
                nx, nz = (self.path[0][0] + 0.5) * CELL, (self.path[0][1] + 0.5) * CELL
        self._fly_to(floor, nx, nz, self.CHASE * (0.45 if self.slow else 1.0))
        self.node.refresh()

    def _fly_to(self, floor, tx, tz, speed):
        dx, dz = tx - self.x, tz - self.z
        d = math.hypot(dx, dz)
        if d < 1:
            return
        step = min(speed, d)
        self.x, self.z = move_circle(self.x, self.z, dx / d * step, dz / d * step, self.RADIUS, floor.solid)
        self._turn_toward(tx, tz, 12)


def tr_(text):
    from lang import tr
    return tr(text)


class MothNode(Node):
    def __init__(self, moth):
        super().__init__()
        self.e = moth
        self.refresh()

    def refresh(self):
        e = self.e
        self.transform = _t(e.x, 0, e.z)

    def on_draw(self):
        e = self.e
        if e.state == "dead":
            return
        n = 9
        if e.state == "dying":
            n = max(0, 9 - e.t // 3)
        col = WHITE if e.flash > 0 else STONE_I[7]
        self.shaded(False)  # pale wings catch any light
        for i in range(n):
            a = e.walk_phase * (0.6 + 0.1 * i) + i * 0.9
            r = 12 + (i * 7) % 20
            x, z = math.cos(a) * r, math.sin(a * 1.3) * r
            y = 72 + math.sin(a * 2.1 + i) * 9 - (e.t * 2 if e.state == "dying" else 0) * 0.5
            flap = 9 if (pyxel_frame() + i) % 4 < 2 else 3
            self.box(_t(x, y, z), Vec3(flap * 2, 2, 7), col)
            self.box(_t(x, y, z), Vec3(3, 3, 5), EARTH_I[3])
        self.shaded(True)


def pyxel_frame():
    import pyxel
    return pyxel.frame_count


# ---------------------------------------------------------------- the Lord of the Tombs
class Lord(Skeleton):
    """The master of the catacombs. Blades only bite as far as the four sconces of its hall burn,
    and it goes to put them out."""

    KIND = "lord"
    DOUSE_EVERY = 540  # frames between its walks to a burning sconce

    def __init__(self, x, z, yaw=0.0):
        super().__init__(x, z, yaw)
        self.node = LordNode(self)
        self.sconces = []  # the hall's sconces, set by the floor
        self.floor = None
        self.douse_timer = self.DOUSE_EVERY
        self.target = None

    @property
    def center(self):
        return Vec3(self.x, 70, self.z)

    def lit(self):
        return sum(sc.lit for sc in self.sconces)

    def guard(self, amount):
        """How much of a blow gets through: a quarter for every burning sconce of the hall."""
        return round(amount * self.lit() / max(1, len(self.sconces)))

    def update(self, floor, world):
        if self.state in ("chase", "idle") and self.alive and not self.stun:
            self.douse_timer -= 1
            burning = [sc for sc in self.sconces if sc.lit]
            if self.target is None and self.douse_timer <= 0 and burning and self.state == "chase":
                self.target = min(burning, key=lambda sc: math.dist(floor.sconce_point(sc), (self.x, self.z)))
            if self.target is not None:
                self.t += 1
                self.flash = max(0, self.flash - 1)
                tx, tz = floor.sconce_point(self.target)
                if not self.target.lit:
                    self.target, self.douse_timer = None, self.DOUSE_EVERY
                elif math.hypot(tx - self.x, tz - self.z) < 60:
                    self.target.lit = False
                    floor.emit("fizzle", (tx, tz))
                    world.messages.add(tr_("The Lord of the Tombs puts out a sconce of its hall."))
                    self.target, self.douse_timer = None, self.DOUSE_EVERY
                else:
                    self._turn_toward(tx, tz, 6)
                    dx, dz = tx - self.x, tz - self.z
                    d = math.hypot(dx, dz)
                    self.x, self.z = move_circle(self.x, self.z, dx / d * self.CHASE, dz / d * self.CHASE,
                                                 self.RADIUS, floor.enemy_solid)
                    self.walk_phase += self.CHASE * 0.075
                    self.walk_amount += (1 - self.walk_amount) * 0.15
                self.node.refresh()
                return
        super().update(floor, world)


class LordNode(SkeletonNode):
    BONE = STONE_I[6]
    BONE_DARK = STONE_I[4]
    BLADE = STONE_I[7]
    HILT = FIRE_I[2]
    EYES = MOSS_I[2]
    SCALE = 1.6

    def refresh(self):
        e = self.e
        s = self.SCALE
        self.transform = (_t(*self.jolted()) * _t(e.x, 0, e.z) * Mat4.from_euler(Vec3(0, e.yaw, 0))
                          * Mat4.from_scale(Vec3(s, s, s)))

    def on_draw(self):
        e = self.e
        ghost = e.alive and e.lit() == 0  # with its hall dark, it is a shade the blade cannot touch
        self.BONE, self.BONE_DARK = (BLUE_I[2], BLUE_I[1]) if ghost else (STONE_I[6], STONE_I[4])
        super().on_draw()
        if e.state in ("dying", "dead"):
            return
        torso = _t(0, 40, 0)
        for x in (-6, 0, 6):  # a crown of iron spikes
            self.box(torso * _t(x, 44, 0), Vec3(2.5, 7, 2.5), FIRE_I[2])


def apply_tables():
    """Set each enemy kind's numbers from data/enemies.csv (again after a reload)."""
    for cls in (Skeleton, Guardian, Moth, Lord):
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
