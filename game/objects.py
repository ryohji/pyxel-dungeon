"""Mechanisms and items: their state and their 3D nodes."""

import math

import pyxel
from pyxel.cube import Mat4, Node, Vec3

from dungeon import CELL, SIDES, WALL_H
from palette import BLACK, BLUE_I, EARTH_I, FIRE_I, MOSS_I, RED, STONE_I, WHITE
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
DOOR_LIFT = 0.8  # an open door's panel hangs this far up, its lower edge still in sight


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
        lift = self.door.open * WALL_H * DOOR_LIFT
        self.transform = self.base * Mat4.from_translation(Vec3(0, WALL_H / 2 + lift, 0))

    def on_draw(self):
        self.box(Mat4.IDENTITY, self.size, self.image)
        if self.door.open < 0.97:
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
    """Something set into a wall, usable from every open side: fountain, carving, niche."""

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


class Carving(Fixture):
    """Words and a relief cut into the wall: the old kingdom speaking."""

    KIND = "carving"
    text = ""
    text_ja = ""

    def make_node(self):
        return CarvingNode()


class Niche(Fixture):
    """A sealed niche: relics laid here are buried for good."""

    KIND = "niche"

    def __init__(self, cell, open_sides):
        self.contents = []
        super().__init__(cell, open_sides)

    def make_node(self):
        return NicheNode(self)


class Sconce(Fixture):
    """An iron sconce in the wall. Burning, it keeps the dead in the coffins near it asleep;
    light it from a torch, or light a torch from it."""

    KIND = "sconce"

    def __init__(self, cell, open_sides):
        self.lit = False
        super().__init__(cell, open_sides)

    def make_node(self):
        return SconceNode(self)


class Coffin(Fixture):
    """A coffin in a wall niche of the catacombs. In the dark, its dead climb out."""

    KIND = "coffin"

    def __init__(self, cell, open_sides):
        self.open = False
        super().__init__(cell, open_sides)

    def make_node(self):
        return CoffinNode(self)


class Shelf(Fixture):
    """A shelf of old books in the library. A torch kept near too long sets it alight."""

    KIND = "shelf"
    text = ""
    text_ja = ""

    def __init__(self, cell, open_sides):
        self.burnt = False
        super().__init__(cell, open_sides)

    def make_node(self):
        return ShelfNode(self)


class SconceNode(Node):
    def __init__(self, sconce):
        super().__init__()
        self.sconce = sconce

    def on_draw(self):
        b = self.box
        b(Mat4.from_translation(Vec3(0, 60, 2)), Vec3(12, 28, 4), STONE_I[2])  # the iron plate
        b(Mat4.from_translation(Vec3(0, 54, 10)), Vec3(5, 4, 16), STONE_I[3])  # the arm
        b(Mat4.from_translation(Vec3(0, 58, 18)), Vec3(18, 6, 18), STONE_I[3])  # the cup
        if self.sconce.lit:
            self.shaded(False)
            f = pyxel.frame_count // 5 % 3
            b(Mat4.from_translation(Vec3(0, 70 + f, 18)), Vec3(13, 18 + f * 3, 13), FIRE_I[4])
            b(Mat4.from_translation(Vec3(0, 67, 18)), Vec3(8, 9, 8), FIRE_I[5])
            self.shaded(True)
        else:
            b(Mat4.from_translation(Vec3(0, 61.5, 18)), Vec3(14, 1, 14), BLACK)  # cold soot


class CoffinNode(Node):
    def __init__(self, coffin):
        super().__init__()
        self.coffin = coffin

    def on_draw(self):
        b = self.box
        b(Mat4.from_translation(Vec3(0, 30, 1)), Vec3(80, 52, 2), STONE_I[2])  # the niche frame
        if self.coffin.open:
            b(Mat4.from_translation(Vec3(0, 30, 2)), Vec3(70, 40, 1), BLACK)  # empty and dark
            b(Mat4.from_translation(Vec3(-30, 5, 12)) * Mat4.from_euler(Vec3(0, 0, 70)), Vec3(40, 6, 20), EARTH_I[2])
        else:
            b(Mat4.from_translation(Vec3(0, 30, 3)), Vec3(70, 40, 4), EARTH_I[2])  # the lid
            b(Mat4.from_translation(Vec3(0, 30, 5.5)), Vec3(60, 4, 1), EARTH_I[3])
            b(Mat4.from_translation(Vec3(0, 30, 5.5)), Vec3(4, 30, 1), EARTH_I[3])


