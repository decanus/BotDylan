#!/usr/bin/env python3
"""Acceptance test for the audio pipeline, on audio we synthesize ourselves.

Renders a song to a sine WAV, runs it back through audio_to_song.py, and
checks the notes survived. No recording is downloaded and none is needed —
the test signal is generated from a song already in the repo.

    python3 tools/audio_pipeline_test.py

Only exercises --transcriber naive, which is the path that needs no install.
"""

import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"

# song, bpm to quantise against, how exact we demand
CASES = [("ode_to_joy.json", 125, 1.0)]


def run(*args):
    r = subprocess.run([sys.executable, *map(str, args)],
                       capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"failed: {' '.join(map(str, args))}\n{r.stdout}\n{r.stderr}")
    return r


def main():
    failures = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        for filename, bpm, want in CASES:
            src = ROOT / "songs" / filename
            wav = tmp / (src.stem + ".wav")
            out = tmp / (src.stem + ".back.json")

            run(TOOLS / "song_to_wav.py", src, "-o", wav, "--voices", "sop")
            run(TOOLS / "audio_to_song.py", wav, "-o", out, "--bpm", bpm)

            original = [n["sop"] for n in json.loads(src.read_text())["notes"]
                        if n["sop"] is not None]
            beats = [n["beats"] for n in json.loads(src.read_text())["notes"]
                     if n["sop"] is not None]
            back = json.loads(out.read_text())["notes"]
            got = [n["sop"] for n in back if n["sop"] is not None]
            got_beats = [n["beats"] for n in back if n["sop"] is not None]

            print(f"{filename}: {len(original)} notes in, {len(got)} out")
            if len(got) != len(original):
                print(f"  note count {len(original)} -> {len(got)}")
                failures.append(filename)
                continue

            pitch_ok = sum(1 for a, b in zip(original, got) if a == b) / len(original)
            beat_ok = sum(1 for a, b in zip(beats, got_beats) if a == b) / len(beats)
            print(f"  pitches   {pitch_ok * 100:5.1f}% exact")
            print(f"  durations {beat_ok * 100:5.1f}% exact")
            if pitch_ok < want or beat_ok < want:
                failures.append(filename)

    if failures:
        print(f"\nAUDIO PIPELINE FAILED: {', '.join(failures)}")
        return 1
    print("\nAUDIO PIPELINE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
