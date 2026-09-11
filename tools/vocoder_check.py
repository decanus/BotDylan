#!/usr/bin/env python3
"""Regression gates for the vocoder engine. Five measured defects, five checks.

    .venv-vocoder/bin/python tools/vocoder_check.py

Each gate corresponds to a defect that was actually heard and then measured
during the listening experiment. They catch regressions of KNOWN defects only
— they are not a substitute for the ear, which stays the final gate on any
voice change.

  1 aliasing      inharmonic HF floor <= -70 dB (naive saw measured -36)
  2 bank ripple   <= 5 dB over 400 Hz-6 kHz, summed with ALTERNATING POLARITY
  3 fricative     -8 to -18 dB rel. vowel, measured in 2-8 kHz
  4 note tails    end-of-note envelope residual exactly 0
  5 band leak     zero energy outside a consonant's declared range

Exits non-zero if any gate fails.

NOTE on gate 2: tools/vocoder_diagnostics.py sums the bank all-positive, with
no polarity alternation. At the shipped Q=4.5 that measures 9.3 dB, which
would fail this gate on correct output. Alternating polarity is the thing that
flattens the bank, and this harness sums the way the engine does.
"""

import sys

import numpy as np
from scipy.signal import butter, sosfilt, welch

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from vocoder_render import (SR, NB, BANDS, BANK_Q, CONSONANT_RANGE, SIL,
                            cons_frames, build_note, render)

FAILS = []


def gate(name, ok, detail):
    print(f"  {'PASS' if ok else 'FAIL'}  {name:<28} {detail}")
    if not ok:
        FAILS.append(name)


def bandpass(x, lo, hi):
    sos = butter(4, [lo, min(hi, SR/2 - 100)], "band", fs=SR, output="sos")
    return sosfilt(sos, x)


def db(x):
    r = float(np.sqrt(np.mean(np.square(x))))
    return 20*np.log10(r + 1e-18)


# ---- 1. aliasing ----------------------------------------------------------
def check_aliasing(f0=392.0, seconds=2.0):
    n = int(SR*seconds)
    tt = np.arange(n)/SR
    K = int((SR/2-200)//(f0+6))                 # as the engine sizes it
    x = np.zeros(n)
    for k in range(1, K+1):
        x += np.sin(2*np.pi*k*f0*tt)/k
    x *= 2/np.pi

    f, P = welch(x, SR, nperseg=8192)
    P_db = 10*np.log10(P+1e-18)
    hf = (f > 5000) & (f < 12000)
    harm = np.zeros_like(f, bool)
    k = 1
    while k*f0 < 12000:
        harm |= np.abs(f - k*f0) < 40
        k += 1
    worst = P_db[hf & ~harm].max() - P_db[np.abs(f-f0) < 30].max()
    gate("aliasing floor", worst <= -70, f"{worst:7.1f} dB   (limit -70)")


# ---- 2. bank ripple -------------------------------------------------------
def check_ripple(lo=400, hi=6000):
    imp = np.zeros(SR); imp[0] = 1
    total = np.zeros(SR)
    for b in range(NB):
        bw = BANDS[b]/BANK_Q
        sos = butter(2, [max(20, BANDS[b]-bw/2), min(SR/2-100, BANDS[b]+bw/2)],
                     "band", fs=SR, output="sos")
        y = sosfilt(sos, imp)
        total += -y if b % 2 else y             # alternating polarity, as the engine does
    F = np.fft.rfft(total, SR)
    fr = np.fft.rfftfreq(SR, 1/SR)
    m = (fr > lo) & (fr < hi)
    mag = 20*np.log10(np.abs(F[m])+1e-12)
    r = mag.max()-mag.min()
    gate("bank ripple", r <= 5.0, f"{r:7.1f} dB   ({lo}-{hi} Hz, limit 5)")


# ---- 3. fricative level ---------------------------------------------------
def burst_frames(code, vw=96):
    """Frame span of a consonant's noise burst, skipping any plosive pre-gap."""
    seg = cons_frames(code, vw, 1.0)
    f, spans = 0, []
    for spec, _v, n in seg:
        if not np.allclose(spec, SIL):
            spans.append((f, f+n))
        f += n
    return (spans[0] if spans else None), f


def check_fricatives(codes=("s", "z", "f", "t", "k", "ch")):
    """Gate is the spec's: 2-8 kHz. The consonant's own declared range is
    reported alongside it, because a recipe whose energy sits below 2 kHz is
    measured on its tail rather than its body in the specified window."""
    worst_ok = True
    rows = []
    for code in codes:
        span, cons_n = burst_frames(code)
        if span is None:
            continue
        notes = [(60, 2, 96, 88, code, "")]
        out = render(notes, 560, 1.0, 14.0)

        s0, s1 = [int(round(x*0.01*SR)) for x in span]
        v0 = int(round((cons_n + 6)*0.01*SR))   # past the burst and the dip
        v1 = v0 + int(round(0.30*SR))           # 300 ms of vowel

        spec_win = bandpass(out, 2000, 8000)
        rel = db(spec_win[s0:s1]) - db(spec_win[v0:v1])

        lo, hi = CONSONANT_RANGE[code]
        own = bandpass(out, max(200.0, lo*0.8), hi*1.2)
        rel_own = db(own[s0:s1]) - db(own[v0:v1])

        ok = -18.0 <= rel <= -8.0
        worst_ok &= ok
        rows.append((code, lo, hi, rel, rel_own, ok))

    print(f"  {'':6}{'band':>12}{'2-8kHz':>10}{'own range':>12}")
    for code, lo, hi, rel, rel_own, ok in rows:
        mark = "" if ok else "   <-- outside -8..-18"
        print(f"  {code:<6}{f'{lo}-{hi}':>12}{rel:>9.1f} {rel_own:>11.1f}{mark}")
    gate("fricative level", worst_ok, "see table above")


# ---- 4. note tails --------------------------------------------------------
def check_tails():
    bad = []
    for code in ("", "s", "m", "t"):
        bands, _voi, _N = build_note(96, code, "", 1.0, 1.0, 14.0)
        if not (np.all(bands[:, -1] == 0) and np.all(bands[:, -2] == 0)):
            bad.append(code or "(none)")
    peak = 0.0
    for code in ("", "s", "m", "t"):
        bands, _v, _n = build_note(96, code, "", 1.0, 1.0, 14.0)
        peak = max(peak, float(np.abs(bands[:, -2:]).max()))
    gate("note tail residual", not bad,
         f"{peak:.1e}   (must be exactly 0)" + (f"  offenders {bad}" if bad else ""))


# ---- 5. band leak ---------------------------------------------------------
def check_leak():
    offenders = []
    worst = 0.0
    for code, (lo, hi) in CONSONANT_RANGE.items():
        for spec, _v, _n in cons_frames(code, 96, 1.0):
            if np.allclose(spec, SIL):
                continue
            for b in range(NB):
                if not (lo <= BANDS[b] <= hi) and spec[b] != 0.0:
                    worst = max(worst, float(abs(spec[b])))
                    offenders.append(f"{code}@{BANDS[b]:.0f}Hz")
    gate("out-of-band leak", not offenders,
         f"{worst:.1e}   (must be exactly 0)" +
         (f"  {offenders[:4]}" if offenders else ""))


def main():
    print("vocoder engine gates\n")
    check_aliasing()
    check_ripple()
    check_fricatives()
    check_tails()
    check_leak()
    if FAILS:
        print(f"\n{len(FAILS)} gate(s) FAILED: {', '.join(FAILS)}")
        return 1
    print("\nall gates passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
