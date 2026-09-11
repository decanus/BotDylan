#!/usr/bin/env python3
"""Convert a standard MIDI file into our songs/*.json format.

The inverse of song_to_midi.py, and the keystone of the repertoire pipeline:
every way of teaching the robot a song ends up here.

    python3 tools/midi_to_song.py hymn.mid -o songs/hymn.json
    python3 tools/midi_to_song.py melody.mid --track 2 --unit quarter

Voice assignment:
  - If the file uses channels 1/2/3, they map to soprano/alto/bass directly.
  - Otherwise the melody is taken as the soprano: whichever track has the most
    notes in vocal range (C3-C6), or --track N to say which.

Everything is quantised to a unit grid (default an eighth note) derived from
the file's own PPQ, and each voice is reduced to monophonic with last-note
priority, matching the firmware. CC1 and CC3 carry through where present; with
no CC1, vowels are assigned by pitch height across the voice's own range,
which is the same trick Ode to Joy uses.

Standard library only. Reads local files only — this tool never fetches
anything.
"""

import argparse
import json
import pathlib
import struct
import sys

UNITS = {"quarter": 1.0, "eighth": 0.5, "sixteenth": 0.25, "triplet": 1.0 / 3.0}
VOICES = ["sop", "alto", "bass"]
VOCAL_LO, VOCAL_HI = 48, 84          # C3..C6, for the melody heuristic
VOWEL_LO, VOWEL_HI = 16, 88          # CC range for the pitch-height vowel pass


# ---------------------------------------------------------------- reading ---
def read_vlq(d, i):
    n = 0
    while True:
        b = d[i]
        i += 1
        n = (n << 7) | (b & 0x7F)
        if not b & 0x80:
            return n, i


def parse_midi(path):
    """-> (ppq, tempo_us, tracks) where each track is a list of events."""
    d = path.read_bytes()
    if d[:4] != b"MThd":
        raise SystemExit(f"{path}: not a MIDI file (no MThd)")
    (hlen,) = struct.unpack(">I", d[4:8])
    _fmt, ntrk, div = struct.unpack(">HHH", d[8 : 8 + hlen])
    if div & 0x8000:
        raise SystemExit(f"{path}: SMPTE time division is not supported")

    i = 8 + hlen
    tempo = 500000
    meter = "4/4"
    title = None
    tracks = []

    for _ in range(ntrk):
        if d[i : i + 4] != b"MTrk":
            raise SystemExit(f"{path}: expected MTrk at byte {i}")
        (tlen,) = struct.unpack(">I", d[i + 4 : i + 8])
        i += 8
        end, tick, running, events = i + tlen, 0, None, []

        while i < end:
            delta, i = read_vlq(d, i)
            tick += delta
            status = d[i]

            if status == 0xFF:
                mtype = d[i + 1]
                mlen, j = read_vlq(d, i + 2)
                payload = d[j : j + mlen]
                i = j + mlen
                if mtype == 0x51:
                    tempo = int.from_bytes(payload, "big")
                elif mtype == 0x58 and len(payload) >= 2:
                    meter = f"{payload[0]}/{1 << payload[1]}"
                elif mtype == 0x03 and title is None:
                    title = payload.decode("ascii", "replace")
                elif mtype == 0x05:
                    events.append((tick, "lyric", payload.decode("ascii", "replace")))
                continue
            if status in (0xF0, 0xF7):
                slen, j = read_vlq(d, i + 1)
                i = j + slen
                continue

            if status & 0x80:
                running = status
                i += 1
            kind, chan = running & 0xF0, running & 0x0F
            if kind in (0xC0, 0xD0):
                i += 1
                continue
            d1, d2 = d[i], d[i + 1]
            i += 2

            if kind == 0x90 and d2 > 0:
                events.append((tick, "on", chan, d1, d2))
            elif kind == 0x80 or (kind == 0x90 and d2 == 0):
                events.append((tick, "off", chan, d1))
            elif kind == 0xB0:
                events.append((tick, "cc", chan, d1, d2))

        tracks.append(events)
        i = end

    return div, tempo, meter, title, tracks


