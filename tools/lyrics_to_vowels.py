#!/usr/bin/env python3
"""Fill in a song's syllables and vowel positions from a syllabified lyric.

    python3 tools/lyrics_to_vowels.py songs/amazing_grace.json \
        "A-ma-zing grace how sweet the sound ..." -o songs/amazing_grace.json

Whitespace splits words, hyphens split syllables. Rest rows take no syllable.

The sung vowel of a syllable is its LAST vowel cluster, because that is what a
sustained note actually holds: "sweet" holds ee, "sound" holds the ah of the
ou diphthong. Choir directors call this singing on the vowel; consonants are
transitions, and the robot has no consonants at all.

Anchors, as CC values: oo=10, oh=38, ah=64, eh=96, ee=120.

Standard library only. Reads local files only.
"""

import argparse
import json
import pathlib
import re
import sys

OO, OH, AH, EH, EE = 10, 38, 64, 96, 120
I_SHORT = 115          # "sing", "in" — closer to ee than to anything else

# Longest match first. Everything here is the cluster as spelled.
DIGRAPHS = [
    ("igh", AH), ("ough", AH), ("augh", OH),
    ("oo", OO), ("ew", OO), ("ue", OO), ("ui", OO),
    ("oa", OH), ("oe", OH), ("aw", OH), ("au", OH), ("oy", OH), ("oi", OH),
    ("ee", EE), ("ea", EE), ("ie", EE), ("ei", EE), ("ey", EE),
    ("ai", EH), ("ay", EH),
    ("ou", AH), ("ow", AH),          # house/now; the oh-words are overridden below
]

# Vowel when a "magic e" makes it long: name, like, note, tune, these.
LONG = {"a": EH, "e": EE, "i": AH, "o": OH, "u": OO, "y": AH}
# Vowel when it is short: that, wretch, sing, lost, but.
SHORT = {"a": AH, "e": EH, "i": I_SHORT, "o": OH, "u": OH, "y": EE}

# Whole words only (never a hyphenated syllable) whose sung vowel is not what
# the spelling suggests — mostly unstressed function words that reduce to a
# schwa, which sits around "oh" on our scale.
WHOLE_WORD = {
    "the": OH, "a": OH, "was": OH, "of": OH, "once": OH, "to": OO, "do": OO,
    "you": OO, "your": OO, "who": OO, "know": OH, "own": OH, "low": OH,
    "show": OH, "grow": OH, "snow": OH, "though": OH, "come": OH, "some": OH,
    "love": OH, "done": OH, "one": OH, "none": OH, "word": OH, "work": OH,
    "i": AH, "my": AH, "by": AH, "why": AH, "eye": AH,
    "is": I_SHORT, "it": I_SHORT, "its": I_SHORT, "it's": I_SHORT,
    "his": I_SHORT, "him": I_SHORT, "this": I_SHORT,
}


def vowel_cc(token, whole_word):
    """The CC value for one syllable. whole_word is False for a hyphenated
    piece, where the function-word table must not apply — the "A" of
    "A-ma-zing" is a sung ah, not the reduced article."""
    s = re.sub(r"[^a-z']", "", token.lower())
    if not s:
        return AH
    if whole_word and s in WHOLE_WORD:
        return WHOLE_WORD[s]

    core = s.rstrip("'")
    # Silent final e: "like" -> "lik", so the i goes long. Needs a vowel before
    # it, and at most two consonants between.
    magic = False
    if len(core) > 2 and core.endswith("e") and core[-2] not in "aeiouy":
        stem = core[:-1]
        if re.search(r"[aeiouy]", stem):
            core, magic = stem, True

    # A trailing w counts as part of the cluster, or "now"/"saw"/"new" never
    # form their digraph and fall through to a bare short vowel.
    clusters = re.findall(r"[aeiouy]+w?", core)
    if not clusters:
        return AH
    last = clusters[-1]

    for spelling, cc in DIGRAPHS:
        if last.endswith(spelling) or last == spelling:
            return cc

    letter = last[-1]
    if magic:
        return LONG.get(letter, AH)
    # A lone vowel ending the word is long: me, he, go, hi.
    if core.endswith(last) and len(clusters) == 1 and len(core) > 1 and \
            core.index(last) == len(core) - len(last):
        return LONG.get(letter, AH)
    # i before nd / ld / gh runs long: blind, find, mild, high.
    if letter == "i" and re.search(r"i(nd|ld|gh)$", core):
        return AH
    return SHORT.get(letter, AH)


def syllabify(lyric):
    """-> [(syllable, is_whole_word)]"""
    out = []
    for word in lyric.split():
        parts = [p for p in word.split("-") if p]
        whole = len(parts) == 1
        for p in parts:
            out.append((p, whole))
    return out


def alignment_report(rows, sylls):
    """Side by side, so a count mismatch is diagnosable rather than just fatal."""
    print("\n  note | existing syllable | proposed", file=sys.stderr)
    print("  -----+-------------------+---------", file=sys.stderr)
    n = max(len(rows), len(sylls))
    for i in range(n):
        have = rows[i].get("syllable", "") if i < len(rows) else "—"
        want = sylls[i][0] if i < len(sylls) else "—"
        mark = "  " if i < len(rows) and i < len(sylls) else "<<"
        print(f"  {i:4} | {have:<17} | {want} {mark}", file=sys.stderr)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("song", type=pathlib.Path)
    ap.add_argument("lyric", help='syllabified, e.g. "A-ma-zing grace how sweet"')
    ap.add_argument("-o", "--out", type=pathlib.Path, default=None)
    ap.add_argument("--compare", action="store_true",
                    help="report the diff against the song's existing vowelCC "
                         "values instead of writing anything")
    args = ap.parse_args(argv)

    song = json.loads(args.song.read_text())
    sounding = [n for n in song["notes"]
                if any(n.get(v) is not None for v in ("sop", "alto", "bass"))]
    sylls = syllabify(args.lyric)

    if len(sylls) != len(sounding):
        print(f"ERROR: {len(sylls)} syllables for {len(sounding)} sounding notes "
              f"in {args.song.name}.", file=sys.stderr)
        print("Nothing written — fix the lyric or the song, do not let these "
              "drift apart silently.", file=sys.stderr)
        alignment_report(sounding, sylls)
        return 1

    rows = []
    for note, (syl, whole) in zip(sounding, sylls):
        cc = vowel_cc(syl, whole)
        rows.append((syl, note.get("vowelCC"), cc))
        note["syllable"] = syl
        note["vowelCC"] = cc

    if args.compare:
        print(f"{'syllable':>10} {'hand':>6} {'mapped':>7} {'diff':>6}")
        within = 0
        for syl, hand, cc in rows:
            d = None if hand is None else cc - hand
            if d is not None and abs(d) <= 16:
                within += 1
            print(f"{syl:>10} {str(hand):>6} {cc:>7} {'' if d is None else d:>6}")
        pct = 100.0 * within / len(rows)
        print(f"\nwithin +/-16 CC: {within}/{len(rows)} = {pct:.1f}%"
              f"  ({'PASS' if pct >= 80 else 'FAIL'}, target 80%)")
        return 0 if pct >= 80 else 1

    dest = args.out or args.song
    dest.write_text(json.dumps(song, indent=2) + "\n")
    print(f"{dest}: {len(rows)} syllables applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