class ShelfNode(Node):
    COLORS = (RED, BLUE_I[1], EARTH_I[3], MOSS_I[1], EARTH_I[5], FIRE_I[2])

    def __init__(self, shelf):
        super().__init__()
        self.shelf = shelf

    def on_draw(self):
        b = self.box
        b(Mat4.from_translation(Vec3(0, 48, 2)), Vec3(84, 90, 4), EARTH_I[2])  # the case
        for row, y in enumerate((18, 40, 62, 84)):
            b(Mat4.from_translation(Vec3(0, y - 3, 8)), Vec3(80, 2, 12), EARTH_I[3])
            if self.shelf.burnt:
                b(Mat4.from_translation(Vec3(0, y + 2, 8)), Vec3(76, 6, 10), BLACK)  # ash
                continue
            x = -36
            for k in range(12):
                w = 5 + (row * 7 + k * 3) % 3
                h = 13 + (row + k * 5) % 5
                b(Mat4.from_translation(Vec3(x + w / 2, y + h / 2 - 2, 8)), Vec3(w, h, 10),
                  self.COLORS[(row * 5 + k) % len(self.COLORS)])
                x += w + 1


class CarvingNode(Node):
    def on_draw(self):
        self.box(Mat4.from_translation(Vec3(0, 55, 1)), Vec3(60, 60, 2), STONE_I[2])  # the panel
        self.box(Mat4.from_translation(Vec3(0, 55, 2)), Vec3(54, 54, 1), STONE_I[4])
        # a hill with an eye in its side
        for i, w in enumerate((44, 34, 24, 14)):
            self.box(Mat4.from_translation(Vec3(0, 34 + i * 8, 3)), Vec3(w, 8, 1.5), STONE_I[5])
        self.box(Mat4.from_translation(Vec3(0, 44, 4)), Vec3(12, 6, 1), STONE_I[1])
        self.box(Mat4.from_translation(Vec3(0, 44, 4.5)), Vec3(4, 4, 1), STONE_I[6])
        for x in (-18, -10, 10, 18):  # kneeling figures
            self.box(Mat4.from_translation(Vec3(x, 31, 4)), Vec3(4, 6, 1), STONE_I[6])
        for y in (72, 76, 80):  # a line of old letters
            self.box(Mat4.from_translation(Vec3(0, y, 3)), Vec3(44, 1.5, 1), STONE_I[1])


class NicheNode(Node):
    def __init__(self, niche):
        super().__init__()
        self.niche = niche

    def on_draw(self):
        self.box(Mat4.from_translation(Vec3(0, 52, 1)), Vec3(44, 56, 2), STONE_I[5])  # frame
        self.box(Mat4.from_translation(Vec3(0, 50, 2)), Vec3(32, 44, 1), BLACK)  # the dark inside
        self.box(Mat4.from_translation(Vec3(0, 76, 2)), Vec3(26, 6, 1.5), STONE_I[6])  # lintel
        for x in (-12, 12):  # wax seals
            self.box(Mat4.from_translation(Vec3(x, 30, 3)), Vec3(5, 5, 1), RED)
        if self.niche.contents:  # what was laid here glints faintly
            self.shaded(False)
            for i in range(len(self.niche.contents)):
                self.box(Mat4.from_translation(Vec3(-8 + i * 8, 34, 2.5)), Vec3(4, 3, 1), FIRE_I[3])
            self.shaded(True)


# ---------------------------------------------------------------- the shaft up
PERSON_NAMES = {"scholar": "Vesk, the scholar", "keeper": "the gravekeeper"}


def person_title(who):
    from lang import tr
    return tr(PERSON_NAMES.get(who, who))


