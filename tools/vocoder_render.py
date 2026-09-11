#!/usr/bin/env python3
"""Render a song JSON through the vocoder engine (mode 2, experimental).

    .venv-vocoder/bin/python tools/vocoder_render.py songs/amazing_grace.json \
        -o /tmp/full.wav --diction 1 --smear 14

    # the diction-0 control, for the listening pair
    ... --diction 0 -o /tmp/vowels_only.wav

Per note a precomputed envelope drives the sound: 14 log-spaced bands from
220 Hz to 5.6 kHz, a gain trajectory at 10 ms frames, and a voicing trajectory
crossfading the excitation between a bandlimited sawtooth and soft noise.

THIS IS A TRANSCRIPTION OF tools/vocoder_reference.py AND MUST STAY ONE.
The acceptance test is a byte-for-byte match against that script's output, so
the order of floating-point operations here is load-bearing. Do not tidy the
arithmetic, do not vectorise the loops, do not reorder the band sum. If you
need to change the engine, change it in both and re-baseline the fixture.

Needs numpy and scipy:  .venv-vocoder/bin/pip install -r tools/requirements-vocoder.txt
Reads local files only.
"""

import argparse
import hashlib
import json
import pathlib
import sys

import numpy as np
from scipy.signal import butter, sosfilt
from scipy.io import wavfile

SR = 44100
NB = 14
BANDS = [220 * (5600/220) ** (b/(NB-1)) for b in range(NB)]
FR = 0.01
VOWELS = [
    dict(f=[300,870,2240],  g=[1,.35,.12]),
    dict(f=[570,840,2410],  g=[1,.45,.15]),
    dict(f=[730,1090,2440], g=[1,.6,.2]),
    dict(f=[530,1840,2480], g=[1,.5,.22]),
    dict(f=[270,2290,3010], g=[1,.3,.28]),
]

# --- reference constants ---------------------------------------------------
# These come from vocoder_reference.py and deliberately DIVERGE from
# src/house_sound.h, which governs mode 1. Keeping them means mode 2 renders
# exactly as the reference; it also means mode 2 is a slightly different voice
# from mode 1. Recorded as a known divergence in NOTES.md, pending a verdict.
#
#   here (mode 2)                     src/house_sound.h (mode 1)
#   vibrato 4.8 Hz, fixed +/-5 Hz     5.0 Hz, proportional (50.4 cents)
#   level   0.25 + 0.5*vel            GLOTTIS_AMP_BASE 0.22
#   gap     40 ms                     songs' own gapMs, 60
REF_GAP_MS      = 40
REF_LEVEL_BASE  = 0.25
REF_LEVEL_SCALE = 0.5
REF_VIB_HZ      = 4.8
REF_VIB_DEPTH   = 5.0     # Hz, absolute
REF_NOISE_SEED  = 11
BANK_Q          = 4.5


def mtof(n): return 440*2**((n-69)/12)


def vowel_spectrum(cc):
    pos = max(0, min(4, (cc/127)*4)); i = int(pos); j = min(i+1,4); t = pos-i
    F = [VOWELS[i]["f"][k]*(VOWELS[j]["f"][k]/VOWELS[i]["f"][k])**t for k in range(3)]
    G = [VOWELS[i]["g"][k]+(VOWELS[j]["g"][k]-VOWELS[i]["g"][k])*t for k in range(3)]
    s = np.array([sum(G[k]*np.exp(-0.5*(np.log(BANDS[b]/F[k])/0.20)**2) for k in range(3)) for b in range(NB)])
    return s/s.max()


def tilt_hf(s):
    """Rule 1's high-frequency tilt on consonant gains."""
    return s*np.array([min(1.0,(4200/BANDS[b])**0.6) for b in range(NB)])


def band_only(lo,hi,g):
    """Rule 1: out-of-band gain is exactly 0. A 0.04 leak caused harshness."""
    return np.array([g if lo <= BANDS[b] <= hi else 0.0 for b in range(NB)])


SIL = np.full(NB, 0.004)
UNVOICED_ONSETS = set("s z f h t k ch".split())

# Declared band range per consonant, for the leak check in vocoder_check.py.
CONSONANT_RANGE = {
    "s": (3800,5600), "z": (3000,5600), "f": (1800,5000), "t": (2600,5200),
    "k": (1200,2400), "ch": (1800,4000), "b": (200,600),  "d": (1400,3000),
    "g": (900,2000),  "m": (0,420),     "n": (0,420),
}


