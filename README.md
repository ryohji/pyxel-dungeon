# Pyxel Dungeon

[日本語](README.ja.md)

A real-time, first-person dungeon crawler made with [Pyxel](https://github.com/kitao/pyxel) 3 and its 3D module, Pyxel Cube. It takes after the classic party-based dungeon games, with two changes: monsters and items are 3D models instead of flat sprites, and you move freely instead of stepping square by square.

**Play in your browser: https://ryohji.github.io/pyxel-dungeon/**

Work in progress. So far there are two floors, a small puzzle (a lever, a pressure plate, a locked door), skeleton guards, an AI companion, and the character side: stats, four skills that grow with use, equipment and packs, hunger, thirst, torches that burn down, and rune magic.

The game is about bringing things back, one delve at a time. You start at a camp at the mouth of the dungeon, a single menu screen: before going down, look over the requests and take some (or find them on notes inside), go down, and bring back what was asked for: a lost ring, a stone idol, the remains of an adventurer who never came home. Back at the camp, what was asked for is handed over by itself, the party rests, and a report shows what the delve brought. Spend the coins on torches and food (Supplies), and bring bones to the smith for a maul. Choose Arn's weapon at the weapon rack: the quick sword, the long but slow spear (no use with a load), or the maul that breaks stone. Skills grow with use only up to a habit of 5; the rest of Arn's strength is what you bring back, and go down again. The dead rise again on every delve; doors you opened and things you left stay as they were. Climb an old shaft once, and the camp can send you straight down it next time. Heavy things ride on Arn's back: while he carries one he walks slowly, cannot run, and swings weakly, so set the load down before a fight.

The cellars turn out to be the ruins of an old kingdom under the hill. Five relics lie in its three floors, and carvings on the walls tell its story. Each relic is yours to settle: give it to Vesk, the scholar at the camp, to bring the kingdom's power back (old lamps relight, but stone guardians wake), or lay it in a sealed niche to bury it for good (the dark deepens, but some of the dead fall still). The gravekeeper at the camp would rather you buried them. When all five are settled, the hill decides how the story ends. See [PLAN.md](PLAN.md) for the plan (in Japanese).

## Controls

| Input | Action |
|---|---|
| W A S D | move (hold Shift to run) |
| Q E / ← → | turn |
| ↑ ↓ | look up / down (R levels the view) |
| right drag | look around |
| left click | act on what the mouse points at: attack, take or lift an item, pull a lever, open or shut a door, drink from a fountain |
| left click on the floor while carrying a load | set the load down |
| left click while holding an item | click the floor to put it down, a lock to use a key, a fountain to fill a waterskin, anything else to throw it |
| Tab | choose the next target with the keyboard (brackets mark it) |
| Space | act on the target: the Tab choice or what the mouse points at, whichever you used last. With nothing to act on, swing at the enemy in front |
| G | heavy blow, once learned from the guards' drill book (bring it back from floor 2). The sword sweeps everything in front, the spear runs through a line, the maul shakes everyone around |
| 1 2 3 4 | pick a rune from the panel at the bottom: power, then element, then shape (or click them) |
| Enter | cast the runes (Backspace takes the last one back) |
| I, or click a party panel | inventory: equip, sort the packs, eat and drink (pauses the game) |
| J | journal, in three books: what people said, relics (with what became of each), carvings and notes (Tab or 1-3 picks a book, ← → turns the page) |
| M | map (awake stone guardians show as blue squares) |
| L | language: Japanese (the default) or English |
| F | debug info (game cost and frame rate). While it is on: F5 reloads the CSVs and the current map, F6 the party takes no harm, F7 / F8 go up / down a floor, F9 puts the next kind of item in the hand |
| H | help (pauses the game; Esc or a click also closes it) |
| close the window | quit (Esc does not quit) |

You play Arn, the fighter. Mira, your companion, casts bolts at enemies in view and heals on her own, spending mana. If the party falls, the gravekeeper carries everyone back to the camp, but what Arn carried stays where he fell (the map marks it) until you go back for it.

At the camp, choose with 1-8, Tab / ↑ ↓ and Space, or the mouse. The game saves by itself when you leave the camp and when you get back (on the desktop in `~/.pyxel/ryohji/pyxel-dungeon/save.json`; delete it to start over).

Each member has four skills (fighter, ninja, priest, wizard) that level up with use: sword hits train fighter, thrown hits train ninja, healing trains priest and bolts train wizard. Running and swinging use stamina. Food and water run down over time; eat by putting food on the mouth slot in the inventory, and drink from a waterskin or a fountain. The view darkens as the torch burns low.

Arn casts rune magic. A spell is three runes: a power (1 to 4, which multiplies the mana cost and the effect), an element (fire, frost, light, life) and a shape (bolt, ward, burst, wall). Fire + bolt throws a fireball, frost + wall raises a wall of ice, light + ward lights the way without a torch, and life + burst heals the party. A bolt flies at the targeted enemy, or straight ahead. A power rune can be at most one level above the caster's skill (wizard; priest for life), or the runes fizzle.

**Turn off Japanese (or other IME) input before playing.** A composing input method swallows held keys and slows the game down. The desktop version switches to Latin input by itself on macOS and Windows; the browser version cannot.

## Run on your computer

Requires Python 3.11 or later (Pyxel 3 needs it).

```sh
python -m venv .venv
.venv/bin/pip install pyxel==3.0.0
cd game && ../.venv/bin/python main.py
```

## Layout

| Path | Contents |
|---|---|
| `game/` | the game: `main.py` (start here), the world, the party, enemies, rendering |
| `game/data/` | the numbers to tune, as CSV: members' stats, skill levels and growth, items, starting kit, spells, requests, the shop, relics and story lines, enemies, and single values such as hunger rates and hit stop (see `game/tables.py`). Japanese text is in the `*_ja` columns and in `text.csv` (see `game/lang.py`) |
| `game/maps/` | floors as ASCII maps; the format is described at the top of `game/dungeon.py` |
| `game/sfx/` | sound effects, generated by `tools/make_sfx.py` |
| `game/test_p2.py` ... `game/test_p10.py`, `game/test_story.py`, `game/test_feedback.py` | headless checks of the puzzle, combat, the character systems, magic, the camp, the story, hit stop, the development keys, Japanese, the delve loop (the camp menu, falling, the shaft, saving), and growth (weapons, the heavy blow, the smith, habits) |
| `tools/` | sound synthesis and a profiler |
| `p0/` | the rendering benchmark that settled the approach |

Every push to `main` builds the browser version and publishes it to GitHub Pages (`.github/workflows/pages.yml`).

## License

- Source code: [MIT](LICENSE)
- Assets (sound effects, maps, screenshots): [CC BY 4.0](LICENSE-ASSETS)
