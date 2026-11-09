"""Sound effects: load the WAVs and play them with distance-based volume.

Channels
  0  the player's hands and body (lever, key, take, throw, sword, getting hurt)
  1  mechanisms and enemies (doors, plates, skeleton swings, alerts, collapse)
  2  impacts and footsteps (thuds, hits on bone)
  3  travel, the companion and ambience (stairs, falling, bolts, healing, drips)
"""

import math
import os
import random

import pyxel

HERE = os.path.dirname(os.path.abspath(__file__))

NAMES = ("lever", "unlock", "door_open", "door_close", "thud", "knock", "throw", "pickup",
         "plate_down", "plate_up", "stairs_down", "stairs_up", "fall", "land", "step0", "step1", "drip", "run0", "run1",
         "swing", "hit_bone", "enemy_swing", "hurt", "collapse", "alert", "bolt", "bolt_hit", "heal", "defeat")

CHANNEL = {
    "lever": 0, "unlock": 0, "throw": 0, "pickup": 0,
    "door_open": 1, "door_close": 1, "plate_down": 1, "plate_up": 1,
    "thud": 2, "knock": 2, "step0": 2, "step1": 2, "run0": 2, "run1": 2,
    "stairs_down": 3, "stairs_up": 3, "fall": 3, "land": 3, "drip": 3,
    "swing": 0, "hit_bone": 2, "hurt": 0, "bolt": 3, "heal": 3, "defeat": 3,
    "enemy_swing": 1, "collapse": 1, "alert": 1, "bolt_hit": 2,
}
BASE_GAIN = {"step0": 0.4, "step1": 0.4, "run0": 0.55, "run1": 0.55, "drip": 0.45, "throw": 0.7, "pickup": 0.7}
MAX_GAIN = 0.5  # Channel.gain at full volume (Pyxel's default is 0.125)
HEAR_RANGE = 900.0  # beyond this a sound is silent (9 m)


class Sfx:
    def __init__(self):
        self.index = {}
        for i, name in enumerate(NAMES):
            pyxel.sounds[i].pcm(os.path.join(HERE, "sfx", name + ".wav"))
            self.index[name] = i
        self.busy_until = [0] * 4  # frame until which a louder sound holds the channel
        self.busy_gain = [0.0] * 4
        self.rnd = random.Random()
        self.next_drip = 300

    def play(self, name, volume=1.0, dist=0.0):
        """Play a sound; dist (world units) from the listener lowers the volume."""
        if dist > 0:
            volume *= max(0.0, 1 - dist / HEAR_RANGE) ** 2
        gain = MAX_GAIN * BASE_GAIN.get(name, 1.0) * min(1.0, volume)
        if gain < 0.01:
            return
        ch = CHANNEL[name]
        now = pyxel.frame_count
        # do not cut off a louder sound that is still playing for a quieter one
        if now < self.busy_until[ch] and gain < self.busy_gain[ch] * 0.6:
            return
        pyxel.channels[ch].gain = gain
        pyxel.play(ch, self.index[name])
        self.busy_until[ch] = now + 12
        self.busy_gain[ch] = gain

    def ambience(self):
        """Occasional drips from somewhere in the dark."""
        if pyxel.frame_count < self.next_drip:
            return
        self.next_drip = pyxel.frame_count + self.rnd.randint(4 * 60, 11 * 60)
        if pyxel.play_pos(3) is None:
            self.play("drip", self.rnd.uniform(0.3, 1.0))


class NullSfx:
    """Silent stand-in for headless tests; remembers what would have played."""

    def __init__(self):
        self.played = []

    def play(self, name, volume=1.0, dist=0.0):
        self.played.append(name)

    def ambience(self):
        pass


def distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])