# --- recipe sets -----------------------------------------------------------
# "reference" is frozen: it reproduces vocoder_reference.py exactly, and the
# byte-match acceptance test runs against it. Every tuning change lands as a
# NEW set, so the reference stays a fixed point to measure against and each
# change stays individually A/B-able.
#
# v2 changes, each from a listening verdict plus a coverage measurement:
#
#   m, n  band 0-420 -> PITCH-RELATIVE 0.8*f0 .. 5*f0, amp 0.8 -> 0.45.
#
#         At 0-420 the nasal passed exactly one harmonic — the fundamental —
#         and measured 99.9% of its energy there. It was a sine, not an m. It
#         was also SILENT above C5, where no harmonic lands in 0-420 at all.
#
#         A fixed wider band (0-1100) fixes it only where we happened to
#         listen: 4/3/3/2 harmonics at A3-G4, but 1/1/1 at C5-G5. This is a
#         ratio problem, not a frequency problem — a nasal murmur is "the low
#         harmonics of whatever note is sounding" — so the band has to track
#         f0. 0.8..5*f0 holds 3-5 harmonics across A3-G5 with a steady 7-8
#         bands lit, so the loudness does not drift with pitch either.
#
# DELIBERATELY NOT CHANGED: b, d and g keep their absolute bands. Their
# spectral region is a place-of-articulation cue — the velar pinch for g, the
# alveolar region for d — tied to the vocal tract, not to f0. Making those
# track pitch would move them off the cue that identifies them. They are also
# 20 ms transients rather than 90 ms sustains, so a thin harmonic count reads
# as a blip rather than as a tone. b is the weakest of the three (sine-like at
# 5 of 7 pitches) and is flagged in NOTES rather than silently retuned.
RECIPE_SETS = ("reference", "v2")


def cons_frames(code, vw, dic, recipes="reference", f0=None):
    seg=[]
    def push(spec,voi,ms,amp): seg.append((spec*amp, voi, max(1,round(ms/10))))
    vsp = vowel_spectrum(vw)
    if code=="s": push(tilt_hf(band_only(3800,5600,1)),0,60,0.28*dic)
    elif code=="z": push(tilt_hf(band_only(3000,5600,1)),0.65,55,0.18*dic)
    elif code=="f": push(tilt_hf(band_only(1800,5000,0.7)),0,55,0.16*dic)
    elif code=="t": push(SIL,1,30,1); push(tilt_hf(band_only(2600,5200,1)),0,20,0.30*dic)
    elif code=="k": push(SIL,1,30,1); push(band_only(1200,2400,1),0,20,0.30*dic)
    elif code=="ch": push(SIL,1,22,1); push(tilt_hf(band_only(1800,4000,1)),0,50,0.26*dic)
    elif code=="b": push(SIL,1,20,1); push(band_only(200,600,1),1,20,0.5*dic)
    elif code=="d": push(SIL,1,20,1); push(band_only(1400,3000,1),1,18,0.28*dic)
    elif code=="g": push(SIL,1,22,1); push(band_only(900,2000,1),1,20,0.30*dic)
    elif code=="h": push(vsp,0,55,0.30*dic)
    elif code in ("m","n"):
        if recipes=="v2" and f0:
            push(band_only(0.8*f0, 5.0*f0, 1), 1, 90, 0.45)
        else:
            push(band_only(0,420,1),1,90,0.8)
    elif code=="w": push(vowel_spectrum(0),1,90,0.9)
    elif code in ("l","r"): push(vowel_spectrum(38),1,90,0.9)
    return seg


