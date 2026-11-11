"""Synthesize the game's sound effects into game/sfx/*.wav.

Pure Python (no numpy), deterministic. Run from the repository root:
    python tools/make_sfx.py
"""

import math
import os
import random
import struct
import wave

SR = 22050
STAIR_PACE = 0.46  # seconds per step on the stairs, the same as walking
OUT = os.path.join(os.path.dirname(__file__), "..", "game", "sfx")


# ---------------------------------------------------------------- building blocks
def silence(sec):
    return [0.0] * int(SR * sec)


def noise(sec, rnd):
    return [rnd.uniform(-1, 1) for _ in range(int(SR * sec))]


def lowpass(x, cutoff):
    """One-pole low-pass; cutoff may be a number or a function of t (sec)."""
    y, out = 0.0, []
    for i, s in enumerate(x):
        c = cutoff(i / SR) if callable(cutoff) else cutoff
        a = 1 - math.exp(-2 * math.pi * c / SR)
        y += a * (s - y)
        out.append(y)
    return out


def highpass(x, cutoff):
    lp = lowpass(x, cutoff)
    return [s - l for s, l in zip(x, lp)]


def bandpass(x, lo, hi):
    return highpass(lowpass(x, hi), lo)


def env(x, attack, decay, hold=0.0):
    """Linear attack, hold, then exponential decay (decay = time constant)."""
    out = []
    for i, s in enumerate(x):
        t = i / SR
        if t < attack:
            g = t / attack
        elif t < attack + hold:
            g = 1.0
        else:
            g = math.exp(-(t - attack - hold) / decay)
        out.append(s * g)
    return out


def tone(sec, freq, phase=0.0):
    """Sine with a frequency that may be a function of t (sec)."""
    out, ph = [], phase
    for i in range(int(SR * sec)):
        f = freq(i / SR) if callable(freq) else freq
        ph += 2 * math.pi * f / SR
        out.append(math.sin(ph))
    return out


def mix(*parts):
    """Mix (offset_sec, samples, gain) parts."""
    n = max(int(o * SR) + len(s) for o, s, _ in parts)
    out = [0.0] * n
    for o, s, g in parts:
        k = int(o * SR)
        for i, v in enumerate(s):
            out[k + i] += v * g
    return out


def echo(x, delay, feedback, taps=3):
    out = list(x) + [0.0] * int(delay * SR * taps)
    d = int(delay * SR)
    for t in range(1, taps + 1):
        g = feedback ** t
        for i, v in enumerate(x):
            out[i + d * t] += v * g
    return out


def normalize(x, peak=0.9):
    m = max(1e-9, max(abs(v) for v in x))
    return [v * peak / m for v in x]


def crunch(x, bits=10):
    """Reduce resolution a little for a lo-fi edge."""
    q = 2 ** (bits - 1)
    return [round(v * q) / q for v in x]


def write(name, x, peak=0.9):
    x = crunch(normalize(x, peak))
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name + ".wav")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, v)) * 32767)) for v in x))
    print(f"{name:12s} {len(x) / SR:4.2f}s")


# ---------------------------------------------------------------- sounds
def thump(rnd, freq=90, sec=0.25, click=0.4, decay=0.06):
    """Something heavy hitting stone."""
    body = env(tone(sec, lambda t: freq * (1 + 0.6 * math.exp(-t * 40))), 0.002, decay)
    hit = env(lowpass(noise(sec, rnd), 1800), 0.001, 0.015)
    return mix((0, body, 1.0), (0, hit, click))


def grind(rnd, sec, rate=17.0, cutoff=380, wobble=0.6):
    """Stone and timber dragging: rumble with a ratchety amplitude."""
    base = lowpass(lowpass(noise(sec, rnd), cutoff), cutoff * 1.5)
    out = []
    for i, s in enumerate(base):
        t = i / SR
        am = 1 - wobble * (0.5 + 0.5 * math.sin(2 * math.pi * rate * t + 2 * math.sin(7 * t)))
        out.append(s * am)
    fade = int(0.04 * SR)
    for i in range(fade):
        out[i] *= i / fade
        out[-1 - i] *= i / fade
    return out


