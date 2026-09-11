#!/usr/bin/env python3
"""Turn a recording — a hummed phone memo, say — into a song JSON.

    python3 tools/audio_to_song.py hum.wav -o songs/new.json
    python3 tools/audio_to_song.py take.mp3 --separate --transcriber basicpitch
    python3 tools/audio_to_song.py hum.wav --key Am --min-ms 120

Stages, each skippable:

  1. separation   optional, --separate, isolates the vocal with Demucs.
                  Skip it for clean input; a hummed memo needs nothing.
  2. transcription  --transcriber naive (default) or basicpitch.
  3. cleanup      length threshold, same-pitch merging, optional key snap,
                  octave-outlier collapse. Shared by both transcribers.
  4. conversion   the cleaned notes go out as MIDI, then through
                  midi_to_song.py, so there is one path into songs/*.json.

Both the cleaned .mid and the final .json are written: the MIDI is what you
open in a DAW when the transcription needs a human fix.

THE DEFAULT TRANSCRIBER NEEDS NOTHING INSTALLED. It is pure standard library
autocorrelation pitch tracking — good enough for a clean monophonic hum, which
is the intended input, and not much else. For anything polyphonic or noisy,
install the extras (see tools/requirements-audio.txt) and pass
--transcriber basicpitch.

This tool reads local files only. It never fetches audio or MIDI from anywhere.
"""

import argparse
import array
import json
import math
import pathlib
import struct
import subprocess
import sys
import tempfile
import wave
from operator import mul

# --- naive transcriber settings -------------------------------------------
WORK_RATE = 8000          # everything is decimated to this before analysis
FRAME = 400               # 50 ms
HOP = 200                 # 25 ms
F_LO, F_HI = 80.0, 800.0  # the range the naive tracker will look in

SCALES = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],
}
NOTE_NAMES = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}


# ------------------------------------------------------------------ audio ---
def load_mono(path):
    """-> (samples at WORK_RATE as array('d'), original rate). Uses ffmpeg for
    anything that is not already a PCM wav, since stdlib reads wav only."""
    src = path
    tmp = None
    if path.suffix.lower() != ".wav":
        tmp = pathlib.Path(tempfile.mkstemp(suffix=".wav")[1])
        run_ffmpeg(path, tmp)
        src = tmp

    try:
        with wave.open(str(src), "rb") as w:
            if w.getsampwidth() != 2:
                tmp2 = pathlib.Path(tempfile.mkstemp(suffix=".wav")[1])
                run_ffmpeg(src, tmp2)
                src = tmp2
                w2 = wave.open(str(src), "rb")
                chans, rate, raw = w2.getnchannels(), w2.getframerate(), w2.readframes(w2.getnframes())
                w2.close()
            else:
                chans, rate = w.getnchannels(), w.getframerate()
                raw = w.readframes(w.getnframes())
    finally:
        if tmp and tmp.exists():
            tmp.unlink()

    pcm = array.array("h")
    pcm.frombytes(raw)
    if chans > 1:
        pcm = array.array("h", (sum(pcm[i:i + chans]) // chans
                                for i in range(0, len(pcm) - chans + 1, chans)))

    # Box-filter then decimate to WORK_RATE. Crude anti-aliasing, but the
    # fundamental is what matters and it keeps this dependency-free.
    factor = max(1, int(round(rate / WORK_RATE)))
    if factor > 1:
        out = array.array("d")
        inv = 1.0 / (factor * 32768.0)
        for i in range(0, len(pcm) - factor + 1, factor):
            out.append(sum(pcm[i:i + factor]) * inv)
        return out, rate / factor
    return array.array("d", (s / 32768.0 for s in pcm)), rate


def run_ffmpeg(src, dest):
    try:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
                        "-ac", "1", "-ar", str(WORK_RATE), "-sample_fmt", "s16",
                        str(dest)], check=True)
    except FileNotFoundError:
        raise SystemExit("ffmpeg is needed to read anything but a 16-bit WAV.\n"
                         "  brew install ffmpeg")
    except subprocess.CalledProcessError as e:
        raise SystemExit(f"ffmpeg failed on {src}: {e}")


