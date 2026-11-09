"""Floors, the player's hand, combat, picking, and floor-to-floor travel."""

import math
import os
import random

import pyxel
from pyxel.cube import Vec3

from dungeon import CELL, WALL_H, Dungeon
from enemies import Skeleton, line_of_sight
from objects import (ITEM_RADIUS, Door, Fountain, Item, Plate, StairsNode, Switch, cell_center, cell_of,
                     open_sides)
from party import SWORD_REACH, Party
from player import RADIUS as PLAYER_RADIUS
from player import Player, move_circle
from tables import TUNE
from textures import tile_image
from view import MAX_DARK, DungeonView

HERE = os.path.dirname(os.path.abspath(__file__))
REACH = 175.0  # how far the hand reaches from the eye
GRAVITY = 0.35  # units / frame^2 for thrown items
THROW_SPEED = 7.5
FALL_FRAMES = 18  # fade out and in when changing floors
STAIRS_HOLD = 46  # frames of darkness while walking the stairs (the steps keep walking pace)
WIPE_FRAMES = 90  # darkness after the party falls, before trying the floor again
ENEMY_KINDS = {"skeleton": Skeleton}
ENEMY_PICK_RADIUS = 26.0
TARGET_RANGE = 7 * CELL  # Tab reaches enemies this far away
ACTIONS = {"item": "take", "switch": "pull", "door": "open / close", "enemy": "attack", "fountain": "drink"}


class Hit:
    def __init__(self, kind, t, point=None, obj=None, cell=None):
        self.kind = kind  # item, enemy, switch, door, floor, wall, none
        self.t = t
        self.point = point
        self.obj = obj
        self.cell = cell


