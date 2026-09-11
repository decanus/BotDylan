#!/usr/bin/env python3
"""Acceptance test: song JSON -> MIDI -> song JSON must come back unchanged.

This is what makes midi_to_song.py trustworthy. If a song survives the trip
through a standard MIDI file with every field intact, the importer understands
the format as well as the exporter does.

    python3 tools/roundtrip_test.py

Exits non-zero on any mismatch, and prints a field-by-field diff of the first
few offending rows so a failure is actionable rather than just red.
"""

import json
import pathlib
import subprocess
import sys
import tempfile

FIELDS = ["sop", "alto", "bass", "beats", "vowelCC", "syllable", "velocity", "glide"]
TOOLS = pathlib.Path(__file__).resolve().parent
ROOT = TOOLS.parent


def run(*args):
    r = subprocess.run([sys.executable, *map(str, args)],
                       capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"command failed: {args}\n{r.stderr}")
    return r


def compare(original, returned, label, failures):
    a, b = original["notes"], returned["notes"]

    if original["quarterMs"] != returned["quarterMs"]:
        print(f"  quarterMs: {original['quarterMs']} -> {returned['quarterMs']}")
        failures.append(label)
    if original.get("meter") != returned.get("meter"):
        print(f"  meter: {original.get('meter')} -> {returned.get('meter')}")
        failures.append(label)
    if len(a) != len(b):
        print(f"  row count: {len(a)} -> {len(b)}")
        failures.append(label)
        return

    shown = 0
    bad_rows = 0
    for i, (x, y) in enumerate(zip(a, b)):
        diffs = [(f, x.get(f), y.get(f)) for f in FIELDS if x.get(f) != y.get(f)]
        if not diffs:
            continue
        bad_rows += 1
        if shown < 5:
            shown += 1
            syl = x.get("syllable") or "(rest)"
            print(f"  row {i:3} {syl:>8}: " +
                  ", ".join(f"{f} {orig!r} -> {got!r}" for f, orig, got in diffs))
    if bad_rows:
        if bad_rows > shown:
            print(f"  ... and {bad_rows - shown} more row(s)")
        failures.append(label)
    return bad_rows


def main():
    songs = sorted((ROOT / "songs").glob("*.json"))
    if not songs:
        raise SystemExit("no songs found")

    failures = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        run(TOOLS / "song_to_midi.py", "--out", tmp, *songs)

        for src in songs:
            mid = tmp / (src.stem + ".mid")
            back = tmp / (src.stem + ".back.json")
            run(TOOLS / "midi_to_song.py", mid, "-o", back)

            original = json.loads(src.read_text())
            returned = json.loads(back.read_text())
            print(f"{src.name}: {len(original['notes'])} rows")
            bad = compare(original, returned, src.name, failures)
            if not bad:
                print(f"  all {len(FIELDS)} fields identical on every row")

    if failures:
        print(f"\nROUND TRIP FAILED: {', '.join(sorted(set(failures)))}")
        return 1
    print(f"\nROUND TRIP OK — {len(songs)} songs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