def build_note(vw,on,co,dur_s,dic,smear_ms,release_above=2500,recipes="reference",
               f0=None):
    N = max(6, round(dur_s/FR))
    bands = np.zeros((NB,N)); voi = np.zeros(N); amp = np.zeros(N)
    f = 0
    def write(seg):
        nonlocal f
        for spec,v,n in seg:
            for _ in range(n):
                if f>=N: return
                bands[:,f]=spec; voi[f]=v; amp[f]=1; f+=1
    if on: write(cons_frames(on,vw,dic,recipes,f0))
    vsp = vowel_spectrum(vw)
    # Rule 3: one 10 ms frame at 15% vowel between an unvoiced onset and the vowel.
    if on in UNVOICED_ONSETS and f<N:
        bands[:,f]=vsp*0.15; voi[f]=1; amp[f]=1; f+=1
    glide_from = f if on in ("w","l","r","m","n") else -1
    co_seg = cons_frames(co,vw,dic,recipes,f0) if co else []
    co_n = sum(n for _,_,n in co_seg)
    sus_end = N-co_n-3; sus_start=f
    while f<sus_end and f<N:
        t=(f-sus_start)/max(1,sus_end-sus_start)
        blend=min(1,(f-sus_start)/8) if glide_from>=0 else 1
        prev = bands[:,max(0,sus_start-1)] if glide_from>=0 else vsp
        bands[:,f]=prev*(1-blend)+vsp*blend
        voi[f]=1; amp[f]=1-0.1*t; f+=1
    if co: write(co_seg)
    while f<N:
        bands[:,f]=0; voi[f]=voi[max(0,f-1)]; amp[f]=0; f+=1
    # Rule 2: asymmetric smear. Attacks and bands <=2.5 kHz use the user smear
    # time; bands above it release at a fixed 4 ms, so fricatives stop rather
    # than fade. Voicing rises at 5 ms, falls at the smear rate.
    a_att=np.exp(-10/max(2,smear_ms)); a_rel=np.exp(-10/4)
    st=np.zeros(NB)
    for i in range(N):
        tgt=bands[:,i]*amp[i]
        for b in range(NB):
            a = a_att if (tgt[b]>=st[b] or BANDS[b]<=release_above) else a_rel
            st[b]=a*st[b]+(1-a)*tgt[b]
        bands[:,i]=st.copy()
    sv=0; voi_s=np.zeros(N); a_vup=np.exp(-10/5)
    for i in range(N):
        a = a_vup if voi[i]>=sv else a_att
        sv=a*sv+(1-a)*voi[i]; voi_s[i]=sv
    # Rule 4: hard-zero tails. A 24% residual held between notes and was
    # audible as noise on the next syllable's start.
    bands[:,-3]*=0.4; bands[:,-2]=0; bands[:,-1]=0
    return bands, voi_s, N


