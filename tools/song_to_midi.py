#!/usr/bin/env python3
"""Convert songs/*.json into standard MIDI files.

The bridge from our song format to the Digitakt, a DAW, or anything else that
reads SMF. Notes land on channels 1/2/3 for soprano/alto/bass, matching the
firmware's channel-per-voice allocation, so an exported file plays the robot
without any mapping.

Standard library only, on purpose: a MIDI file is just length-prefixed chunks
and variable-length integers, and nothing here is worth an install step.

    python3 tools/song_to_midi.py                    # convert every song
    python3 tools/song_to_midi.py songs/ode_to_joy.json
    python3 tools/song_to_midi.py --out /tmp --ticks 960

Per note the exporter writes, in this order and at the same tick:

    CC1  the note's vowel
    CC3  the glide onset (0 none, 32 = "w", 96 = "l")
    note on ... note off

CC before note-on matters: the firmware latches CC3 and consumes it on the
next note-on. CC3 is written for every note, including 0 for no glide, so a
previous note's glide can never leak into the next one.
"""

import argparse
import json
import pathlib
import struct
import sys

# CC3 bands the firmware decodes: 0 none, 1-63 "w", 64-127 "l".
GLIDE_CC = {"": 0, "w": 32, "l": 96}

VOICES = [("sop", 0, "Soprano"), ("alto", 1, "Alto"), ("bass", 2, "Bass")]


def vlq(n):
    """MIDI variable-length quantity."""
    if n < 0:
        raise ValueError("negative delta time")
    out = bytearray([n & 0x7F])
    n >>= 7
    while n:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    return bytes(reversed(out))


def chunk(tag, body):
    return tag + struct.pack(">I", len(body)) + body


def track(events):
    """events: list of (tick, order, bytes). Returns an MTrk chunk."""
    body = bytearray()
    prev = 0
    for tick, _order, data in sorted(events, key=lambda e: (e[0], e[1])):
        body += vlq(tick - prev)
        body += data
        prev = tick
    body += vlq(0) + b"\xff\x2f\x00"          # end of track
    return chunk(b"MTrk", bytes(body))


def meta_name(text):
    raw = text.encode("ascii", "replace")
    return b"\xff\x03" + vlq(len(raw)) + raw


def meta_text(text):
    """FF 01 — carries the vocoder's onset/coda codes, which have no natural
    home in MIDI. Without this the round trip would quietly drop them."""
    raw = text.encode("ascii", "replace")
    return b"\xff\x01" + vlq(len(raw)) + raw


def meta_lyric(text):
    """FF 05 — the syllable. Without this the round trip through MIDI loses
    the lyric entirely, since nothing else in the file carries it."""
    raw = text.encode("ascii", "replace")
    return b"\xff\x05" + vlq(len(raw)) + raw


def convert(song, ticks_per_quarter):
    quarter_ms = song["quarterMs"]
    gap_ms = song.get("gapMs", 60)
    gap_ticks = round(gap_ms / quarter_ms * ticks_per_quarter)

    # Track 0: tempo, time signature, and the lyric.
    usec_per_quarter = int(round(quarter_ms * 1000))
    meta = [
        (0, 0, meta_name(song.get("name", "song"))),
        (0, 1, b"\xff\x51\x03" + struct.pack(">I", usec_per_quarter)[1:]),
    ]
    num, den = (int(x) for x in song.get("meter", "4/4").split("/"))
    meta.append((0, 2, b"\xff\x58\x04" + bytes([num, den.bit_length() - 1, 24, 8])))

    tick = 0
    for note in song["notes"]:
        if note.get("syllable"):
            meta.append((tick, 3, meta_lyric(note["syllable"])))
        if note.get("onset") or note.get("coda"):
            meta.append((tick, 4, meta_text(
                "art:%s/%s" % (note.get("onset", ""), note.get("coda", "")))))
        tick += round(note["beats"] * ticks_per_quarter)

    tracks = [track(meta)]

    for key, channel, label in VOICES:
        events = [(0, 0, meta_name(label))]
        tick = 0
        sounded = False

        for note in song["notes"]:
            length = round(note["beats"] * ticks_per_quarter)
            pitch = note.get(key)

            if pitch is not None:
                sounded = True
                dur = max(1, length - gap_ticks)
                vel = int(note["velocity"])
                # order: CCs first, then the note-on, at the same tick
                events.append((tick, 0, bytes([0xB0 | channel, 1, int(note["vowelCC"])])))
                events.append((tick, 1, bytes([0xB0 | channel, 3, GLIDE_CC[note.get("glide", "")]])))
                events.append((tick, 2, bytes([0x90 | channel, pitch, vel])))
                events.append((tick + dur, 3, bytes([0x80 | channel, pitch, 0])))

            tick += length

        if sounded:
            tracks.append(track(events))

    header = chunk(b"MThd", struct.pack(">HHH", 1, len(tracks), ticks_per_quarter))
    return header + b"".join(tracks)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("songs", nargs="*", type=pathlib.Path,
                    help="song JSON files (default: every file in songs/)")
    ap.add_argument("--out", type=pathlib.Path, default=None,
                    help="output directory (default: alongside each input)")
    ap.add_argument("--ticks", type=int, default=480,
                    help="ticks per quarter note (default: 480)")
    args = ap.parse_args(argv)

    paths = args.songs
    if not paths:
        here = pathlib.Path(__file__).resolve().parent.parent / "songs"
        paths = sorted(here.glob("*.json"))
    if not paths:
        print("no song files found", file=sys.stderr)
        return 1

    for path in paths:
        song = json.loads(path.read_text())
        data = convert(song, args.ticks)
        dest = (args.out or path.parent) / (path.stem + ".mid")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        voices = [label for key, _c, label in VOICES
                  if any(n.get(key) is not None for n in song["notes"])]
        print(f"{dest}  {len(song['notes'])} notes  {', '.join(voices)}  "
              f"{len(data)} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