# ------------------------------------------------------------ note building --
def notes_from(events):
    """Pair note-ons with note-offs -> [(start, end, chan, pitch, vel)]."""
    open_notes, out = {}, []
    for ev in events:
        if ev[1] == "on":
            _t, _k, chan, pitch, vel = ev
            if (chan, pitch) in open_notes:       # re-articulation without an off
                s, v = open_notes.pop((chan, pitch))
                out.append((s, ev[0], chan, pitch, v))
            open_notes[(chan, pitch)] = (ev[0], vel)
        elif ev[1] == "off":
            _t, _k, chan, pitch = ev
            if (chan, pitch) in open_notes:
                s, v = open_notes.pop((chan, pitch))
                out.append((s, ev[0], chan, pitch, v))
    for (chan, pitch), (s, v) in open_notes.items():
        out.append((s, s, chan, pitch, v))        # unterminated; zero length
    return sorted(out)


def monophonic(notes):
    """Last-note priority, like the firmware: a new note cuts the sounding one,
    and when it ends an older note that is still held resumes.

    Event-driven, so a note that ends exactly where the next begins is not
    mistaken for an overlap: at equal timestamps, offs are processed first.
    """
    events = []
    for idx, (start, end, _chan, pitch, vel) in enumerate(sorted(notes)):
        if end <= start:
            continue
        events.append((start, 1, idx, pitch, vel))   # 1 = on
        events.append((end, 0, idx, pitch, vel))     # 0 = off, sorts first
    events.sort(key=lambda e: (e[0], e[1]))

    out, stack, seg_start = [], [], None
    for tick, kind, idx, pitch, vel in events:
        before = stack[-1] if stack else None
        if kind == 0:
            stack = [x for x in stack if x[0] != idx]
        else:
            stack.append((idx, pitch, vel))
        after = stack[-1] if stack else None

        if after != before:
            if before is not None and seg_start is not None and tick > seg_start:
                out.append((seg_start, tick, before[1], before[2]))
            seg_start = tick if after is not None else None
    return sorted(out)


def pick_melody_track(tracks):
    best, best_score = None, -1
    for idx, events in enumerate(tracks):
        ns = notes_from(events)
        score = sum(1 for n in ns if VOCAL_LO <= n[3] <= VOCAL_HI)
        if score > best_score:
            best, best_score = idx, score
    if best_score <= 0:
        raise SystemExit("no track contains notes in vocal range; use --track N")
    return best