class Floor:
    def __init__(self, name, atlas, door_image, peaceful=False):
        self.name = name
        self.d = Dungeon.load(os.path.join(HERE, "maps", f"{name}.txt"), name)
        d = self.d
        self.doors = {c: Door(c, d.door_axis(*c), d.locks.get(c), door_image) for c in d.cells_of("D")}
        self.switches = {c: Switch(c, open_sides(d, c)) for c in d.cells_of("S")}
        self.fountains = {c: Fountain(c, open_sides(d, c)) for c in d.cells_of("F")}
        self.plates = {c: Plate(c) for c in d.cells_of("_")}
        for src, tgt, mode in d.links:
            source = self.switches.get(src) or self.plates.get(src)
            door = self.doors.get(tgt)
            if source is None or door is None:
                raise ValueError(f"{name}: bad link {src} -> {tgt}")
            source.targets.append((door, mode))
            door.controlled = True

        self.view = DungeonView(d, atlas, blocks_sight=self.blocks_sight)
        for door in self.doors.values():
            self.view.attach(door.node, door.cell)
        for wall in (*self.switches.values(), *self.fountains.values()):
            for node, cell in wall.nodes:
                self.view.attach(node, cell)
        for plate in self.plates.values():
            self.view.attach(plate.node, plate.cell)
        for c in d.cells_of("XU"):
            self.view.attach(StairsNode(c, d.char(*c) == "X"), c)

        rnd = random.Random(hash(name) & 0xFFFF)
        self.events = []  # (sound name, (x, z), volume) raised during update
        self.hits = []  # (enemy, (from x, z), thing) struck by thrown things during update
        self.items = []
        for cell, kind in d.items:
            x, z = cell_center(cell)
            self.add_item(Item(kind, x + rnd.uniform(-20, 20), z + rnd.uniform(-20, 20), yaw=rnd.uniform(0, 360)))
        self.enemies = []
        for cell, kind, yaw in ([] if peaceful else d.enemies):
            enemy = ENEMY_KINDS[kind](*cell_center(cell), yaw)
            self.enemies.append(enemy)
            self.view.attach(enemy.node, enemy.cell)
        self.bolts = []

    def add_bolt(self, bolt):
        self.bolts.append(bolt)
        self.view.attach(bolt.node, bolt.cell)

    # ------------------------------------------------------------ queries
    def solid(self, gx, gy):
        if self.d.is_wall(gx, gy):
            return True
        door = self.doors.get((gx, gy))
        return door is not None and door.blocks_move

    def enemy_solid(self, gx, gy):
        """Enemies also keep out of pits and stairwells."""
        return self.solid(gx, gy) or self.d.char(gx, gy) in "OXU"

    def blocks_sight(self, gx, gy):
        door = self.doors.get((gx, gy))
        return door is not None and door.blocks_sight

    def add_item(self, item):
        self.items.append(item)
        item.node.refresh()
        self.view.attach(item.node, item.cell)

    def remove_item(self, item):
        self.items.remove(item)
        self.view.detach(item.node)

    # ------------------------------------------------------------ update
    def update(self, player_cell, messages):
        resting = {it.cell for it in self.items if not it.moving}
        for plate in self.plates.values():
            pressed = plate.cell == player_cell or plate.cell in resting
            if plate.set_pressed(pressed):
                self.emit("plate_down" if pressed else "plate_up", cell_center(plate.cell))
                if pressed:
                    messages.add("Click.")
        for door in self.doors.values():
            sound = door.update(door.cell == player_cell or door.cell in resting)
            if sound:
                self.emit(sound, cell_center(door.cell))
        fallen = []
        for it in list(self.items):
            if it.moving and self._step_item(it):
                fallen.append(it)
        return fallen

    def emit(self, name, pos, volume=1.0):
        self.events.append((name, pos, volume))

    def _step_item(self, it):
        """Advance a thrown item. Returns True when it drops to the floor below."""
        it.vy -= GRAVITY
        steps = max(1, int(math.ceil(max(abs(it.vx), abs(it.vz)) / 10)))
        knock = 0.0
        for _ in range(steps):
            nx = it.x + it.vx / steps
            if self.solid(*cell_of(nx, it.z)):
                knock = max(knock, abs(it.vx))
                it.vx *= -0.4
            else:
                it.x = nx
            nz = it.z + it.vz / steps
            if self.solid(*cell_of(it.x, nz)):
                knock = max(knock, abs(it.vz))
                it.vz *= -0.4
            else:
                it.z = nz
        if knock > 1.0:
            self.emit("knock", (it.x, it.z), min(1.0, knock / 6))
        if math.hypot(it.vx, it.vz) > 2.0:
            for e in self.enemies:
                if e.alive and math.hypot(it.x - e.x, it.z - e.z) < e.RADIUS + 6 and it.y < 80:
                    self.hits.append((e, (it.x - it.vx, it.z - it.vz), it.thing))
                    it.vx, it.vz = -it.vx * 0.25, -it.vz * 0.25
                    break
        it.y += it.vy
        if it.y > WALL_H - 12:
            it.y, it.vy = WALL_H - 12, -abs(it.vy) * 0.5
        hole = self.d.char(*it.cell) in "OX"
        if hole:
            if it.y < -WALL_H * 0.6:
                return True
        elif it.y <= 0:
            if it.vy < -1.5:
                self.emit("thud", (it.x, it.z), min(1.0, -it.vy / 7))
            it.y = 0.0
            it.vy = -it.vy * 0.3
            it.vx *= 0.6
            it.vz *= 0.6
            it.yaw += it.vx * 3
            if abs(it.vy) < 1.0 and math.hypot(it.vx, it.vz) < 0.5:
                it.vx = it.vy = it.vz = 0.0
                it.moving = False
        it.node.refresh()
        self.view.move(it.node, it.cell)
        return False


class Messages:
    LIFETIME = 240

    def __init__(self):
        self.lines = []

    def add(self, text):
        self.lines.append((text, pyxel.frame_count))
        self.lines = self.lines[-3:]

    def visible(self):
        now = pyxel.frame_count
        return [(t, now - f) for t, f in self.lines if now - f < self.LIFETIME]


