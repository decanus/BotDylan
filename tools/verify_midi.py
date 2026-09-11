#!/usr/bin/env python3
"""Verify generated MIDI files parse cleanly and match their source JSON.

An independent reader, not a reuse of the writer's code — the point is to
catch a writer bug, which sharing code would hide. Standard library only, so
it runs in CI without an install step.

    python3 tools/verify_midi.py midi/*.mid
    python3 tools/verify_midi.py midi/amazing_grace.mid --songs songs

Checks, per file:
  - MThd header: format, track count, ticks per quarter
  - every MTrk chunk consumes exactly its declared length and ends with
    end-of-track
  - a tempo meta event exists, and matches quarterMs from the JSON
  - every note-on is matched by a note-off
  - note-on counts per channel match the source JSON's per-voice counts
  - CC1 and CC3 are present for every note-on, and CC precedes its note-on

Exits non-zero if anything fails.
"""

import argparse
import json
import pathlib
import struct
import sys

VOICE_FOR_CHANNEL = {0: "sop", 1: "alto", 2: "bass"}


class Fail(Exception):
    pass


def read_vlq(data, i):
    n = 0
    for _ in range(4):
        b = data[i]
        i += 1
        n = (n << 7) | (b & 0x7F)
        if not b & 0x80:
            return n, i
    raise Fail("variable-length quantity longer than 4 bytes")


def parse(path):
    d = path.read_bytes()
    if d[:4] != b"MThd":
        raise Fail("does not start with MThd")
    (hlen,) = struct.unpack(">I", d[4:8])
    fmt, ntrk, div = struct.unpack(">HHH", d[8 : 8 + hlen])
    if fmt not in (0, 1):
        raise Fail(f"unexpected format {fmt}")
    if div & 0x8000:
        raise Fail("SMPTE time division not supported by this checker")

    i = 8 + hlen
    tracks, tempo = [], None

    for t in range(ntrk):
        if d[i : i + 4] != b"MTrk":
            raise Fail(f"track {t}: missing MTrk tag")
        (tlen,) = struct.unpack(">I", d[i + 4 : i + 8])
        i += 8
        end, tick, running = i + tlen, 0, None
        notes_on, ons, ccs, saw_end = {}, [], [], False

        while i < end:
            delta, i = read_vlq(d, i)
            tick += delta
            status = d[i]

            if status == 0xFF:                       # meta
                mtype = d[i + 1]
                mlen, j = read_vlq(d, i + 2)
                payload = d[j : j + mlen]
                i = j + mlen
                if mtype == 0x51:
                    tempo = int.from_bytes(payload, "big")
                elif mtype == 0x2F:
                    saw_end = True
                continue

            if status in (0xF0, 0xF7):               # sysex
                slen, j = read_vlq(d, i + 1)
                i = j + slen
                continue

            if status & 0x80:
                running = status
                i += 1
            if running is None:
                raise Fail(f"track {t}: data byte with no running status")

            kind, chan = running & 0xF0, running & 0x0F
            if kind in (0xC0, 0xD0):
                i += 1
                continue
            d1, d2 = d[i], d[i + 1]
            i += 2

            if kind == 0x90 and d2 > 0:
                ons.append((tick, chan, d1, d2))
                notes_on[(chan, d1)] = notes_on.get((chan, d1), 0) + 1
            elif kind == 0x80 or (kind == 0x90 and d2 == 0):
                key = (chan, d1)
                if not notes_on.get(key):
                    raise Fail(f"track {t}: note-off with no matching note-on "
                               f"(ch {chan + 1}, note {d1})")
                notes_on[key] -= 1
            elif kind == 0xB0:
                ccs.append((tick, chan, d1, d2))

        if i != end:
            raise Fail(f"track {t}: consumed {i - (end - tlen)} bytes, declared {tlen}")
        if not saw_end:
            raise Fail(f"track {t}: no end-of-track meta event")
        stuck = [k for k, v in notes_on.items() if v]
        if stuck:
            raise Fail(f"track {t}: {len(stuck)} note(s) never released: {stuck[:4]}")

        tracks.append({"ons": ons, "ccs": ccs})
        i = end

    if tempo is None:
        raise Fail("no tempo meta event")
    return {"format": fmt, "ntrk": ntrk, "div": div, "tempo": tempo, "tracks": tracks}


def check_against_song(mid, song, report):
    quarter_us = int(round(song["quarterMs"] * 1000))
    if mid["tempo"] != quarter_us:
        raise Fail(f"tempo {mid['tempo']} us/quarter != quarterMs "
                   f"{song['quarterMs']} ({quarter_us})")

    ons = [o for t in mid["tracks"] for o in t["ons"]]
    ccs = [c for t in mid["tracks"] for c in t["ccs"]]

    for chan, key in VOICE_FOR_CHANNEL.items():
        want = sum(1 for n in song["notes"] if n.get(key) is not None)
        got = sum(1 for o in ons if o[1] == chan)
        if want != got:
            raise Fail(f"channel {chan + 1} ({key}): {got} note-ons, JSON has {want}")
        if want:
            report.append(f"ch{chan + 1} {key}: {got} notes")

    # every note-on needs CC1 and CC3 at or before its tick on the same channel
    cc_at = {}
    for tick, chan, num, val in ccs:
        cc_at.setdefault((chan, num), []).append(tick)
    for tick, chan, _note, _vel in ons:
        for num in (1, 3):
            ticks = cc_at.get((chan, num), [])
            if not any(t <= tick for t in ticks):
                raise Fail(f"note-on at tick {tick} ch {chan + 1} has no preceding "
                           f"CC{num}")
    report.append(f"CC1/CC3 precede every note-on")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", type=pathlib.Path)
    ap.add_argument("--songs", type=pathlib.Path, default=None,
                    help="directory of source JSON to cross-check against "
                         "(default: songs/ next to this tool)")
    args = ap.parse_args(argv)

    songs_dir = args.songs or (pathlib.Path(__file__).resolve().parent.parent / "songs")
    failures = 0

    for path in args.files:
        report = []
        try:
            mid = parse(path)
            report.append(f"format {mid['format']}, {mid['ntrk']} tracks, "
                          f"{mid['div']} ticks/quarter, "
                          f"{60_000_000 / mid['tempo']:.2f} BPM")
            src = songs_dir / (path.stem + ".json")
            if src.exists():
                check_against_song(mid, json.loads(src.read_text()), report)
            else:
                report.append(f"(no {src.name} to cross-check against)")
            print(f"OK   {path}")
            for line in report:
                print(f"       {line}")
        except Fail as e:
            print(f"FAIL {path}: {e}", file=sys.stderr)
            failures += 1
        except (IndexError, struct.error) as e:
            print(f"FAIL {path}: truncated or malformed ({e})", file=sys.stderr)
            failures += 1

    if failures:
        print(f"\n{failures} file(s) failed", file=sys.stderr)
        return 1
    print(f"\nall {len(args.files)} file(s) verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