# ------------------------------------------------------------------ convert --
def convert(path, unit_beats, track_override, name):
    ppq, tempo, meter, title, tracks = parse_midi(path)
    grid = max(1, round(unit_beats * ppq))
    q = lambda t: round(t / grid) * grid

    all_events = [e for tr in tracks for e in tr]
    by_channel = {}
    for n in notes_from(all_events):
        by_channel.setdefault(n[2], []).append(n)

    # Channels 1/2/3 present? Then the file already speaks our dialect.
    if any(c in by_channel for c in (0, 1, 2)):
        voice_notes = {v: monophonic(by_channel.get(c, []))
                       for c, v in enumerate(VOICES)}
        cc_channel = {v: c for c, v in enumerate(VOICES)}
    else:
        idx = track_override if track_override is not None else pick_melody_track(tracks)
        if not 0 <= idx < len(tracks):
            raise SystemExit(f"--track {idx} out of range (file has {len(tracks)})")
        picked = notes_from(tracks[idx])
        voice_notes = {"sop": monophonic(picked), "alto": [], "bass": []}
        cc_channel = {"sop": picked[0][2] if picked else 0, "alto": 0, "bass": 0}

    if not any(voice_notes.values()):
        raise SystemExit(f"{path}: no notes found")

    lyrics = {}
    for tr in tracks:
        for e in tr:
            if e[1] == "lyric":
                lyrics[e[0]] = e[2]

    ccs = {}                       # (channel, cc) -> [(tick, value)]
    for e in all_events:
        if e[1] == "cc":
            ccs.setdefault((e[2], e[3]), []).append((e[0], e[4]))
    for v in ccs.values():
        v.sort()

    def cc_at(chan, num, tick):
        vals = [val for t, val in ccs.get((chan, num), []) if t <= tick]
        return vals[-1] if vals else None

    # Quantised note table per voice, keyed by start
    grid_notes = {}
    for voice, ns in voice_notes.items():
        table = {}
        for start, end, pitch, vel in ns:
            s = q(start)
            e = max(s + grid, q(end + grid // 2))   # never shorter than one unit
            table[s] = (e, pitch, vel)
        grid_notes[voice] = table

    onsets = sorted({s for tbl in grid_notes.values() for s in tbl})

    # Vowel fallback: pitch height across each voice's own range
    have_cc1 = any((c, 1) in ccs for c in cc_channel.values())
    lo = min(p for tbl in grid_notes.values() for (_e, p, _v) in tbl.values())
    hi = max(p for tbl in grid_notes.values() for (_e, p, _v) in tbl.values())

    def vowel_for(pitch, chan, tick):
        existing = cc_at(chan, 1, tick)
        if have_cc1 and existing is not None:
            return existing
        if hi == lo:
            return (VOWEL_LO + VOWEL_HI) // 2
        return round(VOWEL_LO + (pitch - lo) / (hi - lo) * (VOWEL_HI - VOWEL_LO))

    rows = []
    for i, t in enumerate(onsets):
        row = {v: None for v in VOICES}
        extent, vel, lead = t, None, None
        for v in VOICES:
            hit = grid_notes[v].get(t)
            if hit:
                end, pitch, vv = hit
                row[v] = pitch
                extent = max(extent, end)
                if lead is None:
                    lead, vel = v, vv

        nxt = onsets[i + 1] if i + 1 < len(onsets) else extent
        sound = min(extent, nxt) if nxt > t else extent
        chan = cc_channel[lead]
        glide_cc = cc_at(chan, 3, t)

        rows.append({
            "sop": row["sop"], "alto": row["alto"], "bass": row["bass"],
            "beats": (sound - t) / ppq,
            "vowelCC": vowel_for(row[lead], chan, t),
            "syllable": lyrics.get(t, ""),
            "velocity": vel,
            "glide": "" if not glide_cc else ("w" if glide_cc < 64 else "l"),
        })
        if nxt > sound:                             # a genuine rest
            rows.append({"sop": None, "alto": None, "bass": None,
                         "beats": (nxt - sound) / ppq, "vowelCC": 0,
                         "syllable": "", "velocity": 0, "glide": ""})

    for r in rows:                                  # tidy 2.0 -> 2
        if r["beats"] == int(r["beats"]):
            r["beats"] = int(r["beats"])

    return {
        "name": name or title or path.stem.replace("_", " ").title(),
        "meter": meter,
        "quarterMs": round(tempo / 1000),
        "gapMs": 60,
        "source": f"transcribed from {path.name} by tools/midi_to_song.py",
        "notes": rows,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("midi", type=pathlib.Path)
    ap.add_argument("-o", "--out", type=pathlib.Path, default=None)
    ap.add_argument("--unit", default="eighth",
                    help="quantisation grid: quarter, eighth, sixteenth, triplet, "
                         "or a number in quarter notes (default: eighth)")
    ap.add_argument("--track", type=int, default=None,
                    help="force the melody track index (only used when the file "
                         "has no channel 1/2/3 layout)")
    ap.add_argument("--name", default=None)
    args = ap.parse_args(argv)

    unit = UNITS.get(args.unit)
    if unit is None:
        try:
            unit = float(args.unit)
        except ValueError:
            raise SystemExit(f"--unit: expected one of {list(UNITS)} or a number")

    song = convert(args.midi, unit, args.track, args.name)
    text = json.dumps(song, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)
        voices = [v for v in VOICES if any(n[v] is not None for n in song["notes"])]
        print(f"{args.out}  {len(song['notes'])} rows  {', '.join(voices)}  "
              f"quarterMs {song['quarterMs']}")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
