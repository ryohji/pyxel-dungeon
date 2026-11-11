"""Mechanisms and items: their state and their 3D nodes."""

import math

from pyxel.cube import Mat4, Node, Vec3

from dungeon import CELL, SIDES, WALL_H
from palette import BLUE_I, EARTH_I, FIRE_I, RED, STONE_I, WHITE
from things import Thing

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


# ---------------------------------------------------------------- wall fixtures
class Fixture:
    """Something set into a wall, usable from every open side: fountain, board, counter."""

    KIND = "fixture"

    def __init__(self, cell, open_sides):
        self.cell = cell
        self.nodes = []
        x, z = cell_center(cell)
        for dx, dy in open_sides:
            node = self.make_node()
            face = Vec3(x + dx * CELL / 2, 0, z + dy * CELL / 2)
            node.transform = Mat4.from_translation(face) * yaw_matrix(facing_yaw(dx, dy))
            self.nodes.append((node, (cell[0] + dx, cell[1] + dy)))

    @property
    def kind(self):
        return self.KIND


class Fountain(Fixture):
    """A basin in a wall: drink from it, or refill a waterskin."""

    KIND = "fountain"

    def make_node(self):
        return FountainNode()


class Board(Fixture):
    """The camp's request board."""

    KIND = "board"

    def make_node(self):
        return BoardNode()


class Counter(Fixture):
    """The camp counter: hand over what you brought back, buy supplies."""

    KIND = "counter"

    def make_node(self):
        return CounterNode()


class BoardNode(Node):
    def on_draw(self):
        self.box(Mat4.from_translation(Vec3(0, 55, 2)), Vec3(64, 44, 4), EARTH_I[3])
        for x in (-34, 34):
            self.box(Mat4.from_translation(Vec3(x, 40, 3)), Vec3(5, 80, 5), EARTH_I[2])
        for i, (x, y, w, h) in enumerate(((-18, 62, 18, 16), (4, 66, 16, 12), (20, 50, 14, 16), (-14, 44, 20, 12))):
            self.box(Mat4.from_translation(Vec3(x, y, 4.5)), Vec3(w, h, 1), (STONE_I[7], EARTH_I[7], STONE_I[6])[i % 3])
            self.box(Mat4.from_translation(Vec3(x, y + h / 2 - 2, 5.5)), Vec3(2, 2, 1), RED)


class CounterNode(Node):
    def on_draw(self):
        self.box(Mat4.from_translation(Vec3(0, 18, 14)), Vec3(80, 36, 26), EARTH_I[2])  # the counter
        self.box(Mat4.from_translation(Vec3(0, 37, 15)), Vec3(86, 4, 30), EARTH_I[4])  # its top
        self.box(Mat4.from_translation(Vec3(-24, 42, 18)), Vec3(12, 8, 12), FIRE_I[2])  # coin box
        self.box(Mat4.from_translation(Vec3(20, 43, 14)), Vec3(14, 10, 10), STONE_I[5])  # scales
        self.box(Mat4.from_translation(Vec3(0, 80, 8)), Vec3(3, 20, 3), STONE_I[3])  # lantern hook
        self.shaded(False)
        self.box(Mat4.from_translation(Vec3(0, 66, 8)), Vec3(8, 10, 8), FIRE_I[5])  # lantern
        self.shaded(True)


class FountainNode(Node):
    def on_draw(self):
        self.box(Mat4.from_translation(Vec3(0, 20, 9)), Vec3(46, 6, 18), STONE_I[4])  # basin rim
        self.box(Mat4.from_translation(Vec3(0, 9, 7)), Vec3(30, 18, 12), STONE_I[3])  # pedestal
        self.box(Mat4.from_translation(Vec3(0, 23.5, 9)), Vec3(38, 1, 13), BLUE_I[1])  # water
        self.box(Mat4.from_translation(Vec3(0, 55, 2)), Vec3(14, 14, 4), STONE_I[2])  # spout face
        self.box(Mat4.from_translation(Vec3(0, 50, 6)), Vec3(4, 4, 8), STONE_I[5])
        self.box(Mat4.from_translation(Vec3(0, 36, 9)), Vec3(2, 24, 2), BLUE_I[2])  # trickle


# ---------------------------------------------------------------- items
class Item:
    """A thing lying on (or flying over) the floor."""

    def __init__(self, thing, x, z, y=0.0, yaw=0.0):
        self.thing = thing if isinstance(thing, Thing) else Thing(thing)
        self.x, self.y, self.z = x, y, z
        self.vx = self.vy = self.vz = 0.0
        self.yaw = yaw
        self.moving = False
        self.node = ItemNode(self)
        self.node.refresh()

    @property
    def kind(self):
        return self.thing.kind

    @property
    def cell(self):
        return cell_of(self.x, self.z)

    @property
    def center(self):
        return Vec3(self.x, self.y + 7, self.z)

    @property
    def name(self):
        return self.thing.name


def _at(x, y, z, deg=0.0):
    m = Mat4.from_translation(Vec3(x, y, z))
    return m * yaw_matrix(deg) if deg else m