class RopeNode(Node):
    """An old shaft up to the camp (H): a knotted rope hanging from the dark."""

    def __init__(self, cell):
        super().__init__()
        x, z = cell_center(cell)
        self.transform = Mat4.from_translation(Vec3(x, 0, z))

    def on_draw(self):
        self.box(Mat4.from_translation(Vec3(0, 100, 0)), Vec3(3, 200, 3), EARTH_I[5])
        for y in range(14, 200, 22):  # knots to climb by
            self.box(Mat4.from_translation(Vec3(0, y, 0)), Vec3(6, 4, 6), EARTH_I[4])
        self.box(Mat4.from_translation(Vec3(0, 2, 0)), Vec3(18, 4, 18), EARTH_I[3])  # a coil on the floor


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
        elif kind in ("torch", "wax_torch"):
            b(_at(0, 2, 0), Vec3(30, 4, 4), EARTH_I[2])
            b(_at(14, 3, 0), Vec3(7, 6, 6), EARTH_I[1] if kind == "torch" else EARTH_I[6])
            if thing.fuel > 0 and not thing.out:
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
        elif kind == "spear":
            b(_at(8, 1.5, 0), Vec3(70, 3, 3), EARTH_I[3])
            b(_at(48, 1.5, 0), Vec3(12, 2, 6), STONE_I[6])
        elif kind == "maul":
            b(_at(-4, 2, 0), Vec3(44, 4, 4), EARTH_I[4])
            b(_at(20, 7, 0), Vec3(12, 14, 20), STONE_I[6])
        elif kind == "bone":
            b(_at(0, 2, 0, 25), Vec3(26, 3, 4), STONE_I[7])
            for dx in (-13, 13):
                b(_at(dx * 0.9, 2.5, dx * 0.42, 25), Vec3(6, 5, 7), STONE_I[7])
        elif kind == "corpse_wax":
            b(_at(0, 4, 0, 15), Vec3(14, 8, 11), EARTH_I[6])
            b(_at(2, 8, 1, 15), Vec3(8, 3, 6), EARTH_I[7])
        elif kind == "drill_book":
            b(_at(0, 2, 0, 10), Vec3(20, 4, 26), FIRE_I[1])
            b(_at(1, 2.2, 0, 10), Vec3(18, 4, 24), EARTH_I[6])
            b(_at(0, 4.3, 0, 10), Vec3(20, 0.5, 26), EARTH_I[3])
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
        elif kind == "relic_shard":
            b(_at(0, 3, 0, 20), Vec3(18, 6, 4), FIRE_I[4])
            for dx in (-6, 0, 6):
                b(_at(dx, 8, 0, 20), Vec3(3, 6, 3), FIRE_I[5])
            b(_at(0, 4, 2.5, 20), Vec3(3, 3, 1), BLUE_I[2])
        elif kind == "relic_seal":
            b(_at(0, 2, 0), Vec3(14, 4, 14), FIRE_I[2])
            b(_at(0, 2, 0, 45), Vec3(14, 3.5, 14), FIRE_I[2])
            b(_at(0, 9, 0), Vec3(5, 10, 5), FIRE_I[3])
        elif kind == "relic_tablet":
            b(_at(0, 4, 0), Vec3(34, 8, 46), STONE_I[4])
            for dz in (-12, -4, 4, 12):
                b(_at(0, 8.2, dz), Vec3(24, 0.5, 2), STONE_I[2])
        elif kind == "relic_chronicle":
            b(_at(0, 1, 0, 8), Vec3(18, 2, 24), EARTH_I[6])
            for dz in (-6, -2, 2, 6):
                b(_at(1, 2.2, dz, 8), Vec3(12, 0.5, 1), EARTH_I[2])
        elif kind == "relic_heart":  # it beats, faintly lit from within
            self.shaded(False)
            pulse = 1 + 0.15 * max(0.0, math.sin(pyxel.frame_count * 0.12)) ** 8
            b(_at(0, 8, 0), Vec3(13 * pulse, 13 * pulse, 13 * pulse), FIRE_I[1])
            b(_at(0, 8, 0, 45), Vec3(9 * pulse, 15 * pulse, 9 * pulse), FIRE_I[2])
            b(_at(0, 9, 4), Vec3(4, 4, 6), FIRE_I[4])
            self.shaded(True)
        else:
            b(_at(0, 5, 0), Vec3(10, 10, 10), 30)


def open_sides(dungeon, cell):
    return [(dx, dy) for dx, dy in SIDES if not dungeon.is_wall(cell[0] + dx, cell[1] + dy)]
