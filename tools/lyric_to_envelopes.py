#!/usr/bin/env python3
"""Analyse a song's lyric with eSpeak NG into 14-band envelopes.

    .venv-vocoder/bin/python tools/lyric_to_envelopes.py songs/amazing_grace.json \
        -o songs/amazing_grace.envelopes.npz

Replaces the hand-written consonant recipes with measurement. Each syllable is
spoken by eSpeak offline, analysed through the SAME Q=4.5 filter bank the
renderer synthesises with, segmented into onset / vowel nucleus / coda, and
emitted as band envelopes plus per-frame voicing.

Why this beats the recipes: eSpeak has the whole phoneme set. "poor" is p'U@,
a real /p/, where the recipe table had no p at all and voiced it as b; "the" is
D'@, a real voiced th, where the table used d. It also ends the business of
guessing what an /f/ looks like and then tuning it by ear.

WHICH RULES ARE APPLIED HERE, and which are not:

  rule 1  levels and HF tilt   APPLIED HERE — a property of the consonant data
  rule 2  asymmetric smear     applied by the renderer, on the assembled note
  rule 3  articulation dip     applied by the renderer
  rule 4  hard-zero tails      applied by the renderer

So this file emits PRE-SMEAR frames. The renderer still owns note assembly,
which keeps one implementation of rules 2-4 rather than two that can drift.

Time-stretch policy: the consonant head and tail run at natural speed; only the
vowel steady-state is stretched to fill the note. Stretching a consonant is
what makes synthetic singing sound drunk.

Needs espeak-ng (brew install espeak-ng) and the vocoder venv.
Runs espeak locally and reads local files only; nothing is fetched.
"""

import argparse
import json
import pathlib
import subprocess
import sys
import tempfile
import wave

import numpy as np
from scipy.signal import butter, sosfilt, resample_poly

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from vocoder_render import BANDS, NB, BANK_Q, SR, FR, tilt_hf

PITCH_LO, PITCH_HI = 70.0, 400.0     # search range for the voicing estimate
# All thresholds are RELATIVE to the syllable's own peak. Absolute ones do not
# survive contact with real data: the autocorrelation voicing estimate tops out
# around 0.7-0.8 rather than 1.0, and it varies per phoneme, so a fixed 0.6 cut
# threw whole words ("how", "like", "wretch") into a zero-length vowel.
ACTIVE_FLOOR = 0.12                  # trims eSpeak's trailing decay too
NUCLEUS_VOICED = 0.70                # share of this syllable's own max voicing
NUCLEUS_ENERGY = 0.35


def speak(text, wpm, tmp):
    """Synthesize one syllable with eSpeak, resampled to our rate."""
    path = pathlib.Path(tmp) / "syl.wav"
    subprocess.run(["espeak-ng", "-v", "en", "-s", str(wpm), "-w", str(path), text],
                   check=True, capture_output=True)
    with wave.open(str(path)) as w:
        sr = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    x = x.astype(float)/32768
    return resample_poly(x, SR, sr) if sr != SR else x


def phonemes(text):
    r = subprocess.run(["espeak-ng","-v","en","-q","-x",text],
                       capture_output=True, text=True)
    return r.stdout.strip()