class World:
    def __init__(self, atlas, w, h, sfx, peaceful=False):
        self.sfx = sfx
        self.peaceful = peaceful  # no enemies (for puzzle tests)
        self.party = Party()
        self.atlas = atlas
        self.door_image = tile_image(atlas, "door")
        self.w, self.h = w, h
        self.floors = {}
        self.floor = self.get_floor("floor1")
        self.player = Player(self.floor.d.start, self.floor.solid)
        self.hand = None  # the Thing held in the cursor, or None
        self.messages = Messages()
        self.explored = {}  # floor name -> set of cells
        self.arrived_on = None  # stairs cell we arrived on; ignored until we step off
        self.travel = None  # [frame, target floor, message, how]
        self.hover = None
        self.shake = 0.0  # screen shake strength, decays every frame
        self.last_step = 0
        self.rnd = random.Random()
        self.swing = 0  # frames left of the sword-swing overlay
        self.popups = []  # [world pos, text, age, color]
        self.wipe = None  # frames since the party fell
        self.hurt_flash = 0
        self.entry = None
        self.mode = "mouse"  # which device picks the target: the one used last
        self.key_target = None  # Hit chosen with Tab
        self.key_pick = None  # (kind, obj) of that choice, to follow it across frames
        self.player.can_run = lambda: not self.party.fighter.tired
        self._remember_entry()

    def get_floor(self, name):
        if name not in self.floors:
            self.floors[name] = Floor(name, self.atlas, self.door_image, self.peaceful)
        return self.floors[name]

    def _remember_entry(self):
        """What to go back to if the party falls on this floor."""
        p = self.player
        self.entry = dict(floor=self.floor.name, x=p.x, z=p.z, yaw=p.yaw,
                          party=self.party.snapshot(), hand=self.hand and self.hand.copy(),
                          arrived_on=self.arrived_on)

    # ------------------------------------------------------------ frame
    def update(self, mx, my, clicked, attack_key=False, tab=False, mouse_moved=False):
        """One frame. attack_key: Space (act on the target); tab: pick the next target."""
        self.party.tick()
        self.party.needs(self.messages)
        self.swing = max(0, self.swing - 1)
        self.hurt_flash = max(0, self.hurt_flash - 1)
        if clicked or mouse_moved:
            self.mode = "mouse"
        if self.wipe is not None:
            self._update_wipe()
        elif self.travel is not None:
            self._update_travel()
        else:
            p = self.player
            ox, oz = p.x, p.z
            p.update()
            if p.running and (p.x, p.z) != (ox, oz):
                f = self.party.fighter
                f.stamina = max(0.0, f.stamina - TUNE["stamina_run"] / 60)
            self._keep_apart()
            self._check_cell_events()
            self.hover = self.pick(mx, my)
            if tab:
                self._next_target(self.mode == "keys")
                self.mode = "keys"
            elif self.mode == "keys":
                self._next_target(False)
            if clicked:
                self.click(self.hover)
            if attack_key:
                self.act()
        p = self.player
        if self.wipe is None:
            self._update_combat()
        for it in self.floor.update(p.cell, self.messages):
            self.floor.remove_item(it)
            below = self.get_floor(self.floor.d.below)
            it.y, it.vy = WALL_H * 0.9, 0.0
            below.add_item(it)
        for name, pos, volume in self.floor.events:
            self.sfx.play(name, volume, math.hypot(pos[0] - p.x, pos[1] - p.z))
        self.floor.events.clear()
        self._footsteps()
        self.sfx.ambience()
        self._update_shake()
        yaw, pitch = p.yaw, p.pitch
        if self.shake > 0:
            yaw += self.rnd.uniform(-1, 1) * self.shake * 1.5
            pitch += self.rnd.uniform(-1, 1) * self.shake * 2.5
        light = self.party.light
        view = self.floor.view
        view.dark = MAX_DARK if light <= 0 else round((1 - light) * 4)
        view.flicker_amount = 1.0 if light > 0 else 0.2
        view.update(p.eye, yaw, pitch, pyxel.frame_count)
        self.explored.setdefault(self.floor.name, set()).update(self.floor.view.shown)
        for pop in self.popups:
            pop[2] += 1
        self.popups = [pop for pop in self.popups if pop[2] < 45]

    # ------------------------------------------------------------ combat
    def _update_combat(self):
        fl = self.floor
        for e in fl.enemies:
            e.update(fl, self)
            fl.view.move(e.node, e.cell)
        for bolt in list(fl.bolts):
            hit = bolt.step(fl)
            if hit is None:
                fl.view.move(bolt.node, bolt.cell)
                continue
            fl.bolts.remove(bolt)
            fl.view.detach(bolt.node)
            fl.emit("bolt_hit", (bolt.pos.x, bolt.pos.z))
            if hit != "wall":
                self._damage_enemy(hit, bolt.damage, bolt.pos.x - bolt.vel.x, bolt.pos.z - bolt.vel.z,
                                   bolt.caster, "wizard")
        f = self.party.fighter
        for e, (fx, fz), thing in fl.hits:
            row = thing.row
            amount = self.rnd.randint(row["throw_min"], row["throw_max"]) + f.bonus("dex", "dex_per_throw", "ninja")
            self.award(f, "ninja", TUNE["xp_throw"])
            self._damage_enemy(e, amount, fx, fz, f, "ninja")
        fl.hits.clear()
        if self.party.alive:
            self.party.companion(self, fl)

    def _keep_apart(self):
        """Bodies do not overlap: push the player out of living enemies."""
        p = self.player
        for e in self.floor.enemies:
            if not e.alive:
                continue
            dx, dz = p.x - e.x, p.z - e.z
            d = math.hypot(dx, dz)
            gap = PLAYER_RADIUS + e.RADIUS
            if 1e-6 < d < gap:
                push = gap - d
                p.x, p.z = move_circle(p.x, p.z, dx / d * push, dz / d * push, PLAYER_RADIUS, self.floor.solid)

    def _enemy_in_front(self):
        p = self.player
        yr = math.radians(p.yaw)
        fx, fz = math.sin(yr), -math.cos(yr)
        best, best_d = None, SWORD_REACH
        for e in self.floor.enemies:
            dx, dz = e.x - p.x, e.z - p.z
            d = math.hypot(dx, dz)
            if e.alive and d < best_d and dx * fx + dz * fz > d * 0.6:
                best, best_d = e, d
        return best

    def attack(self, enemy):
        """Swing the weapon in Arn's right hand (or a fist), hitting enemy if it is within reach."""
        f = self.party.fighter
        if not f.up or f.cooldown:
            return
        tired = f.tired
        f.stamina = max(0.0, f.stamina - TUNE["stamina_swing"])
        f.busy(max(12, TUNE["swing_cooldown"] - (f.level["fighter"] - 1) * TUNE["swing_cooldown_per_level"]))
        self.swing = 12
        self.sfx.play("swing")
        p = self.player
        if enemy is not None and enemy.alive and math.hypot(enemy.x - p.x, enemy.z - p.z) <= SWORD_REACH:
            weapon = f.equip["right"]
            if weapon is not None and weapon.row["damage_max"] > 0:
                lo, hi = weapon.row["damage_min"], weapon.row["damage_max"]
            else:
                lo, hi = TUNE["fist_min"], TUNE["fist_max"]
            amount = self.rnd.randint(lo, hi) + f.bonus("str", "str_per_damage", "fighter")
            if tired:
                amount = max(1, amount // 2)
            self._damage_enemy(enemy, amount, p.x, p.z, f, "fighter")

    def _damage_enemy(self, enemy, amount, from_x, from_z, by=None, skill=None):
        killed = enemy.hurt(amount, from_x, from_z)
        self.sfx.play("hit_bone", 1.0, math.hypot(enemy.x - self.player.x, enemy.z - self.player.z))
        self._popup(enemy.center + Vec3(0, 25, 0), str(amount), 1)
        if killed:
            self.messages.add(f"The {enemy.NAME} falls apart.")
        if by is not None:
            self.award(by, skill, amount * TUNE["xp_hit"] + (TUNE["xp_kill"] if killed else 0))

    def award(self, member, skill, xp):
        """Experience for a skill; announce any level reached."""
        if xp <= 0:
            return
        for lv in member.gain_xp(skill, xp):
            self.messages.add(f"{member.name} is now a level {lv} {skill}!")
            self.sfx.play("levelup")

    def _popup(self, pos, text, kind):
        self.popups.append([pos, text, 0, kind])

    def hit_party(self, amount, enemy):
        """An enemy's blow lands on the front member."""
        m = self.party.front()
        m.damage(max(1, amount - m.defense))
        self.sfx.play("hurt")
        self.shake = max(self.shake, 0.35)
        self.hurt_flash = 8
        if not m.up:
            self.messages.add(f"{m.name} falls!")
        if not self.party.alive:
            self.wipe = 0
            self.sfx.play("defeat")
            self.messages.add("The party has fallen...")

    def _update_wipe(self):
        self.wipe += 1
        if self.wipe == WIPE_FRAMES:
            self._restart_floor()
        elif self.wipe >= WIPE_FRAMES + FALL_FRAMES:
            self.wipe = None

    def _restart_floor(self):
        """Back to the moment the party entered this floor, with the floor as it was then."""
        e = self.entry
        self.floors.pop(e["floor"], None)
        self.floor = self.get_floor(e["floor"])
        p = self.player
        p.solid = self.floor.solid
        p.x, p.z, p.yaw, p.pitch = e["x"], e["z"], e["yaw"], 0.0
        p.dip, self.shake = 0.0, 0.0
        self.party.restore(e["party"])
        self.hand = e["hand"] and e["hand"].copy()
        self.arrived_on = e["arrived_on"]
        self.swing = 0
        self.popups.clear()
        self.messages.add("You wake at the floor's entrance.")

    def _footsteps(self):
        step = int(self.player.bob / math.pi)
        if step != self.last_step:
            kind = "run" if self.player.running else "step"
            self.sfx.play(f"{kind}{step % 2}", self.rnd.uniform(0.75, 1.0))
            self.last_step = step

    def _update_shake(self):
        p = self.player
        if self.shake > 0.02:
            a = self.shake * 7
            p.shake = (self.rnd.uniform(-a, a), self.rnd.uniform(-a, a) * 0.6, self.rnd.uniform(-a, a))
            self.shake *= 0.9
        else:
            self.shake = 0.0
            p.shake = (0.0, 0.0, 0.0)
        p.dip *= 0.9

    def _check_cell_events(self):
        p = self.player
        cell = p.cell
        if self.arrived_on is not None and cell != self.arrived_on:
            self.arrived_on = None
        ch = self.floor.d.char(*cell)
        cx, cz = cell_center(cell)
        near_center = math.hypot(p.x - cx, p.z - cz)
        if ch == "O" and near_center < 36:
            self._start_travel(self.floor.d.below, "You fall through a pit!", "fall")
        elif ch == "X" and near_center < 30 and cell != self.arrived_on:
            self._start_travel(self.floor.d.below, "You go down the stairs.", "stairs_down")
        elif ch == "U" and near_center < 30 and cell != self.arrived_on:
            self._start_travel(self.floor.d.above, "You climb the stairs.", "stairs_up")

    def _start_travel(self, target, message, how):
        if target is None:
            return
        self.travel = [0, target, message, how]
        self.sfx.play(how)

    def _travel_hold(self):
        return 0 if self.travel[3] == "fall" else STAIRS_HOLD

    def _update_travel(self):
        self.travel[0] += 1
        frame, target, message, how = self.travel
        if frame == FALL_FRAMES:
            self.floor = self.get_floor(target)
            p = self.player
            p.solid = self.floor.solid
            cx, cz = cell_center(p.cell)
            if how == "fall":
                self.sfx.play("land")
                self.shake = 1.0
                p.dip = 30.0  # knocked to the ground, then getting up
            else:
                p.x, p.z = cx, cz
                self.arrived_on = p.cell
            self.messages.add(message)
            self._remember_entry()
        elif frame >= FALL_FRAMES * 2 + self._travel_hold():
            self.travel = None

    @property
    def fade(self):
        """0 = clear, 1 = black."""
        if self.wipe is not None:
            w = self.wipe
            if w < WIPE_FRAMES:
                return min(1.0, w / 50)
            return 1 - (w - WIPE_FRAMES) / FALL_FRAMES
        if self.travel is None:
            return 0.0
        f = self.travel[0]
        if f <= FALL_FRAMES:
            return f / FALL_FRAMES
        return min(1.0, 2 - (f - self._travel_hold()) / FALL_FRAMES)

    # ------------------------------------------------------------ hand
    def click(self, hit):
        near = hit.t <= REACH
        if self.hand is None:
            if hit.kind == "enemy":
                self.attack(hit.obj)
            elif hit.kind == "item" and near:
                self.floor.remove_item(hit.obj)
                self.hand = hit.obj.thing
                self.sfx.play("pickup")
                self.messages.add(f"You take {hit.obj.name}.")
            elif hit.kind == "fountain" and near:
                for m in self.party.members:
                    if m.up:
                        m.water = 100.0
                        m.warned.discard("thirsty")
                self.sfx.play("drink")
                self.messages.add("You drink the cold water.")
            elif hit.kind == "switch" and near:
                hit.obj.toggle()
                self.sfx.play("lever")
                self.messages.add("You pull the lever.")
            elif hit.kind == "door" and near:
                self._use_door(hit.obj)
            return
        if hit.kind == "fountain" and near and self.hand.kind == "waterskin":
            self.hand.charges = self.hand.row["charges"]
            self.sfx.play("drink")
            self.messages.add("You fill the waterskin.")
        elif hit.kind == "door" and near and hit.obj.lock is not None:
            if hit.obj.lock == self.hand.kind:
                hit.obj.lock = None
                hit.obj.target_open = True
                self.hand = None
                self.sfx.play("unlock")
                self.messages.add("The key turns. The door opens.")
            else:
                self.messages.add("It doesn't fit.")
        elif hit.kind == "floor" and near:
            p = hit.point
            item = Item(self.hand, p.x, p.z, yaw=random.uniform(0, 360))
            self.floor.add_item(item)
            item.moving = self.floor.d.char(*item.cell) in "OX"  # dropped into a hole: let it fall
            if not item.moving:
                self.sfx.play("thud", 0.35)
            self.messages.add(f"You put down {item.name}.")
            self.hand = None
        else:
            self._throw(hit)

    def _use_door(self, door):
        if door.lock is not None:
            self.messages.add("It is locked.")
        elif door.controlled:
            self.messages.add("It won't budge.")
        else:
            door.target_open = not door.target_open

    def _throw(self, hit):
        o, d = hit.ray
        start = o + d * 18
        if self.floor.solid(*cell_of(start.x, start.z)):
            start = o
        item = Item(self.hand, start.x, start.z, y=start.y - 7, yaw=self.player.yaw)
        item.vx, item.vy, item.vz = d.x * THROW_SPEED, d.y * THROW_SPEED + 1.5, d.z * THROW_SPEED
        item.moving = True
        self.floor.add_item(item)
        self.sfx.play("throw")
        self.messages.add(f"You throw {item.name}.")
        self.hand = None

    # ------------------------------------------------------------ targets
    @property
    def target(self):
        """What Space acts on: the Tab choice, or what the mouse points at."""
        return self.key_target if self.mode == "keys" else self.hover

    def act(self):
        """Space: act on the target; with nothing to act on, swing at whatever is in front."""
        hit = self.target
        idle = hit is None or hit.kind in ("wall", "none", "floor") or (hit.kind != "enemy" and hit.t > REACH)
        if self.hand is None and idle:
            self.attack(self._enemy_in_front())
        elif hit is None:
            self._throw(self._ahead())
        else:
            self.click(hit)

    def action_name(self, hit):
        """A word for what acting on hit would do, or None."""
        if hit is None or self.travel is not None:
            return None
        if hit.kind == "enemy":
            return "attack" if self.hand is None else "throw"
        if hit.t > REACH:
            return None if self.hand is None else "throw"
        if self.hand is None:
            if hit.kind == "door" and (hit.obj.controlled or hit.obj.lock is not None):
                return "try"
            return ACTIONS.get(hit.kind)
        if hit.kind == "floor":
            return "put down"
        if hit.kind == "door" and hit.obj.lock is not None:
            return "use key"
        if hit.kind == "fountain" and self.hand.kind == "waterskin":
            return "fill"
        return "throw"

    def _ahead(self):
        """A target-less hit straight ahead (Space with nothing chosen throws this way)."""
        o, d = self.screen_ray(self.w // 2, self.h // 2)
        hit = Hit("none", REACH * 4)
        hit.ray = (o, d)
        return hit

    def key_targets(self):
        """Things Tab can choose, left to right on screen."""
        p = self.player
        fl = self.floor
        eye = p.eye
        out = []

        def add(kind, point, obj, cell, reach):
            v = point - eye
            t = v.length()
            if t > reach or t < 1e-3:
                return
            sp = self.project(point)
            if sp is None or not (0 <= sp[0] < self.w and 0 <= sp[1] < self.h):
                return
            if not line_of_sight(fl.solid, eye.x, eye.z, point.x - v.x / t * 55, point.z - v.z / t * 55):
                return
            hit = Hit(kind, t, point, obj, cell)
            hit.ray = (eye, v * (1 / t))
            hit.screen = sp
            out.append(hit)

        for e in fl.enemies:
            if e.alive:
                add("enemy", e.center, e, e.cell, TARGET_RANGE)
        for it in fl.items:
            if not it.moving:
                add("item", it.center, it, it.cell, REACH)
        for door in fl.doors.values():
            x, z = cell_center(door.cell)
            add("door", Vec3(x, 50, z), door, door.cell, REACH + 15)
        for kind, walls, y in (("switch", fl.switches, 55), ("fountain", fl.fountains, 22)):
            for wall in walls.values():
                x, z = cell_center(wall.cell)
                for _, side in wall.nodes:
                    dx, dz = side[0] - wall.cell[0], side[1] - wall.cell[1]
                    if (p.x - x) * dx + (p.z - z) * dz > CELL / 2:  # on this face's side
                        add(kind, Vec3(x + dx * (CELL / 2 + 1), y, z + dz * (CELL / 2 + 1)), wall, wall.cell, REACH + 10)
        if self.hand is not None:
            yr = math.radians(p.yaw)
            spot = Vec3(p.x + math.sin(yr) * 60, 0, p.z - math.cos(yr) * 60)
            if not fl.solid(*cell_of(spot.x, spot.z)):
                add("floor", spot, None, cell_of(spot.x, spot.z), REACH)
        out.sort(key=lambda h: h.screen[0])
        return out

    def _next_target(self, advance):
        """Follow the chosen target; advance=True moves to the next one to the right."""
        hits = self.key_targets()
        keys = [(h.kind, h.obj) for h in hits]
        if not hits:
            self.key_target = self.key_pick = None
            return
        if self.key_pick in keys:
            i = keys.index(self.key_pick)
            i = (i + 1) % len(hits) if advance else i
        else:  # nothing chosen yet, or it is gone: the one nearest the middle of the view
            i = min(range(len(hits)), key=lambda k: abs(hits[k].screen[0] - self.w / 2)
                    + abs(hits[k].screen[1] - self.h / 2) * 0.5 + (0 if hits[k].kind == "enemy" else 20))
        self.key_target = hits[i]
        self.key_pick = keys[i]

    # ------------------------------------------------------------ picking
    def screen_ray(self, mx, my):
        """Eye position and unit direction through screen pixel (mx, my)."""
        p = self.player
        cam = self.floor.view.camera
        yr, pr = math.radians(p.yaw), math.radians(p.pitch)
        fwd = Vec3(math.sin(yr) * math.cos(pr), math.sin(pr), -math.cos(yr) * math.cos(pr))
        right = fwd.cross(Vec3.UP).normalize()
        up = right.cross(fwd)
        k = math.tan(math.radians(cam.fov) / 2)
        nx = (2 * (mx + 0.5) / self.w - 1) * k * self.w / self.h
        ny = (1 - 2 * (my + 0.5) / self.h) * k
        return p.eye, (fwd + right * nx + up * ny).normalize()

    def project(self, pt):
        """Screen pixel of a world point (inverse of screen_ray), or None if behind."""
        p = self.player
        cam = self.floor.view.camera
        yr, pr = math.radians(p.yaw), math.radians(p.pitch)
        fwd = Vec3(math.sin(yr) * math.cos(pr), math.sin(pr), -math.cos(yr) * math.cos(pr))
        right = fwd.cross(Vec3.UP).normalize()
        up = right.cross(fwd)
        v = pt - p.eye
        z = v.dot(fwd)
        if z <= 0:
            return None
        k = math.tan(math.radians(cam.fov) / 2)
        nx = v.dot(right) / z / (k * self.w / self.h)
        ny = v.dot(up) / z / k
        return (nx + 1) * self.w / 2 - 0.5, (1 - ny) * self.h / 2 - 0.5

    def pick(self, mx, my):
        o, d = self.screen_ray(mx, my)
        hit = self._pick_grid(o, d, 8 * CELL)
        for it in self.floor.items:
            if it.moving:
                continue
            c = it.center
            oc = o - c
            b = oc.dot(d)
            disc = b * b - (oc.dot(oc) - ITEM_RADIUS * ITEM_RADIUS)
            if disc < 0:
                continue
            t = -b - math.sqrt(disc)
            if 0 < t < hit.t:
                hit = Hit("item", t, o + d * t, it, it.cell)
        for e in self.floor.enemies:
            if not e.alive:
                continue
            for cy in (20, 45, 70):  # three spheres stacked along the body
                oc = o - Vec3(e.x, cy, e.z)
                b = oc.dot(d)
                disc = b * b - (oc.dot(oc) - ENEMY_PICK_RADIUS * ENEMY_PICK_RADIUS)
                if disc < 0:
                    continue
                t = -b - math.sqrt(disc)
                if 0 < t < hit.t:
                    hit = Hit("enemy", t, o + d * t, e, e.cell)
        hit.ray = (o, d)
        return hit

    def _pick_grid(self, o, d, max_t):
        fl = self.floor
        gx, gz = cell_of(o.x, o.z)
        inf = float("inf")
        sx = 1 if d.x > 0 else -1
        sz = 1 if d.z > 0 else -1
        tx = ((gx + (sx > 0)) * CELL - o.x) / d.x if d.x else inf
        tz = ((gz + (sz > 0)) * CELL - o.z) / d.z if d.z else inf
        dtx = CELL / abs(d.x) if d.x else inf
        dtz = CELL / abs(d.z) if d.z else inf
        t0 = 0.0
        while t0 < max_t:
            t1 = min(tx, tz)
            door = fl.doors.get((gx, gz))
            if door is not None and door.open < 0.97:
                cx, cz = cell_center((gx, gz))
                t = ((cz - o.z) / d.z if d.z else inf) if door.axis == "x" else ((cx - o.x) / d.x if d.x else inf)
                if t0 <= t <= t1 and door.open * WALL_H <= o.y + d.y * t <= WALL_H:
                    return Hit("door", t, o + d * t, door, (gx, gz))
            ch = fl.d.char(gx, gz)
            if d.y < 0:
                t = -o.y / d.y
                if t0 <= t <= t1:
                    return Hit("floor", t, o + d * t, None, (gx, gz))
            if d.y > 0 and ch != "U":
                t = (WALL_H - o.y) / d.y
                if t0 <= t <= t1:
                    return Hit("wall", t, o + d * t, None, (gx, gz))
            if tx < tz:
                gx += sx
                t0, tx = tx, tx + dtx
            else:
                gz += sz
                t0, tz = tz, tz + dtz
            if fl.d.is_wall(gx, gz):
                sw = fl.switches.get((gx, gz))
                y = o.y + d.y * t0
                if sw is not None and 25 <= y <= 85:
                    return Hit("switch", t0, o + d * t0, sw, (gx, gz))
                fountain = fl.fountains.get((gx, gz))
                if fountain is not None and y <= 65:
                    return Hit("fountain", t0, o + d * t0, fountain, (gx, gz))
                return Hit("wall", t0, o + d * t0, None, (gx, gz))
        return Hit("none", max_t)