def main():
    rnd = random.Random(2026)

    # lever: two dry clacks and a low thunk
    clack = env(bandpass(noise(0.06, rnd), 700, 4000), 0.001, 0.01)
    write("lever", mix((0, clack, 1.0), (0.11, clack, 0.8), (0.11, thump(rnd, 140, 0.15, 0.2, 0.04), 0.7)))

    # key: small metallic clicks, a ring, then the bolt sliding home
    tick = env(highpass(noise(0.03, rnd), 2500), 0.0005, 0.006)
    ring = env(mix((0, tone(0.3, 2150), 1.0), (0, tone(0.3, 3370), 0.6), (0, tone(0.3, 5100), 0.3)), 0.001, 0.05)
    bolt = mix((0, env(bandpass(noise(0.12, rnd), 300, 2500), 0.005, 0.04), 0.8), (0.06, thump(rnd, 160, 0.2, 0.5, 0.03), 0.8))
    write("unlock", mix((0, tick, 0.7), (0.07, tick, 0.7), (0.07, ring, 0.35), (0.2, bolt, 1.0)))

    # door opening: half a second of grinding, settling at the top
    write("door_open", mix((0, grind(rnd, 0.55, 17, 420), 1.0), (0.5, thump(rnd, 110, 0.2, 0.2, 0.05), 0.4)))
    # door closing: grinding, then a heavy slam
    write("door_close", mix((0, grind(rnd, 0.5, 21, 360), 0.8), (0.48, thump(rnd, 70, 0.45, 0.6, 0.12), 1.0)), peak=0.95)

    # rock hitting the floor, and a lighter knock off a wall
    write("thud", echo(thump(rnd, 85, 0.3, 0.6, 0.05), 0.07, 0.25, 2))
    write("knock", thump(rnd, 180, 0.15, 0.8, 0.025))

    # throw: a short whoosh
    whoosh = bandpass(noise(0.28, rnd), 500, 2200)
    write("throw", env(whoosh, 0.08, 0.05, hold=0.04), peak=0.6)

    # pick up: a soft scrape
    write("pickup", env(bandpass(noise(0.14, rnd), 900, 3500), 0.02, 0.03), peak=0.5)

    # pressure plate: stone sinking with a click, and coming back up
    sink = mix((0, env(highpass(noise(0.02, rnd), 1500), 0.0005, 0.004), 0.6),
               (0.015, thump(rnd, 60, 0.35, 0.3, 0.09), 1.0),
               (0.12, env(bandpass(noise(0.05, rnd), 600, 3000), 0.001, 0.008), 0.5))
    write("plate_down", echo(sink, 0.09, 0.3, 2))
    write("plate_up", mix((0, env(bandpass(noise(0.05, rnd), 700, 3000), 0.001, 0.01), 0.7),
                          (0.02, thump(rnd, 120, 0.15, 0.2, 0.03), 0.5)))

    # stairs: footsteps on stone, falling (down) or rising (up) in pitch, with a stairwell echo.
    # Four steps at walking pace (STRIDE_WALK / WALK = 0.46 s); a fifth is drawn and dropped
    # so the sounds generated after these stay as tuned.
    def steps(direction):
        parts = []
        for k in range(5):
            f = 110 - direction * k * 9
            step = thump(rnd, f, 0.16, 0.8, 0.03)
            if k < 4:
                parts.append((k * STAIR_PACE, step, 1.0 - k * 0.1))
        return echo(mix(*parts), 0.11, 0.3, 3)

    write("stairs_down", steps(+1))
    write("stairs_up", steps(-1))

    # falling: wind rushing past, the cutoff dropping as you fall
    rush = env(lowpass(noise(0.6, rnd), lambda t: 2600 * math.exp(-t * 2.5) + 200), 0.05, 0.25, hold=0.25)
    write("fall", rush, peak=0.7)
    # landing: a heavy crash with debris
    crash = mix((0, thump(rnd, 55, 0.6, 1.0, 0.15), 1.0),
                (0.0, env(lowpass(noise(0.5, rnd), 1200), 0.002, 0.12), 0.7),
                (0.08, env(bandpass(noise(0.25, rnd), 800, 4000), 0.002, 0.03), 0.3),
                (0.16, env(bandpass(noise(0.2, rnd), 1000, 5000), 0.002, 0.02), 0.2))
    write("land", echo(crash, 0.12, 0.3, 3), peak=0.95)

    # walking: a lighter cousin of the running footfall (own generator, so the
    # running steps below keep the noise they were tuned with)
    srnd = random.Random(7)
    for k in range(2):  # draw what the earlier soft steps drew, so the running steps stay as tuned
        thump(rnd, 70 + k * 12, 0.12, 0.5, 0.02)
    for k in range(2):
        fall = thump(srnd, 72 + k * 10, 0.18, 0.7, 0.03)
        scuff = env(bandpass(noise(0.05, srnd), 400, 2200), 0.004, 0.014)
        write(f"step{k}", mix((0, fall, 1.0), (0.012, scuff, 0.25)), peak=0.6)

    # running: heavier footfalls with a scuff of the sole
    for k in range(2):
        fall = thump(rnd, 62 + k * 10, 0.2, 0.9, 0.035)
        scuff = env(bandpass(noise(0.06, rnd), 400, 2500), 0.004, 0.018)
        write(f"run{k}", mix((0, fall, 1.0), (0.012, scuff, 0.45)), peak=0.7)

    # a water drip somewhere in the dark
    drop = env(tone(0.12, lambda t: 1900 * math.exp(-t * 9) + 700), 0.001, 0.025)
    write("drip", echo(drop, 0.23, 0.35, 4), peak=0.5)

    combat_sounds()
    p4_sounds()
    p5_sounds()
    p6_sounds()


