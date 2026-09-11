#!/usr/bin/env python3
"""Render a song JSON to a plain sine-wave WAV.

Two uses: hearing a transcription without opening a browser, and generating
known-good test audio for the audio_to_song.py pipeline — which is how that
pipeline gets tested without downloading anyone's recording.

    python3 tools/song_to_wav.py songs/ode_to_joy.json -o /tmp/ode.wav
    python3 tools/song_to_wav.py songs/amazing_grace.json --voices sop

Deliberately a bare sine per voice: no formants, no vibrato. The point is a
signal whose pitches are known exactly, not a good impression of the robot.

Standard library only. Reads local files only.
"""

import argparse
import array
import json
import math
import pathlib
import wave

VOICES = ["sop", "alto", "bass"]


def render(song, rate, voices, amplitude=0.22):
    quarter_ms = song["quarterMs"]
    gap_ms = song.get("gapMs", 60)
    total_ms = sum(n["beats"] * quarter_ms for n in song["notes"]) + 500
    buf = array.array("d", [0.0]) * int(rate * total_ms / 1000)

    t_ms = 0.0
    for note in song["notes"]:
        dur_ms = max(1.0, note["beats"] * quarter_ms - gap_ms)
        start = int(rate * t_ms / 1000)
        n = int(rate * dur_ms / 1000)
        vel = (note.get("velocity") or 0) / 127.0

        for v in voices:
            pitch = note.get(v)
            if pitch is None:
                continue
            freq = 440.0 * (2.0 ** ((pitch - 69) / 12.0))
            step = 2.0 * math.pi * freq / rate
            fade = max(1, int(rate * 0.008))        # 8 ms, to avoid clicks
            for i in range(n):
                if start + i >= len(buf):
                    break
                env = min(1.0, i / fade, (n - i) / fade)
                buf[start + i] += amplitude * vel * env * math.sin(step * i)
        t_ms += note["beats"] * quarter_ms

    peak = max((abs(x) for x in buf), default=1.0) or 1.0
    scale = (0.89 / peak) if peak > 0.89 else 1.0
    return array.array("h", (int(max(-1.0, min(1.0, x * scale)) * 32767) for x in buf))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("song", type=pathlib.Path)
    ap.add_argument("-o", "--out", type=pathlib.Path, required=True)
    ap.add_argument("--rate", type=int, default=22050)
    ap.add_argument("--voices", default="sop,alto,bass",
                    help="which voices to render (default: all)")
    args = ap.parse_args(argv)

    song = json.loads(args.song.read_text())
    voices = [v.strip() for v in args.voices.split(",") if v.strip() in VOICES]
    samples = render(song, args.rate, voices)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(args.out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(args.rate)
        w.writeframes(samples.tobytes())

    print(f"{args.out}  {len(samples) / args.rate:.1f}s  {args.rate} Hz mono  "
          f"voices: {', '.join(voices)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