# ---------------------------------------------------------- transcription ---
def track_pitch(samples, rate, rms_floor):
    """Autocorrelation pitch track -> [(time_s, midi_float or None)]."""
    lo_lag = max(2, int(rate / F_HI))
    hi_lag = min(FRAME - 1, int(rate / F_LO))
    out = []

    for start in range(0, max(0, len(samples) - FRAME), HOP):
        frame = samples[start:start + FRAME]
        energy = sum(map(mul, frame, frame))
        rms = math.sqrt(energy / FRAME)
        t = start / rate

        if rms < rms_floor:
            out.append((t, None, rms))
            continue

        mean = sum(frame) / FRAME
        frame = array.array("d", (x - mean for x in frame))
        e0 = sum(map(mul, frame, frame)) or 1e-12

        best, best_r = 0, 0.0
        scores = {}
        for lag in range(lo_lag, hi_lag):
            tail = frame[lag:]
            ac = sum(map(mul, frame, tail))
            et = sum(map(mul, tail, tail)) or 1e-12
            r = ac / math.sqrt(e0 * et)
            scores[lag] = r
            if r > best_r:
                best, best_r = lag, r

        if best_r < 0.5:
            out.append((t, None, rms))
            continue

        # Octave-down guard: autocorrelation loves 2x the true period. If half
        # the winning lag scores nearly as well, the shorter one is the truth.
        half = best // 2
        if half >= lo_lag and scores.get(half, 0.0) > 0.85 * best_r:
            best = half

        freq = rate / best
        out.append((t, 69.0 + 12.0 * math.log2(freq / 440.0), rms))
    return out


def rms_envelope(samples, rate, win_ms=10.0, hop_ms=5.0):
    """A much finer energy track than the pitch frames. Note boundaries come
    from here: a 50 ms analysis window cannot see a 60 ms re-articulation gap,
    because the window still straddles the notes on either side of it."""
    win = max(8, int(rate * win_ms / 1000))
    hop = max(1, int(rate * hop_ms / 1000))
    env = []
    for start in range(0, max(0, len(samples) - win), hop):
        frame = samples[start:start + win]
        env.append((start / rate, math.sqrt(sum(map(mul, frame, frame)) / win)))
    return env


def sounding_segments(env, floor, hop_ms=5.0):
    """Contiguous runs of audible energy -> [(start_s, end_s)]."""
    segs, cur = [], None
    for t, r in env:
        if r >= floor:
            cur = [t, t] if cur is None else [cur[0], t]
        elif cur:
            segs.append((cur[0], cur[1] + hop_ms / 1000.0))
            cur = None
    if cur:
        segs.append((cur[0], cur[1] + hop_ms / 1000.0))
    return segs