def render(notes, quarter_ms, dic, smear_ms, gap_ms=REF_GAP_MS, release_above=2500,
           recipes="reference"):
    """notes: [(midi, beats, vowelCC, velocity, onset, coda)], rests as midi=None."""
    total_ms = sum(round(b*quarter_ms) for _,b,_,_,_,_ in notes) + 600
    NF = round(total_ms/10)
    g_bands = np.zeros((NB,NF)); g_voi = np.ones(NF); g_f0 = np.full(NF, 220.0)
    t = 0
    for note,beats,vw,vel,on,co in notes:
        if note is None:                       # a rest just advances the clock
            t += round(beats*quarter_ms); continue
        dur_s = (round(beats*quarter_ms)-gap_ms)/1000
        bands, voi, N = build_note(vw,on,co,dur_s,dic,smear_ms,release_above,recipes,
                                   mtof(note))
        lvl = REF_LEVEL_BASE+REF_LEVEL_SCALE*(vel/127)
        off = round(t/10); n = min(N, NF-off)
        g_bands[:,off:off+n] = bands[:,:n]*lvl
        g_voi[off:off+n] = voi[:n]
        g_f0[off:off+round(round(beats*quarter_ms)/10)] = mtof(note)
        t += round(beats*quarter_ms)
    n_samp = round(NF*0.01*SR)
    tt = np.arange(n_samp)/SR
    fi = np.minimum(np.arange(n_samp)/(0.01*SR), NF-1)
    i0=fi.astype(int); frac=fi-i0; i1=np.minimum(i0+1,NF-1)
    interp = lambda row: row[i0]*(1-frac)+row[i1]*frac
    f0_t = interp(g_f0) + REF_VIB_DEPTH*np.sin(2*np.pi*REF_VIB_HZ*tt)
    phase = np.cumsum(2*np.pi*f0_t/SR)
    # Rule 5: bandlimited carrier. A naive saw measured -36 dB aliasing.
    K = int((SR/2-200)//(g_f0.max()+6))
    saw = np.zeros(n_samp)
    for k in range(1, K+1):
        saw += np.sin(k*phase)/k
    saw *= 2/np.pi
    noise = np.random.default_rng(REF_NOISE_SEED).standard_normal(n_samp)*0.35
    v = interp(g_voi)
    exc = saw*v + noise*(1-v)*0.4
    out = np.zeros(n_samp)
    # Rule 5: alternating polarity summation. Flattens bank ripple from
    # 9.3 dB to 3.1 dB measured over 400 Hz-6 kHz.
    for b in range(NB):
        bw = BANDS[b]/BANK_Q
        sos = butter(2,[max(20,BANDS[b]-bw/2),min(SR/2-100,BANDS[b]+bw/2)],"band",fs=SR,output="sos")
        y = sosfilt(sos, exc)*interp(g_bands[b])
        out += -y if b % 2 else y
    out = out/np.max(np.abs(out))*0.89
    fade = round(0.01*SR)
    out[:fade]*=np.linspace(0,1,fade); out[-fade:]*=np.linspace(1,0,fade)
    return out


def notes_from_song(song, voice="sop", first=None):
    rows = song["notes"][:first] if first else song["notes"]
    return [(n.get(voice), n["beats"], n["vowelCC"], n.get("velocity") or 0,
             n.get("onset","") or "", n.get("coda","") or "") for n in rows]


def verify(song_path):
    """Byte-for-byte acceptance against the frozen reference render.

    Not a tolerance check: the same float64 operations in the same order give
    the same bits, so an exact match is the honest bar. It only holds inside
    the pinned environment in tools/requirements-vocoder.txt — scipy's sosfilt
    can differ in the last bits between releases, so a mismatch means "the
    engine changed OR the environment did", and pip freeze settles which.
    """
    fixtures = pathlib.Path(__file__).with_name("vocoder_fixtures") / "reference.sha256"
    if not fixtures.exists():
        print(f"no fixture at {fixtures}", file=sys.stderr)
        return 2
    want = {}
    for line in fixtures.read_text().split("\n"):
        if line.strip():
            h, name = line.split()
            want[name] = h

    song = json.loads(song_path.read_text())
    notes = notes_from_song(song, "sop", 14)
    cases = [("vocoder_reference_full.wav", 1.0), ("vocoder_reference_vowels_only.wav", 0.0)]

    import tempfile
    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        for name, dic in cases:
            out = render(notes, song["quarterMs"], dic, 14.0, REF_GAP_MS)
            path = pathlib.Path(tmp) / name
            wavfile.write(str(path), SR, (out*32767).astype(np.int16))
            got = hashlib.sha256(path.read_bytes()).hexdigest()
            ok = got == want.get(name)
            print(f"  {'OK  ' if ok else 'FAIL'} {name}")
            print(f"         rendered {got}")
            if not ok:
                print(f"         expected {want.get(name, '(not in fixture)')}")
                failures += 1
    if failures:
        print(f"\nBYTE-MATCH FAILED ({failures}/{len(cases)})")
        return 1
    print(f"\nBYTE-MATCH OK — {len(cases)}/{len(cases)} identical to the reference render")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("song", type=pathlib.Path)
    ap.add_argument("-o","--out", type=pathlib.Path, default=None)
    ap.add_argument("--diction", type=float, default=1.0,
                    help="0-2; 0 is the vowels-only control (default 1)")
    ap.add_argument("--smear", type=float, default=14.0, help="ms (default 14)")
    ap.add_argument("--gap-ms", type=float, default=REF_GAP_MS,
                    help=f"note gap (default {REF_GAP_MS}, the reference value; "
                         "the songs themselves say 60)")
    ap.add_argument("--release-above", type=float, default=2500.0,
                    help="bands above this get rule 2's fast 4 ms release; below "
                         "it they release at the smear time. Default 2500 is the "
                         "reference. 0 gives every band the fast release.")
    ap.add_argument("--recipes", default="reference", choices=list(RECIPE_SETS),
                    help="consonant recipe set. 'reference' reproduces the frozen "
                         "spec and is what --verify checks; later sets carry tuning "
                         "changes that came from listening verdicts.")
    ap.add_argument("--voice", default="sop", choices=["sop","alto","bass"])
    ap.add_argument("--first", type=int, default=None,
                    help="render only the first N notes")
    ap.add_argument("--sha", action="store_true", help="print the output's SHA-256")
    ap.add_argument("--verify", action="store_true",
                    help="acceptance test: render the reference's 14-note phrase "
                         "at both diction settings and check both SHA-256s against "
                         "tools/vocoder_fixtures/reference.sha256")
    args = ap.parse_args(argv)

    if args.verify:
        return verify(args.song)

    if args.out is None:
        ap.error("-o/--out is required unless --verify is given")
    song = json.loads(args.song.read_text())
    notes = notes_from_song(song, args.voice, args.first)
    out = render(notes, song["quarterMs"], args.diction, args.smear, args.gap_ms,
                 args.release_above, args.recipes)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    wavfile.write(str(args.out), SR, (out*32767).astype(np.int16))

    line = (f"{args.out}  {len(out)/SR:.2f}s  {len(notes)} notes  "
            f"diction {args.diction}  smear {args.smear}ms  gap {args.gap_ms}ms")
    if args.sha:
        line += "\n  sha256 " + hashlib.sha256(args.out.read_bytes()).hexdigest()
    print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