def p4_sounds():
    """P4 sounds (eating, drinking, a level gained), from their own generator."""
    rnd = random.Random(404)

    # eating: three soft crunches
    def crunch_bite(gain):
        return [v * gain for v in env(bandpass(noise(0.07, rnd), 600, 3000), 0.003, 0.02)]
    write("eat", mix((0, crunch_bite(1.0), 1.0), (0.16, crunch_bite(0.8), 1.0), (0.33, crunch_bite(0.6), 1.0)), peak=0.55)

    # drinking: two gulps, low bubbly blips falling in pitch
    def gulp():
        return env(tone(0.09, lambda t: 420 * math.exp(-t * 14) + 160), 0.004, 0.03)
    splash = env(bandpass(noise(0.15, rnd), 1500, 6000), 0.005, 0.05)
    write("drink", mix((0, splash, 0.25), (0.05, gulp(), 1.0), (0.32, gulp(), 0.9)), peak=0.6)

    # a level gained: a bright rising arpeggio
    notes = (523, 659, 784, 1047)
    arp = mix(*[(k * 0.08, env(mix((0, tone(0.5, f), 1.0), (0, tone(0.5, f * 2), 0.25)), 0.004, 0.14), 0.7)
                for k, f in enumerate(notes)])
    write("levelup", echo(arp, 0.12, 0.25, 2), peak=0.5)


def p6_sounds():
    """P6: coins at the counter, lifting a load onto the back."""
    rnd = random.Random(606)

    def clink(f):
        return env(mix((0, tone(0.25, f), 1.0), (0, tone(0.25, f * 2.76), 0.4)), 0.001, 0.05)
    write("coins", mix(*[(k * 0.06 + rnd.uniform(0, 0.02), clink(rnd.uniform(2400, 3400)), 1.0 - k * 0.15)
                         for k in range(5)]), peak=0.5)

    # a grunt of effort is too much: cloth and a heavy shift of weight
    cloth = env(bandpass(noise(0.35, rnd), 300, 2000), 0.08, 0.1)
    write("lift", mix((0, cloth, 0.8), (0.25, thump(rnd, 75, 0.25, 0.4, 0.06), 1.0)), peak=0.6)


def p5_sounds():
    """P5 rune magic, from its own generator."""
    rnd = random.Random(505)

    # casting: a shimmer rising in pitch
    shimmer = mix(*[(k * 0.04, env(tone(0.35, lambda t, f=f: f * (1 + 0.8 * t)), 0.01, 0.1), 0.5)
                    for k, f in enumerate((660, 990, 1320))])
    write("cast", mix((0, shimmer, 1.0), (0, env(highpass(noise(0.3, rnd), 4000), 0.02, 0.08), 0.2)), peak=0.5)

    # fizzle: a short sputter falling away
    sputter = env(bandpass(noise(0.35, rnd), 300, 1800), 0.005, 0.1)
    write("fizzle", mix((0, sputter, 1.0), (0, env(tone(0.3, lambda t: 400 * math.exp(-t * 5)), 0.005, 0.08), 0.4)),
          peak=0.5)

    # fire: a roaring whoomph
    roar = env(lowpass(noise(0.6, rnd), lambda t: 300 + 1500 * math.exp(-t * 6)), 0.01, 0.2, hold=0.1)
    write("burn", mix((0, roar, 1.0), (0, thump(rnd, 70, 0.3, 0.3, 0.08), 0.6)), peak=0.8)

    # frost: glassy crackle and a cold ring
    crackle = mix(*[(rnd.uniform(0, 0.3), env(highpass(noise(0.02, rnd), 3000), 0.0005, 0.005), rnd.uniform(0.4, 1.0))
                    for _ in range(14)])
    ring = env(mix((0, tone(0.6, 1760), 1.0), (0, tone(0.6, 2637), 0.5)), 0.003, 0.2)
    write("freeze", mix((0, crackle, 1.0), (0.02, ring, 0.3)), peak=0.6)

    # light: a bright flash, a high sweep and a pop
    sweep = env(tone(0.4, lambda t: 1200 + 2400 * t), 0.002, 0.12)
    write("flash", mix((0, env(highpass(noise(0.08, rnd), 2000), 0.001, 0.02), 0.8), (0, sweep, 0.5)), peak=0.55)