def frames_to_notes(track, env, min_ms, rms_floor):
    """Segment on energy first, then split each segment where the pitch moves.

    Two things end a note: silence, and a change of pitch. Doing energy first
    is what makes repeated notes survive — without it a run of the same pitch
    across a short gap reads as one long note.
    """
    pitches = [p for _t, p, _r in track]
    smoothed = []
    for i in range(len(pitches)):
        window = [p for p in pitches[max(0, i - 2):i + 3] if p is not None]
        if len(window) < 2:
            smoothed.append(None)
        else:
            window.sort()
            smoothed.append(window[len(window) // 2])

    half = FRAME / (2.0 * WORK_RATE)          # frame centre, not frame start
    centres = [(t + half, smoothed[i], track[i][2]) for i, (t, _p, _r) in enumerate(track)]

    notes = []
    for seg_start, seg_end in sounding_segments(env, rms_floor):
        inside = [(t, p, r) for t, p, r in centres if seg_start <= t < seg_end and p is not None]
        if not inside:
            continue

        cur = None
        for t, p, r in inside:
            semitone = int(round(p))
            if cur and cur["pitch"] == semitone:
                cur["end"] = t
                cur["rms"] = max(cur["rms"], r)
                continue
            if cur:
                notes.append(cur)
            cur = {"pitch": semitone, "start": t, "end": t, "rms": r}
        if cur:
            notes.append(cur)

        # Stretch the first and last note of a segment out to the segment's own
        # edges: the energy gate knows where the sound really started and ended.
        first = next((n for n in notes if n["start"] >= seg_start), None)
        if first:
            first["start"] = seg_start
        last = notes[-1] if notes else None
        if last and last["end"] < seg_end:
            last["end"] = seg_end

    return [n for n in notes if (n["end"] - n["start"]) * 1000 >= min_ms]


# --------------------------------------------------------------- cleanup ----
def parse_key(text):
    t = text.strip().lower()
    if not t:
        return None
    root = NOTE_NAMES.get(t[0])
    if root is None:
        raise SystemExit(f"--key: don't understand {text!r} (try Am, C, F#m)")
    i = 1
    if i < len(t) and t[i] in "#b":
        root += 1 if t[i] == "#" else -1
        i += 1
    mode = "minor" if t[i:].startswith("m") else "major"
    return root % 12, SCALES[mode]


def cleanup(notes, min_ms, merge_ms, key, collapse):
    notes = sorted(notes, key=lambda n: n["start"])

    merged = []
    for n in notes:
        if merged and n["pitch"] == merged[-1]["pitch"] and \
                (n["start"] - merged[-1]["end"]) * 1000 <= merge_ms:
            merged[-1]["end"] = n["end"]
            merged[-1]["rms"] = max(merged[-1]["rms"], n["rms"])
        else:
            merged.append(dict(n))
    notes = [n for n in merged if (n["end"] - n["start"]) * 1000 >= min_ms]

    if collapse and len(notes) >= 3:
        pitches = sorted(n["pitch"] for n in notes)
        median = pitches[len(pitches) // 2]
        for n in notes:
            while n["pitch"] - median > 7:
                n["pitch"] -= 12
            while median - n["pitch"] > 7:
                n["pitch"] += 12

    if key:
        root, scale = key
        for n in notes:
            if (n["pitch"] - root) % 12 not in scale:
                for delta in (-1, 1, -2, 2):
                    if (n["pitch"] + delta - root) % 12 in scale:
                        n["pitch"] += delta
                        break
    return notes


# ------------------------------------------------------------ midi output ---
def vlq(n):
    out = bytearray([n & 0x7F])
    n >>= 7
    while n:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    return bytes(reversed(out))


def write_midi(notes, path, bpm, ppq=480):
    quarter_s = 60.0 / bpm
    events = []
    for n in notes:
        on = int(round(n["start"] / quarter_s * ppq))
        off = max(on + 1, int(round(n["end"] / quarter_s * ppq)))
        vel = max(40, min(110, int(40 + n["rms"] * 400)))
        events.append((on, 0, bytes([0x90, n["pitch"], vel])))
        events.append((off, 1, bytes([0x80, n["pitch"], 0])))

    body = bytearray()
    body += vlq(0) + b"\xff\x51\x03" + struct.pack(">I", int(60_000_000 / bpm))[1:]
    prev = 0
    for tick, order, data in sorted(events, key=lambda e: (e[0], e[1])):
        body += vlq(tick - prev) + data
        prev = tick
    body += vlq(0) + b"\xff\x2f\x00"

    head = b"MThd" + struct.pack(">I", 6) + struct.pack(">HHH", 0, 1, ppq)
    path.write_bytes(head + b"MTrk" + struct.pack(">I", len(body)) + bytes(body))


# ----------------------------------------------------------- optional deps --
def separate_vocal(path, workdir):
    try:
        import demucs.separate  # noqa: F401
    except ImportError:
        raise SystemExit(
            "--separate needs Demucs, which is not installed.\n"
            "  python3 -m venv .venv-audio && .venv-audio/bin/pip install "
            "-r tools/requirements-audio.txt\n"
            "See the README, 'Teaching the robot songs'.")
    out = workdir / "demucs"
    subprocess.run([sys.executable, "-m", "demucs", "--two-stems=vocals",
                    "-o", str(out), str(path)], check=True)
    stems = list(out.rglob("vocals.wav"))
    if not stems:
        raise SystemExit("Demucs produced no vocals stem")
    return stems[0]


def transcribe_basicpitch(path, workdir):
    try:
        from basic_pitch.inference import predict
    except ImportError:
        raise SystemExit(
            "--transcriber basicpitch needs Basic Pitch, which is not installed.\n"
            "  python3 -m venv .venv-audio && .venv-audio/bin/pip install "
            "-r tools/requirements-audio.txt\n"
            "The default --transcriber naive needs nothing.")
    _model, _midi, note_events = predict(str(path))
    return [{"pitch": int(p), "start": float(s), "end": float(e),
             "rms": float(amp)} for s, e, p, amp, *_ in note_events]


# -------------------------------------------------------------------- main --
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("audio", type=pathlib.Path)
    ap.add_argument("-o", "--out", type=pathlib.Path, required=True)
    ap.add_argument("--separate", action="store_true",
                    help="isolate the vocal with Demucs first (needs extras)")
    ap.add_argument("--transcriber", choices=["naive", "basicpitch"], default="naive")
    ap.add_argument("--bpm", type=float, default=120.0,
                    help="tempo to quantise against (default: 120)")
    ap.add_argument("--unit", default="eighth", help="passed to midi_to_song.py")
    ap.add_argument("--min-ms", type=float, default=80.0,
                    help="drop notes shorter than this (default: 80)")
    ap.add_argument("--merge-ms", type=float, default=40.0,
                    help="merge same-pitch notes across gaps up to this. Must "
                         "stay BELOW the re-articulation gap (60 ms) or "
                         "repeated notes fuse into one (default: 40)")
    ap.add_argument("--key", default="",
                    help="snap to a key, e.g. Am or C (default: no snapping)")
    ap.add_argument("--no-collapse", action="store_true",
                    help="keep octave outliers instead of folding them in")
    ap.add_argument("--rms-floor", type=float, default=0.012,
                    help="silence threshold for the naive transcriber")
    ap.add_argument("--name", default=None)
    args = ap.parse_args(argv)

    if not args.audio.exists():
        raise SystemExit(f"{args.audio}: no such file")

    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        source = args.audio

        if args.separate:
            print("separating vocal stem with Demucs ...")
            source = separate_vocal(source, tmp)

        if args.transcriber == "basicpitch":
            print("transcribing with Basic Pitch ...")
            raw = transcribe_basicpitch(source, tmp)
        else:
            print(f"transcribing {source.name} (naive autocorrelation) ...")
            samples, rate = load_mono(source)
            print(f"  {len(samples) / rate:.1f}s at {rate:.0f} Hz")
            track = track_pitch(samples, rate, args.rms_floor)
            voiced = sum(1 for _t, p, _r in track if p is not None)
            env = rms_envelope(samples, rate)
            segs = sounding_segments(env, args.rms_floor)
            print(f"  {len(track)} pitch frames ({voiced} voiced), "
                  f"{len(segs)} sounding segments")
            raw = frames_to_notes(track, env, args.min_ms, args.rms_floor)

        print(f"  {len(raw)} raw notes")
        notes = cleanup(raw, args.min_ms, args.merge_ms,
                        parse_key(args.key), not args.no_collapse)
        print(f"  {len(notes)} after cleanup")
        if not notes:
            raise SystemExit("nothing survived transcription — try lowering "
                             "--rms-floor or --min-ms")

        mid = args.out.with_suffix(".mid")
        mid.parent.mkdir(parents=True, exist_ok=True)
        write_midi(notes, mid, args.bpm)
        print(f"  wrote {mid}")

        cmd = [sys.executable, str(pathlib.Path(__file__).with_name("midi_to_song.py")),
               str(mid), "-o", str(args.out), "--unit", args.unit]
        if args.name:
            cmd += ["--name", args.name]
        subprocess.run(cmd, check=True)

    print("\nListen to it before it goes into songs/ — the pipeline transcribes, "
          "your ear signs off.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
