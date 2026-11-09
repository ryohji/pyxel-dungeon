"""First-person view of the dungeon: cell nodes, camera, light falloff."""

import math
import random
from collections import deque

from pyxel.cube import Camera, Mat4, Node, Vec3

from dungeon import CELL
from palette import BLACK, build_band_shadings

BAND = CELL / 2  # distance per light band (one half-step darker each)
MAX_DARK = 4  # bands of darkness with no torch at all


def flicker_band(x, flicker):
    """Light band for a cell at x bands away, shaken by the torch flicker.

    A cell steps one band darker when the flicker exceeds its up-threshold
    and one band brighter below its down-threshold. Cells near a band edge
    react to small flickers; the thresholds never exceed 0.4 one way and
    0.25 the other, so every distance flickers (plain floor(x + flicker)
    left cells with a fractional part of 0.35-0.65 always steady).
    """
    base = math.floor(x)
    f = x - base
    if flicker > 0.1 + 0.3 * (1 - f):
        return base + 1
    if flicker < -(0.1 + 0.3 * f):
        return base - 1
    return base


class CellNode(Node):
    """Floor, ceiling and the walls around one open cell, merged into one Primitive."""

    def __init__(self, prim, atlas):
        super().__init__()
        self.prim_ = prim
        self.atlas = atlas

    def on_draw(self):
        self.prim(Mat4.IDENTITY, self.prim_, self.atlas)


class DungeonView:
    def __init__(self, dungeon, atlas, radius=7.0, fov=70.0, blocks_sight=None):
        self.dungeon = dungeon
        self.blocks_sight = blocks_sight or (lambda gx, gy: False)
        self.extras = {}  # cell -> set of nodes lit and culled with that cell
        self.node_cell = {}
        self.radius = radius
        self.root = Node()
        self.camera = Camera()
        self.camera.fov = fov
        self.camera.near = 5
        self.camera.far = CELL * (radius + 1.5)
        self.camera.clear_color = BLACK
        self.root.camera = self.camera
        self.shadings = build_band_shadings(int(radius * CELL / BAND) + 2 + MAX_DARK)
        self.root.shading = self.shadings[0]

        self.nodes = {}
        for gx, gy in dungeon.open_cells():
            node = CellNode(dungeon.cell_primitive(gx, gy), atlas)
            node.transform = Mat4.from_translation(Vec3((gx + 0.5) * CELL, 0, (gy + 0.5) * CELL))
            node.visible = False
            self.root.add_child(node)
            self.nodes[(gx, gy)] = node
        self.shown = set()
        self.flicker = 0.0
        self.flicker_target = 0.0
        self.rnd = random.Random()
        self.cells_drawn = 0
        self.dark = 0  # extra bands of darkness when the torch is low or gone
        self.flicker_amount = 1.0

    def update(self, eye, yaw, pitch, frame):
        yr, pr = math.radians(yaw), math.radians(pitch)
        fwd = Vec3(math.sin(yr) * math.cos(pr), math.sin(pr), -math.cos(yr) * math.cos(pr))
        self.camera.transform = Mat4.look_at(eye, eye + fwd)
        for sh in self.shadings:
            sh.direction = fwd  # headlamp: light travels along the view

        # torch flicker: drift the light radius a little
        if frame % 6 == 0:
            self.flicker_target = self.rnd.uniform(-0.35, 0.35)
        self.flicker += (self.flicker_target - self.flicker) * 0.3

        visible = self._visible_cells(eye.x, eye.z, math.sin(yr), -math.cos(yr))
        self.cells_drawn = len(visible)
        last_band = len(self.shadings) - 1
        for key, dist in visible.items():
            node = self.nodes[key]
            band = flicker_band(dist / BAND, self.flicker * self.flicker_amount) + self.dark
            node.shading = self.shadings[max(0, min(last_band, band))]
            node.visible = True
            for extra in self.extras.get(key, ()):
                extra.shading = node.shading
                extra.visible = True
        for key in self.shown - visible.keys():
            self.nodes[key].visible = False
            for extra in self.extras.get(key, ()):
                extra.visible = False
        self.shown = set(visible)
        self.root.update()

    def _visible_cells(self, px, pz, fx, fz):
        """Open cells reachable from the player within the radius and roughly in front."""
        d = self.dungeon
        start = (int(px // CELL), int(pz // CELL))
        if d.is_wall(*start):
            return {}
        limit = self.radius * CELL
        out = {}
        seen = {start}
        q = deque([start])
        while q:
            gx, gy = q.popleft()
            dx = (gx + 0.5) * CELL - px
            dz = (gy + 0.5) * CELL - pz
            dist = math.hypot(dx, dz)
            if dist <= CELL * 1.5 or dx * fx + dz * fz >= dist * 0.45:
                out[(gx, gy)] = dist
            if (gx, gy) != start and self.blocks_sight(gx, gy):
                continue  # e.g. a closed door: draw it, but nothing behind
            for nx, ny in ((gx + 1, gy), (gx - 1, gy), (gx, gy + 1), (gx, gy - 1)):
                if (nx, ny) in seen or d.is_wall(nx, ny):
                    continue
                if math.hypot((nx + 0.5) * CELL - px, (ny + 0.5) * CELL - pz) > limit:
                    continue
                seen.add((nx, ny))
                q.append((nx, ny))
        return out

    # ------------------------------------------------------------ extras
    def attach(self, node, cell):
        """Add a node that is shown and lit together with an open cell."""
        if node.parent is None:
            self.root.add_child(node)
        self.move(node, cell)

    def move(self, node, cell):
        old = self.node_cell.get(node)
        if old == cell:
            return
        if old is not None:
            self.extras[old].discard(node)
        self.extras.setdefault(cell, set()).add(node)
        self.node_cell[node] = cell
        node.visible = cell in self.shown
        if node.visible:
            node.shading = self.nodes[cell].shading

    def detach(self, node):
        old = self.node_cell.pop(node, None)
        if old is not None:
            self.extras[old].discard(node)
        if node.parent is not None:
            self.root.remove_child(node)

    def draw(self, x, y, w, h):
        self.root.draw(x, y, w, h)