class ItemNode(Node):
    def __init__(self, item):
        super().__init__()
        self.item = item

    def refresh(self):
        it = self.item
        self.transform = Mat4.from_translation(Vec3(it.x, it.y, it.z)) * yaw_matrix(it.yaw)

    def on_draw(self):
        thing = self.item.thing
        kind = thing.kind
        b = self.box
        if kind == "rock":
            b(_at(0, 5, 0), Vec3(16, 10, 13), STONE_I[5])
            b(_at(1, 10, -1, 30), Vec3(10, 5, 9), STONE_I[6])
        elif kind == "key_iron":
            c = STONE_I[6]
            b(_at(4, 1.5, 0), Vec3(22, 3, 3), c)
            for dx, dz, sx, sz in ((-12, 0, 3, 11), (-4, 0, 3, 11), (-8, -4, 9, 3), (-8, 4, 9, 3)):
                b(_at(dx, 1.5, dz), Vec3(sx, 3, sz), c)
            for dx in (11, 7):
                b(_at(dx, 1.5, 3), Vec3(2, 3, 5), c)
        elif kind == "torch":
            b(_at(0, 2, 0), Vec3(30, 4, 4), EARTH_I[2])
            b(_at(14, 3, 0), Vec3(7, 6, 6), EARTH_I[1])
            if thing.fuel > 0:
                self.shaded(False)
                b(_at(19, 5, 0), Vec3(6, 8, 6), FIRE_I[5])
                self.shaded(True)
        elif kind == "bread":
            b(_at(0, 4, 0), Vec3(22, 8, 12), EARTH_I[4])
            b(_at(0, 8, 0), Vec3(18, 3, 9), EARTH_I[5])
        elif kind == "waterskin":
            b(_at(0, 6, 0), Vec3(16, 12, 12), EARTH_I[3])
            b(_at(-10, 5, 0), Vec3(6, 4, 4), EARTH_I[2])
            b(_at(-14, 5, 0), Vec3(3, 5, 5), STONE_I[5])
        elif kind in ("dagger", "sword"):
            n = 18 if kind == "dagger" else 36
            b(_at(n / 2 + 4, 1.5, 0), Vec3(n, 2, 5), STONE_I[6])
            b(_at(3, 2, 0), Vec3(3, 3, 14), FIRE_I[2])
            b(_at(-5, 2, 0), Vec3(12, 3, 3), EARTH_I[2])
        elif kind == "buckler":
            b(_at(0, 2, 0), Vec3(22, 4, 22), EARTH_I[3])
            b(_at(0, 2, 0, 45), Vec3(22, 3.5, 22), EARTH_I[3])
            b(_at(0, 5, 0), Vec3(7, 3, 7), STONE_I[6])
        elif kind == "cap":
            b(_at(0, 4, 0), Vec3(18, 8, 18), EARTH_I[3])
            b(_at(0, 9, 0), Vec3(12, 3, 12), EARTH_I[4])
        elif kind == "jerkin":
            b(_at(0, 2, 0), Vec3(26, 4, 24), EARTH_I[3])
            b(_at(0, 2, -15), Vec3(36, 3, 8), EARTH_I[2])
        elif kind == "ring":
            for i in range(6):
                a = i * 60
                b(_at(math.cos(math.radians(a)) * 5, 1, math.sin(math.radians(a)) * 5, -a), Vec3(3, 2, 4), STONE_I[7])
            b(_at(5, 2.5, 0), Vec3(3, 3, 3), BLUE_I[2])
        elif kind == "lantern":
            b(_at(0, 1, 0), Vec3(12, 2, 12), FIRE_I[2])
            b(_at(0, 8, 0), Vec3(9, 12, 9), FIRE_I[3] if thing.fuel <= 0 else FIRE_I[4])
            b(_at(0, 15, 0), Vec3(12, 2, 12), FIRE_I[2])
            b(_at(0, 19, 0), Vec3(2, 6, 2), FIRE_I[2])
        elif kind.startswith("note_"):  # pale paper drawn unshaded so it catches the eye in the dark
            self.shaded(False)
            b(_at(0, 0.5, 0, 12), Vec3(26, 1, 20), STONE_I[7])
            b(_at(-9, 1.0, 9, 12), Vec3(8, 1, 6), WHITE)  # a dog-eared corner
            for dz in (-5, 0, 5):
                b(_at(1, 1.2, dz, 12), Vec3(16, 0.5, 1.5), STONE_I[3])
            self.shaded(True)
            b(_at(9, 3, -6), Vec3(8, 6, 7), STONE_I[4])  # a pebble keeps it from blowing away
        elif kind.startswith("remains_"):
            b(_at(0, 6, 0), Vec3(56, 12, 22), EARTH_I[2])  # wrapped in a cloak
            b(_at(-10, 13, 0), Vec3(30, 4, 16), EARTH_I[3])
            b(_at(32, 8, 0), Vec3(13, 13, 13), STONE_I[7])  # skull
            b(_at(37, 8, 3), Vec3(4, 4, 3), STONE_I[1])
            b(_at(37, 8, -3), Vec3(4, 4, 3), STONE_I[1])
            b(_at(-32, 4, 6), Vec3(10, 6, 6), EARTH_I[1])  # boots
            b(_at(-32, 4, -6), Vec3(10, 6, 6), EARTH_I[1])
        elif kind == "idol":
            b(_at(0, 4, 0), Vec3(22, 8, 22), STONE_I[3])
            b(_at(0, 22, 0), Vec3(16, 28, 14), STONE_I[5])
            b(_at(0, 42, 0), Vec3(14, 12, 12), STONE_I[6])
            b(_at(4, 43, 6.5), Vec3(3, 3, 1), FIRE_I[4])
            b(_at(-4, 43, 6.5), Vec3(3, 3, 1), FIRE_I[4])
        else:
            b(_at(0, 5, 0), Vec3(10, 10, 10), 30)


def open_sides(dungeon, cell):
    return [(dx, dy) for dx, dy in SIDES if not dungeon.is_wall(cell[0] + dx, cell[1] + dy)]
