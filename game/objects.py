"""Mechanisms and items: their state and their 3D nodes."""

import math

from pyxel.cube import Mat4, Node, Vec3

from dungeon import CELL, SIDES, WALL_H
from palette import FIRE_I, STONE_I

DOOR_SPEED = 1 / 30  # fraction per frame
ITEM_RADIUS = 14.0  # pick radius around an item's center


def cell_center(cell):
    return (cell[0] + 0.5) * CELL, (cell[1] + 0.5) * CELL


def cell_of(x, z):
    return int(x // CELL), int(z // CELL)


def yaw_matrix(deg):
    return Mat4.from_euler(Vec3(0, deg, 0))


def facing_yaw(nx, nz):
    """Y rotation that turns local +Z toward (nx, 0, nz)."""
    return math.degrees(math.atan2(nx, nz))


# ---------------------------------------------------------------- doors
class Door:
    def __init__(self, cell, axis, lock, image):
        self.cell = cell
        self.axis = axis  # 'x': panel spans east-west
        self.lock = lock  # item kind needed, or None
        self.controlled = False  # driven by a switch or plate only
        self.open = 0.0
        self.target_open = False
        self.motion = 0  # +1 opening, -1 closing, 0 still
        self.node = DoorNode(self, image)

    @property
    def blocks_move(self):
        return self.open < 0.8

    @property
    def blocks_sight(self):
        return self.open < 0.05

    def update(self, occupied):
        """Move the panel; return 'door_open' / 'door_close' when it starts moving."""
        before = self.open
        if self.target_open:
            self.open = min(1.0, self.open + DOOR_SPEED)
        elif not occupied:  # a door never closes on someone
            self.open = max(0.0, self.open - DOOR_SPEED)
        motion = (self.open > before) - (self.open < before)
        started = motion != 0 and motion != self.motion
        self.motion = motion
        self.node.refresh()
        if started:
            return "door_open" if motion > 0 else "door_close"
        return None


class DoorNode(Node):
    def __init__(self, door, image):
        super().__init__()
        self.door = door
        self.image = image
        x, z = cell_center(door.cell)
        self.base = Mat4.from_translation(Vec3(x, 0, z))
        self.size = Vec3(CELL, WALL_H, 8) if door.axis == "x" else Vec3(8, WALL_H, CELL)
        self.refresh()

    def refresh(self):
        lift = self.door.open * WALL_H * 0.96
        self.transform = self.base * Mat4.from_translation(Vec3(0, WALL_H / 2 + lift, 0))

    def on_draw(self):
        if self.door.open < 0.97:
            self.box(Mat4.IDENTITY, self.size, self.image)
            if self.door.lock is not None:  # brass lock plate on both faces
                lock = Vec3(10, 14, 12) if self.door.axis == "x" else Vec3(12, 14, 10)
                self.box(Mat4.from_translation(Vec3(0, -6, 0)), lock, FIRE_I[2])


# ---------------------------------------------------------------- switches
class Switch:
    """A lever on a wall cell, reachable from every open side."""

    def __init__(self, cell, open_sides):
        self.cell = cell
        self.on = False
        self.targets = []  # (door, mode)
        self.nodes = []
        x, z = cell_center(cell)
        for dx, dy in open_sides:
            node = LeverNode(self)
            face = Vec3(x + dx * CELL / 2, 55, z + dy * CELL / 2)
            node.transform = Mat4.from_translation(face) * yaw_matrix(facing_yaw(dx, dy))
            self.nodes.append((node, (cell[0] + dx, cell[1] + dy)))

    def toggle(self):
        self.on = not self.on
        for door, mode in self.targets:
            if mode == "unlock":
                door.lock = None
                door.target_open = True
            else:
                door.target_open = not door.target_open


class LeverNode(Node):
    def __init__(self, switch):
        super().__init__()
        self.switch = switch
        self.angle = 40.0

    def on_update(self):
        target = -40.0 if self.switch.on else 40.0
        self.angle += (target - self.angle) * 0.3

    def on_draw(self):
        self.box(Mat4.from_translation(Vec3(0, 0, 2)), Vec3(26, 38, 4), STONE_I[1])
        self.box(Mat4.from_translation(Vec3(0, 0, 3)), Vec3(8, 26, 4), STONE_I[0])
        pivot = Mat4.from_translation(Vec3(0, 0, 5)) * Mat4.from_euler(Vec3(-self.angle, 0, 0))
        self.box(pivot * Mat4.from_translation(Vec3(0, 0, 10)), Vec3(4, 4, 20), STONE_I[6])
        self.box(pivot * Mat4.from_translation(Vec3(0, 0, 21)), Vec3(8, 8, 8), FIRE_I[3])


# ---------------------------------------------------------------- plates
class Plate:
    def __init__(self, cell):
        self.cell = cell
        self.pressed = False
        self.targets = []  # (door, mode)
        self.node = PlateNode(self)

    def set_pressed(self, pressed):
        if pressed == self.pressed:
            return False
        self.pressed = pressed
        for door, mode in self.targets:
            if mode == "hold":
                door.target_open = pressed
            elif pressed:  # toggle on each press
                door.target_open = not door.target_open
        return True


class PlateNode(Node):
    def __init__(self, plate):
        super().__init__()
        self.plate = plate
        x, z = cell_center(plate.cell)
        self.transform = Mat4.from_translation(Vec3(x, 0, z))

    def on_draw(self):
        h = 1.0 if self.plate.pressed else 3.0
        self.box(Mat4.from_translation(Vec3(0, h / 2, 0)), Vec3(64, h, 64), STONE_I[5])


# ---------------------------------------------------------------- stairs
class StairsNode(Node):
    """Steps inside a stairs cell: going down (X) or up (U)."""

    def __init__(self, cell, down):
        super().__init__()
        self.down = down
        x, z = cell_center(cell)
        self.transform = Mat4.from_translation(Vec3(x, 0, z))

    def on_draw(self):
        for i in range(4):
            depth = CELL / 4
            zc = -CELL / 2 + depth * (i + 0.5)
            if self.down:
                top = -(i + 1) * 24.0
                self.box(Mat4.from_translation(Vec3(0, top - 10, zc)), Vec3(CELL, 20, depth), STONE_I[4])
            else:
                h = (i + 1) * 25.0
                self.box(Mat4.from_translation(Vec3(0, h / 2, -zc)), Vec3(CELL, h, depth), STONE_I[4])


# ---------------------------------------------------------------- items
ITEM_NAMES = {"rock": "a rock", "key_iron": "an iron key"}


class Item:
    def __init__(self, kind, x, z, y=0.0, yaw=0.0):
        self.kind = kind
        self.x, self.y, self.z = x, y, z
        self.vx = self.vy = self.vz = 0.0
        self.yaw = yaw
        self.moving = False
        self.node = ItemNode(self)
        self.node.refresh()

    @property
    def cell(self):
        return cell_of(self.x, self.z)

    @property
    def center(self):
        return Vec3(self.x, self.y + 7, self.z)

    @property
    def name(self):
        return ITEM_NAMES.get(self.kind, self.kind)


class ItemNode(Node):
    def __init__(self, item):
        super().__init__()
        self.item = item

    def refresh(self):
        it = self.item
        self.transform = Mat4.from_translation(Vec3(it.x, it.y, it.z)) * yaw_matrix(it.yaw)

    def on_draw(self):
        kind = self.item.kind
        if kind == "rock":
            self.box(Mat4.from_translation(Vec3(0, 5, 0)), Vec3(16, 10, 13), STONE_I[5])
            self.box(Mat4.from_translation(Vec3(1, 10, -1)) * Mat4.from_euler(Vec3(0, 30, 0)),
                     Vec3(10, 5, 9), STONE_I[6])
        elif kind == "key_iron":
            c = STONE_I[6]
            self.box(Mat4.from_translation(Vec3(4, 1.5, 0)), Vec3(22, 3, 3), c)
            for dx, dz, sx, sz in ((-12, 0, 3, 11), (-4, 0, 3, 11), (-8, -4, 9, 3), (-8, 4, 9, 3)):
                self.box(Mat4.from_translation(Vec3(dx, 1.5, dz)), Vec3(sx, 3, sz), c)
            for dx in (11, 7):
                self.box(Mat4.from_translation(Vec3(dx, 1.5, 3)), Vec3(2, 3, 5), c)
        else:
            self.box(Mat4.from_translation(Vec3(0, 5, 0)), Vec3(10, 10, 10), 30)


def open_sides(dungeon, cell):
    return [(dx, dy) for dx, dy in SIDES if not dungeon.is_wall(cell[0] + dx, cell[1] + dy)]