def combat_sounds():
    """P3 sounds, from their own generator so the earlier sounds stay as tuned."""
    rnd = random.Random(303)

    def click(gain=1.0):
        return [v * gain for v in env(highpass(noise(0.02, rnd), 1800), 0.0005, 0.004)]

    def rattle(sec, rate, decay_rate=0.0):
        parts, t = [], 0.0
        while t < sec:
            parts.append((t, click(rnd.uniform(0.4, 1.0) * math.exp(-t * decay_rate)), 1.0))
            t += rnd.expovariate(rate)
        return mix(*parts)

    # the fighter's sword cutting the air
    write("swing", env(bandpass(noise(0.2, rnd), 700, 3200), 0.035, 0.035, hold=0.02), peak=0.6)

    # a blade or bolt cracking bone
    knock = env(tone(0.08, lambda t: 480 * math.exp(-t * 18) + 180), 0.001, 0.018)
    write("hit_bone", mix((0, click(1.0), 1.0), (0, knock, 0.9), (0.02, rattle(0.12, 60, 15), 0.6)))

    # a skeleton raising its blade (bones rattle) and bringing it down (whoosh)
    whoosh = env(bandpass(noise(0.18, rnd), 500, 2500), 0.03, 0.04, hold=0.02)
    write("enemy_swing", mix((0, rattle(0.3, 40, 4), 0.7), (0.42, whoosh, 1.0)), peak=0.7)

    # the party taking a blow
    write("hurt", mix((0, thump(rnd, 85, 0.3, 0.9, 0.06), 1.0),
                      (0.0, env(lowpass(noise(0.2, rnd), 700), 0.002, 0.05), 0.6)), peak=0.85)

    # bones clattering to the floor
    write("collapse", mix((0, rattle(0.9, 45, 3), 1.0), (0.05, thump(rnd, 120, 0.2, 0.6, 0.03), 0.5),
                          (0.35, thump(rnd, 95, 0.25, 0.7, 0.04), 0.6)), peak=0.8)

    # a skeleton noticing the party
    write("alert", echo(rattle(0.35, 55, 2), 0.13, 0.35, 3), peak=0.6)

    # Mira's bolt: a rising buzz with sparks
    buzz = [math.copysign(1, v) * 0.5 for v in tone(0.3, lambda t: 250 + 900 * t / 0.3)]
    sparks = highpass(noise(0.3, rnd), 3000)
    bolt = mix((0, env(lowpass(buzz, 2500), 0.01, 0.12, hold=0.1), 1.0), (0, env(sparks, 0.01, 0.1, hold=0.05), 0.35))
    write("bolt", bolt, peak=0.55)
    write("bolt_hit", mix((0, env(highpass(noise(0.25, rnd), 1200), 0.001, 0.05), 1.0),
                          (0, thump(rnd, 150, 0.15, 0.3, 0.03), 0.6)), peak=0.7)

    # healing: a soft rising chime
    chime = mix(*[(k * 0.09, env(tone(0.6, f), 0.005, 0.18), 0.6) for k, f in enumerate((880, 1109, 1319, 1760))])
    write("heal", echo(chime, 0.15, 0.3, 2), peak=0.5)

    # the party falls: a low falling drone
    drone = [v * (0.7 + 0.3 * math.sin(2 * math.pi * 6 * i / SR))
             for i, v in enumerate(tone(1.6, lambda t: 110 * math.exp(-t * 0.45)))]
    write("defeat", env(mix((0, drone, 1.0), (0, lowpass(noise(1.6, rnd), 300), 0.4)), 0.05, 0.6, hold=0.6), peak=0.8)


if __name__ == "__main__":
    main()