def band_envelope(x):
    """Through the same bank the renderer synthesises with, so analysis and
    resynthesis agree. RMS per 10 ms frame."""
    hop = int(SR*FR); F = max(1, len(x)//hop)
    out = np.zeros((NB, F))
    for b in range(NB):
        bw = BANDS[b]/BANK_Q
        sos = butter(2, [max(20, BANDS[b]-bw/2), min(SR/2-100, BANDS[b]+bw/2)],
                     "band", fs=SR, output="sos")
        y = sosfilt(sos, x)
        for i in range(F):
            seg = y[i*hop:(i+1)*hop]
            out[b, i] = np.sqrt(np.mean(seg**2)) if len(seg) else 0.0
    return out


def voicing(x, nframes):
    """Normalised autocorrelation peak, 40 ms window — two periods at the
    bottom of the range. A 20 ms window reads vowels at 0.5 and is useless."""
    hop = int(SR*FR); win = int(SR*0.04)
    lo, hi = int(SR/PITCH_HI), int(SR/PITCH_LO)
    out = np.zeros(nframes)
    for i in range(nframes):
        c = i*hop; a = max(0, c-win//2); seg = x[a:a+win]
        if len(seg) < win or np.sqrt(np.mean(seg**2)) < 2e-4:
            continue
        seg = seg - seg.mean()
        e0 = float(seg @ seg)
        if e0 <= 0:
            continue
        best = 0.0
        for lag in range(lo, min(hi, len(seg)-1), 2):
            t = seg[lag:]; et = float(t @ t)
            if et > 0:
                best = max(best, float(seg[:len(t)] @ t)/np.sqrt(e0*et))
        out[i] = float(np.clip(best, 0, 1))
    return out


def segment(bands, voi):
    """-> (start, nucleus_start, nucleus_end, end) as frame indices."""
    energy = bands.sum(0)
    if energy.max() <= 0:
        return 0, 0, len(energy), len(energy)
    e = energy/energy.max()
    active = [i for i in range(len(e)) if e[i] > ACTIVE_FLOOR]
    if not active:
        return 0, 0, len(e), len(e)
    lo, hi = active[0], active[-1]

    # Grow outward from the loudest frame while it stays voiced and loud.
    # A "longest contiguous run" fails on diphthongs — the spectrum moves
    # through eI / aU / aI and the run breaks in the middle, which put 26
    # frames of "onset" in front of a word that begins with a vowel.
    vmax = voi[lo:hi+1].max()
    if vmax <= 0.15:                       # nothing periodic: all onset
        return lo, hi+1, hi+1, hi+1
    vn = voi/vmax
    peak = int(np.argmax(e[lo:hi+1])) + lo
    ns = ne = peak
    while ns-1 >= lo and vn[ns-1] > NUCLEUS_VOICED and e[ns-1] > NUCLEUS_ENERGY:
        ns -= 1
    while ne+1 <= hi and vn[ne+1] > NUCLEUS_VOICED and e[ne+1] > NUCLEUS_ENERGY:
        ne += 1
    return lo, ns, ne+1, hi+1


def analyse_syllable(text, wpm, tmp, tilt=True):
    x = speak(text, wpm, tmp)
    bands = band_envelope(x)
    voi = voicing(x, bands.shape[1])
    lo, ns, ne, hi = segment(bands, voi)

    bands, voi = bands[:, lo:hi], voi[lo:hi]
    ns, ne = ns-lo, ne-lo

    peak = bands[:, ns:ne].max() if ne > ns else bands.max()
    if peak > 0:
        bands = bands/peak                 # nucleus peaks at 1.0

    # Rule 1: consonants sit 10-15 dB under the vowel in 2-8 kHz, with the HF
    # tilt. Measured data has its own natural balance, so this is a house-sound
    # constraint imposed on top, not a correction.
    hf = [b for b in range(NB) if BANDS[b] >= 2000]
    nuc_hf = bands[np.ix_(hf, range(ns, ne))].mean() if ne > ns else 0.0
    for span in ((0, ns), (ne, bands.shape[1])):
        if span[1] <= span[0]:
            continue
        seg = bands[:, span[0]:span[1]]
        seg_hf = seg[hf].mean()
        if seg_hf > 0 and nuc_hf > 0:
            target = nuc_hf * 10**(-12.5/20)       # midpoint of 10-15 dB
            seg *= min(1.0, target/seg_hf)
        if tilt:
            for i in range(seg.shape[1]):
                seg[:, i] = tilt_hf(seg[:, i])
    return dict(bands=bands, voi=voi, ns=ns, ne=ne, phon=phonemes(text))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("song", type=pathlib.Path)
    ap.add_argument("-o", "--out", type=pathlib.Path, required=True)
    ap.add_argument("--wpm", type=int, default=130,
                    help="eSpeak rate. Lower gives longer, steadier vowels to "
                         "stretch from (default 130)")
    ap.add_argument("--no-tilt", action="store_true",
                    help="skip rule 1's HF tilt. Measured spectra already carry "
                         "their own tilt, so applying it again is arguably a "
                         "double-tilt — kept on by default because the rule says so")
    args = ap.parse_args(argv)

    song = json.loads(args.song.read_text())
    sylls = sorted({n["syllable"] for n in song["notes"] if n.get("syllable")})
    if not sylls:
        raise SystemExit(f"{args.song.name} has no syllables to analyse")

    store = {}
    with tempfile.TemporaryDirectory() as tmp:
        print(f"{len(sylls)} distinct syllables, eSpeak at {args.wpm} wpm\n")
        print(f"  {'syllable':<10}{'phonemes':<14}{'frames':>8}{'onset':>7}"
              f"{'vowel':>7}{'coda':>6}")
        for s in sylls:
            d = analyse_syllable(s, args.wpm, tmp, not args.no_tilt)
            store[f"{s}/bands"] = d["bands"].astype(np.float32)
            store[f"{s}/voi"] = d["voi"].astype(np.float32)
            store[f"{s}/seg"] = np.array([d["ns"], d["ne"]], dtype=np.int32)
            n = d["bands"].shape[1]
            print(f"  {s:<10}{d['phon']:<14}{n:>8}{d['ns']:>7}"
                  f"{d['ne']-d['ns']:>7}{n-d['ne']:>6}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.out, syllables=np.array(sylls), **store)
    kb = args.out.stat().st_size/1024
    print(f"\n{args.out}  {len(sylls)} syllables  {kb:.1f} kB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
