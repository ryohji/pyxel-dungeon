"""Languages: English and Japanese, and drawing text in either.

Every line the player reads is written in English in the code or the CSVs.
Japanese comes from:
  data/text.csv     English line -> Japanese line, for the lines in the code
                    ({name} and the like are filled in after translating)
  *_ja columns      in the other CSVs (name_ja, text_ja, ...), for their own text
  @text_ja          in the maps, for the carvings
Anything without a Japanese version shows in English.

Japanese is drawn with the M+ bitmap font (assets/umplus_j10r.bdf, 10 px),
English with Pyxel's built-in 4x6 font. L switches the language.
"""

import csv
import os
import textwrap

import pyxel

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_FILE = os.path.join(HERE, "assets", "umplus_j10r.bdf")
LANGS = ("ja", "en")
current = ["ja"]  # the language in use (a list so that every module sees a change)
TEXT = {}
_font = []


def load():
    TEXT.clear()
    with open(os.path.join(HERE, "data", "text.csv"), newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["ja"].strip():
                TEXT[row["en"]] = row["ja"]


load()


def ja():
    return current[0] == "ja"


def switch():
    current[0] = LANGS[(LANGS.index(current[0]) + 1) % len(LANGS)]


def tr(s, **kw):
    """A line from the code in the language in use, with its {fields} filled in."""
    if ja():
        s = TEXT.get(s, s)
    return s.format(**kw) if kw else s


def loc(row, field):
    """A field of a CSV row in the language in use (field_ja when there is one)."""
    if ja():
        v = row.get(field + "_ja")
        if isinstance(v, str) and v:
            return v
    return row[field]


# ---------------------------------------------------------------- drawing
def font():
    if not _font:
        _font.append(pyxel.Font(FONT_FILE))
    return _font[0]


def wide(s):
    """Does this line need the Japanese font?"""
    return any(ord(c) > 127 for c in s)


def text(x, y, s, col):
    """Draw a line at the top-left (x, y), in whichever font it needs."""
    if wide(s):
        pyxel.text(x, y - 2, s, col, font())
    else:
        pyxel.text(x, y, s, col)


def width(s):
    return font().text_width(s) if wide(s) else len(s) * 4


def line(base):
    """Line spacing: base for the built-in font, more for Japanese."""
    return max(base, 12) if ja() else base


NO_START = set("、。，．・：；？！ー）」』】〉》…ぁぃぅぇぉっゃゅょァィゥェォッャュョ")


def wrap(s, px):
    """Break a paragraph into lines no wider than px."""
    if not wide(s):
        return textwrap.wrap(s, max(1, px // 4)) or [""]
    lines, cur = [], ""
    for c in s:
        if cur and width(cur + c) > px:
            if c in NO_START and len(cur) > 1:  # a mark may not start a line: take the last letter along
                lines.append(cur[:-1])
                cur = cur[-1] + c
            else:
                lines.append(cur)
                cur = c.lstrip()
        else:
            cur += c
    lines.append(cur)
    return lines
