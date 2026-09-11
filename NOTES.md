# Tuning notes

A log of musical decisions — what each number does, why it is what it is, and
what made the robot sound sung rather than robotic.

Seeded from the original sketch's comments and from the values themselves.
Sections marked **_(to fill in)_** are waiting on your ear; nothing in the
code recorded a reason for them, so nothing is asserted here.

---

## Vibrato — 5.0 Hz, depth 0.12, LFO amplitude 0.35
*(was 5.2 Hz through session 1; per-voice rates since session 2)*

```c
glottis.frequencyModulation(0.12f);   // vibrato depth
vibratoLFO.frequency(def_.vibratoHz);   // 5.0 soprano, 4.6 alto, 4.3 bass
vibratoLFO.amplitude(0.35f);
```

The LFO feeds the FM input of the sawtooth, so depth is the product of
`frequencyModulation` (octaves at full scale) and the LFO's own amplitude.

Human singing vibrato sits around 5–7 Hz. 5.0 Hz is at the slow end of that
band — slower reads as controlled and adult, faster as nervous or operatic.

Now **5.0 Hz** on the soprano, with alto at 4.6 and bass at 4.3 — see the
session 2 findings below on vibrato rate as an intensity control.

**_(to fill in)_** Why 5.0 and not 5.2, where it started? Note what it sounded
like on either side.

**_(to fill in)_** Whether vibrato should ramp in after note onset rather than
being present from the first sample. Real singers do not start a note with
full vibrato, and this is the single most likely reason a sustained note still
reads as synthetic.

---

## The vowel table

Current preset: `src/voice/presets/warm.h`.

| Vowel | F1 | F2 | F3 | Gains |
|---|---|---|---|---|
| oo | 300 | 870 | 2240 | 1.00 / 0.35 / 0.12 |
| oh | 570 | 840 | 2410 | 1.00 / 0.45 / 0.15 |
| ah | 730 | 1090 | 2440 | 1.00 / 0.60 / 0.20 |
| eh | 530 | 1840 | 2480 | 1.00 / 0.50 / 0.22 |
| ee | 270 | 2290 | 3010 | 1.00 / 0.30 / 0.28 |

What the axes are doing:

- **F1 tracks how open the mouth is.** It climbs 300 → 730 as the jaw drops
  toward "ah", then falls back to 270 for "ee". This is why the table is
  ordered the way it is: closed → open → closed. The jaw motion model leans
  on that ordering.
- **F2 tracks tongue position, front to back.** It is nearly flat across
  oo/oh/ah (870 → 840 → 1090) and then leaps for the front vowels
  (1840 → 2290). F2 is what actually distinguishes "ah" from "ee"; F1 alone
  is ambiguous between "oo" and "ee".
- **F3 barely moves** (2240 → 3010) and mostly carries timbre rather than
  vowel identity. It is the "who is singing" formant — the cheapest knob for
  making a second preset sound like a different character without breaking
  intelligibility.
- **Gains fall off with formant number**, and the upper two rise as the vowel
  fronts. Everything gets scaled by `0.9` in `applyVowel()` before reaching
  the mixer.

CC1 morphs left-to-right through the table. Frequencies are interpolated
**geometrically**, gains **linearly**:

```c
float freq = VOWELS[i].f[k] * powf(VOWELS[j].f[k] / VOWELS[i].f[k], t);
```

The original comment on that line: _"Geometric interpolation of frequencies
sounds smoother than linear."_ Pitch perception is logarithmic, so a linear
sweep between 870 Hz and 1840 Hz spends too long at the top end and the morph
lurches. Geometric sweeps at a constant musical rate.

**_(to fill in)_** Per-vowel notes as you retune — which ones sing and which
ones sound like a filter sweep.

---

## Formant resonance — 4.0 / 5.0 / 5.0

```c
formant1.resonance(4.0f);
formant2.resonance(5.0f);
formant3.resonance(5.0f);
```

F1 is left broader than F2 and F3. Higher Q means a more pinched, more clearly
"vowel" sound and more ringing on transients; lower Q is breathier and lets
more of the raw sawtooth through.

**_(to fill in)_** Where this stops sounding like a voice and starts sounding
like a resonant filter — and whether Q should scale with pitch, since a fixed
Q gets relatively narrower as the fundamental rises.

---

## Envelope — 45 / 120 / 0.85 / 260 ms

```c
env.attack(45);  env.decay(120);  env.sustain(0.85f);  env.release(260);
```

A 45 ms attack is slow for a synth and about right for a voice — fast enough
to feel intentional, slow enough that notes bloom instead of clicking. The
high sustain (0.85) with a short decay means notes hold rather than plucking.
260 ms release leaves a tail that makes legato phrases join up.

**_(to fill in)_** Attack is the number most likely to be doing the "sung vs
robotic" work. Log what 20 ms and 80 ms sounded like.

---

## Source mix and breath

```c
sourceMix.gain(0, 0.85f);        // glottis
breathLevel = 0.0f;              // default breath, CC2 overrides
// CC2: breathLevel = 0.0f + (val / 127.0f) * 0.27f;
```

> **Superseded in session 2.** Breath used to sit at 6% by default, on the
> theory that noise keeps a sustained note from sounding like a held organ
> chord. Removing it turned out to sound better — see the session 2 findings.
> CC2 now sweeps 0%–27% from silence.

**_(to fill in)_** Whether breath should duck during the sustain and rise on
attack/release, which is what real breath does. Untested since it was switched
off; it may be worth more as a shaped gesture than as a bed.

---

## Velocity mapping

```c
glottis.amplitude(0.22f + 0.5f * noteVelocity);   // loudness
jawSetTarget(0.35f + 0.65f * noteVelocity);       // mouth
```
*(amplitude base was 0.25 through session 1)*

Both are offset-plus-scale rather than proportional: velocity 1 still makes
sound (0.25) and still opens the mouth (0.35). A quiet note that barely moves
the jaw looks broken.

The jaw opens proportionally *further* than the voice gets louder (0.65 span
vs 0.5) — the mouth is more expressive than the amplitude.

---

## Jaw motion

```c
float rate = (target > jawActual) ? 0.28f : 0.11f;   // fast open, slow close
```
*(was 0.30 / 0.12 through session 1)*

Asymmetric easing at a 200 Hz control rate. Opening is 2.5× faster than
closing. This is the whole illusion: a syllable starts abruptly and the mouth
relaxes shut, which is how a jaw actually behaves under gravity. Symmetric
easing looks like a machine; a faster close looks like a chattering puppet.

Mouth shape also follows the vowel:

```c
float vowelOpenness = 1.0f - 0.35f * fabsf(vowelPos - 2.0f) / 2.0f;
```

"ah" (index 2) opens fully; the closed vowels at either end of the table close
the jaw by up to 35%. So the mouth narrows on "oo" and "ee" without any extra
MIDI data.

> ⚠️ **Flagged during the refactor, not changed.** That line hardcodes `2.0`
> as the index of the most open vowel and `2.0` as half the table length. It
> is exactly correct for a 5-entry table centered on "ah" — and silently wrong
> for any other shape. Generalizing it to `(NUM_VOWELS - 1) / 2` is
> numerically identical for the current preset, but it was left alone to keep
> the refactor behavior-preserving. Worth doing the moment a preset has a
> different length.

**_(to fill in)_** Servo trim for your linkage (`JAW_CLOSED_DEG` /
`JAW_OPEN_DEG` in `config.h`), and whether 200 Hz is more than the MG90S can
actually follow.

---

## Sung vs robotic

**_(to fill in)_** The running list. What has moved the needle so far, in
rough order of suspicion:

- [ ] Vibrato onset delay (see above) — almost certainly the biggest one
- [ ] Attack time
- [ ] Breath envelope following the amplitude envelope
- [ ] Slight pitch drift / scoop into note onsets rather than exact pitch
- [ ] Formant frequencies shifting slightly with pitch, as a real tract does

---

## Refactor caveats

The module split was verified behavior-preserving by diffing the audio graph,
the vowel table and the interpolation math (all byte-identical), and by
comparing every numeric literal in the tree. Build sizes matched closely
(FLASH code 46040 → 46004 bytes, const data and audio RAM unchanged).

**Size parity is a proxy, not proof.** If the robot sounds different after the
refactor, `git bisect` between `cbe372d` (original sketch) and `0297b7c`
(module split) will find it, and this file should record what changed.

---

# Session 2 findings

Landed after a stretch of iterating in the browser simulator. These are the
decisions that changed the design, in roughly the order they mattered.

## Breath is off by default now

Removing the constant breath-noise bed made the tone purer and better. It had
been at 0.06 since the beginning on the theory that a little air stops a
sustained note sounding like a held organ chord. In practice it just muddied
everything. CC2 still sweeps it back in from silence (0.00–0.27) for anyone
who wants it, but zero is the resting state.

## Articulation through formant motion sounds sung; added noise sounds mechanical

This is the central finding of the session. Moving the formants to shape a
syllable reads as singing. Adding noise to shape a syllable reads as a machine
doing an impression of singing. Choir directors coach "sing on the vowel" for
the same reason — the consonant is a transition between vowels, not a separate
sound stapled on the front.

So articulation is glides, and only glides. CC3 picks one per note:

- `w` — vowel starts at 0.0 ("oo") and travels to the note's vowel
- `l` — starts at 1.2 (just past "oh") and travels the same way
- none — the vowel steps straight to target

The travel is not a ramp. The vowel position *jumps* to the glide's start, and
the ordinary 35 ms formant smoothing does the moving; after `GLIDE_MS` (110 ms)
the target is released to the note's real vowel and the same smoothing carries
it the rest of the way. Two steps and a one-pole filter, no ramp generator.

## Why the consonant engine was rejected

We built one — fricative noise, plosive gaps and bursts, nasal pre-hum — and
threw it away.

The killer was the plosive burst. A narrow-band noise burst rings at the
filter's centre frequency, because an impulse into a high-Q bandpass *is* a
struck bell. That was the "beep" we kept hearing and kept failing to tune out.
It is not a bug to be fixed; it is what a resonant filter does to an impulse.

**Preferred consonant level: zero. Glides only.** Do not add consonant noise to
the main firmware. If it gets revisited, it goes on an `experiment/consonants`
branch and stays there until it earns its way out.

## Vowel choreography rules that work

- Map vowels to the lyric's vowel skeleton. The vowels carry the word; write
  those and ignore the consonants entirely.
- On melodies without lyrics, map openness to pitch height — high notes open,
  low notes closed. Ode to Joy uses a literal pitch→vowel lookup for this.
- Re-articulate repeated notes with a short gap, about 60 ms. Without it two
  notes at the same pitch are one long note. `gapMs` in the song format and the
  exporter both use 60.

## Vibrato rate carries emotional intensity

Automating vibrato rate with musical intensity was the key expressiveness
find — it does more than any amount of level or vowel automation.

- calm ≈ 4.3–4.8 Hz
- urgent ≈ 5.5+

CC4 sweeps 2–9 Hz on the soprano; the other voices scale proportionally so the
choir keeps its internal character rather than converging on one rate. Vibrato
depth wants to sit around 35–45 on the simulator's 0–100 scale.

**_(to fill in)_** Where rate automation starts sounding seasick rather than
intense.

## The three voices

| Voice | Vibrato | Detune | Formant scale | Mix |
|---|---|---|---|---|
| Soprano | 5.0 Hz | 0 ¢ | 1.00 | 0.42 |
| Alto | 4.6 Hz | +4 ¢ | 0.93 | 0.30 |
| Bass | 4.3 Hz | −3 ¢ | 0.82 | 0.34 |

Formant scale is what makes the bass a bass. Transposing a voice down without
scaling its formants gives you a chipmunk played slowly; scaling the formant
centres down to 0.82 makes it read as a physically bigger person. Detune is
small on purpose — a few cents apart is a choir, twenty cents apart is out of
tune.

**_(to fill in)_** Whether the mix levels hold up on the actual speaker. They
sum to 1.06 at full tilt, which has headroom only because three voices rarely
peak together.

## Firmware / simulator reconciliation

The two implementations had drifted apart on five values nobody had ruled on.
Resolved by asking which side had actually *decided* the thing:

| | Firmware was | Simulator was | Winner |
|---|---|---|---|
| Jaw open / close | 0.30 / 0.12 | 0.28 / 0.11 | simulator |
| Velocity → amplitude | 0.25 + 0.5v | 0.22 + 0.5v | simulator |
| Portamento | instant | 25 ms | simulator |
| Envelope | ADSR 45/120/0.85/260 | attack + release only | **firmware** |
| Vibrato depth | proportional (octaves) | fixed ±4.5 Hz | **firmware** |

The last two were the simulator being approximate rather than opinionated. Web
Audio makes a real ADSR awkward, so it had grown a one-pole attack and release
with no decay or sustain stage at all. And a fixed Hz vibrato deviation means a
low bass note wobbles far wider *in cents* than a high soprano note — musically
wrong, and most obvious exactly where the choir spreads out. The simulator now
runs a linear ADSR and drives `osc.detune` in cents, which is proportional.

**_(to fill in)_** Whether the 0.25 → 0.22 amplitude drop is audible at all, or
whether it was just drift nobody noticed.

## Still unverified

Nothing in session 2 has run on hardware. The build is clean and the host-side
parity checks pass, but audio, servo motion and the audio budget are all
unconfirmed. `AUDIO_MEMORY_BLOCKS` at 60 is a guess — read
`AudioMemoryUsageMax()` off a real Teensy via `ENABLE_PERF_REPORT` and trim it.

---

# Session 3 findings

## The eyebrows went missing

The eyebrows disappeared when the simulator was rebuilt "to spec," because the
spec only covered audio. The expressive layer (brows, eye wobble, jaw easing
rates) carries the robot's character and is part of the spec, not decoration.
Any rebuild or port must preserve it.

Concretely, what the face does and why it reads as alive:

- **Nothing snaps.** Jaw, brows and eyes are all eased toward a target rather
  than set. The jaw's asymmetric rates (0.28 open, 0.11 close) were the
  original instance of this; the brows use the same pattern at 0.08/frame.
- **Motion is tied to sound, not to the clock.** The eyes only wobble while
  something is sounding, and the brows only lift while something is singing. A
  face that idles in motion reads as a screensaver.
- **The brows lift 2 units** — small. At this scale the difference between
  "expressive" and "cartoon" is a couple of pixels.

The measured eye wobble is `sin(t/380) × 2`, which is ±2 units at a period of
2π × 380 ms ≈ **2.39 s** — worth stating because the spec handed over said
~2.6 s, and the code is the source of truth.

## 2 px is not motion

The brows shipped at 2 units of travel, per the spec. They animated correctly —
the eased state moved, the path attribute updated every frame — and read as
completely static on the live page.

2 units in a 200x130 viewBox drawn at 210x137 px is **2.11 px**. Below noticing.

The second half of the problem was that `singing` is a binary flag held true
for a whole song, so even a visible amplitude would have given one lift at the
start and one drop 18 seconds later. Expression needs something that changes
per note.

Both fixed together: the brows now sit at 4 units and lift toward 8 with note
velocity, using the same drive signal the jaw already follows, so they move on
every note. 5.8-7.4 px in practice, and visibly different between a quiet note
and a loud one.

The general lesson, which is the same one the eyebrows taught the first time:
**an expressive parameter has to be checked against what it looks like, not
against whether the code runs.** The animation was correct in both cases.

**_(to fill in)_** Whether 4-8 units is right or now overshoots into cartoon.
The brow control point reaches y=10 at full tilt and the face frame starts at
y=8, so there are only 2 units of headroom left above it.

## A face that repeats reads as a machine

Three complaints, one cause: the eyes "just move back and forth", the brows
"kinda stay", and he never blinks.

- **The pupils tracked `sin(now/380)`.** Both eyes, in lockstep, horizontally
  only, forever. Perfectly smooth and perfectly periodic, which is exactly what
  nothing alive does. Real eyes *saccade*: hold still, flick somewhere new,
  hold again. Replaced with random gaze targets, a fast flick (eased 0.35, so
  roughly 60 ms — real saccades are 30–80 ms), and a slow drift underneath so a
  held gaze still breathes.
- **No blink at all.** Now every 1.8–6.2 s, 140 ms, shutting faster than it
  opens, with an 18% chance of a double. Measured over 30 s it fires 8–9 times,
  which is in the human range of roughly 15–20 a minute.
- **The brows "kinda stay" was measurable, not vague.** They were driven by
  note velocity, but real song velocities cluster: Amazing Grace runs 72–104,
  House of the Rising Sun 68–96. That is **1.0 px and 0.9 px** of per-note
  travel. The lift was visible; the modulation was not. Fixed with an
  independent slow wander per brow and an occasional single-brow raise, so the
  two are rarely level — about 9 px of travel and 2 px of asymmetry.

The general point, now demonstrated three times on this face: **an expressive
parameter has to be checked against what it looks like.** All three of these
were animating correctly the whole time.

One geometric constraint worth keeping: the brow curve's control point sits 6
units above its endpoints and the face frame starts at y=8, so total brow lift
is capped at 8.5 or the eyebrows leave the head. Verified at worst case over
40 s at full velocity — control point bottoms out at y=9.50.

**_(to fill in)_** Whether the saccade timing feels attentive or shifty. Faster
holds read as nervous; slower read as sleepy.

## ⚠️ The jaw eases 3.3x faster on hardware than in the simulator

Found while deriving the brow constant. The parity rule compares *numbers*,
and these particular numbers do not mean the same thing in both places.

Both implementations run the same one-pole step, `x += (target - x) * rate`.
But the simulator ticks on `requestAnimationFrame` at ~60 fps, and the firmware
ticks at 200 Hz. A per-tick rate is therefore 3.33x more aggressive on the
Teensy — same constant, different clock:

| | sim @ 60 fps | firmware @ 200 Hz |
|---|---|---|
| jaw open 0.28 | 50.7 ms | **15.2 ms** |
| jaw close 0.11 | 143.0 ms | **42.9 ms** |
| brow 0.08 | 199.9 ms | 60.0 ms |

The jaw rates were adopted from the simulator in session 2 on the grounds that
the simulator is where the motion was tuned by eye. But copying the *number*
rather than the *feel* means the hardware jaw snaps in 15 ms where the tuned
version takes 51 ms. That is very likely to read as a twitch rather than a
syllable.

The fix is to express these as time constants, the way `VOWEL_SMOOTH_MS` and
`PORTAMENTO_MS` already are, and derive the per-tick coefficient:

    alpha = 1 - exp(-CONTROL_INTERVAL_MS / TIME_CONSTANT_MS)

    jaw open   50.7 ms -> alpha 0.093851 per 5 ms tick
    jaw close 143.0 ms -> alpha 0.034356 per 5 ms tick

**Not applied.** It changes the jaw feel on hardware, and nothing has run on
hardware yet — so this is a decision for the first real listen, not a silent
correction. The brow module was built the right way from the start
(`BROW_SMOOTH_MS = 200`), so the two approaches sit side by side in `face/`
until this is settled.

Worth checking whether anything else in the repo copies a per-frame rate across
the clock boundary. The vowel and portamento smoothing are already time
constants, so they are fine.

## Minor-key repertoire

**_(to fill in)_** House of the Rising Sun is the first minor-key song, and new
territory for the vowel choreography. The open question: darker vowels may want
to sit lower and more closed than the major-key songs do — the same syllable
that wants "ah" in Amazing Grace may want something nearer "oh" here. Log what
the A minor and E major bars end up wanting.

**_(to fill in)_** Whether the E-major bars (the G#3 in the alto) want a
brighter vowel than the Am bars around them, to lean on the raised third.

## Transcription artifacts, and which ones to keep

The pipeline produces artifacts that are technically errors. Some of them
should survive into `songs/`, because the voice is not a piano.

- **Scoops.** A hummed note that slides into pitch gets transcribed as either a
  short wrong note followed by the right one, or as one note starting flat. The
  cleanup pass drops the short one by default (`--min-ms 80`). But the voice
  already has 25 ms of portamento, so a real scoop and a transcription scoop
  land in nearly the same place — and a scoop into a phrase is exactly what
  makes the robot sound sung rather than sequenced. Consider lowering
  `--min-ms` on expressive takes and keeping the "errors".
- **Split notes.** A wobble across a semitone boundary splits one note into
  two. `--merge-ms` sews them back up, but the threshold must stay **below the
  60 ms re-articulation gap** or genuinely repeated notes fuse into one. 40 ms
  is the default for that reason.
- **Octave jumps.** Autocorrelation's classic failure is picking twice the true
  period. There is a guard for it in the tracker and an octave-outlier collapse
  in the cleanup, but on a breathy low take it still happens. A bass line an
  octave up is obvious on a listen and invisible in a diff.

**_(to fill in)_** Which of these actually sounded good once sung. The question
is not whether the transcription is accurate; it is whether the robot sings it
better with the artifact than without.

**_(to fill in)_** Whether the naive transcriber's 80–800 Hz range is enough in
practice, or whether humming down at the bass part needs the lower bound moved.

---

# Vocoder mode (experimental, branch `mode/vocoder`)

Pronunciation lives in band envelopes, not in events. Consonants that stop beat
consonants that fade. The synthesis floor has to be clean before consonant
tuning means anything — we tuned consonants on top of aliasing for two rounds
without knowing it.

## The five rules, and what each one cost to learn

Each is a defect that was heard first and measured second. `vocoder_check.py`
is the regression test for all five; the numbers below are from this machine.

1. **Levels and tilt.** Consonants sit 10–15 dB under the vowel in 2–8 kHz,
   with a `min(1,(4200/f)^0.6)` high-frequency tilt. Out-of-band gain is
   **exactly** 0 — a 0.04 leak was audible as broadband harshness.
2. **Asymmetric smear.** Smear time on attacks and on bands ≤ 2.5 kHz, a fixed
   4 ms release above it. Symmetric decay was an audible downward sweep.
   Fricatives have to stop.
3. **Articulation dip.** One frame at 15% vowel between an unvoiced onset and
   the vowel. Plosive pre-gaps are near-silence at 0.004, voiced — never an
   unvoiced noise floor.
4. **Hard-zero tails.** A 24% residual held between notes and was audible as
   noise on the next syllable's *start*, which is why it took so long to find.
5. **Clean synthesis floor.** Bandlimited carrier: naive saw measures −36.4 dB
   aliasing, bandlimited −85.0 dB. Alternating-polarity band summation:
   all-positive measures 9.3 dB ripple at Q=4.5, alternating 3.1 dB.

## Measured findings from productionising it

- **The diagnostics measured a configuration that does not ship.**
  `vocoder_diagnostics.py` sums the bank all-positive, with no polarity
  alternation — so it reports the 9.3 dB case, and productionising it unchanged
  would have produced a check that fails on correct output. It also tests
  Q=4/5 and Q=3.8 while the spec ships Q=4.5, and measures 1–6 kHz against an
  acceptance range of 400 Hz–6 kHz. Left unedited; the spec is frozen.
- Q=3.8 uniform, the configuration its docstring proposes as an improvement,
  measures **29.3 dB** ripple — considerably worse than the 11.5 dB split it
  was meant to fix.
- **`f` is out of spec.** −20.2 dB in the 2–8 kHz window, −23.0 dB in its own
  band. It is the only recipe stacking a sub-unity band gain (0.7) with the
  lowest amplitude (0.16): 0.112 effective, about 40% of `s`.
- **`k` reads out of spec but isn't.** Its band is 1200–2400 Hz, mostly below
  the specified measurement window, so 2–8 kHz measures its tail. In its own
  range it is −15.8 dB, inside spec. One window does not fit every consonant.

## Known divergence from mode 1

Kept deliberately, so mode 2 renders exactly as the reference:

| | mode 2 (vocoder) | mode 1 (`house_sound.h`) |
|---|---|---|
| Vibrato | 4.8 Hz, fixed ±5 Hz | 5.0 Hz, proportional (50.4 ¢) |
| Level | `0.25 + 0.5·vel` | `GLOTTIS_AMP_BASE` 0.22 |
| Note gap | 40 ms | the songs' own `gapMs`, 60 |

The vibrato row is the fixed-vs-proportional question from session 2 arriving
again by a different route. Mode 2 is therefore a slightly different voice from
mode 1, which is a thing to rule on by ear, not by diff.

## The m is a sine wave

You said the m in "A-ma-zing" sounds weird. Measured, it is a pure tone:

    H1   262 Hz    0.0 dB   <- the fundamental
    H2   523 Hz  -31.0 dB
    H3   785 Hz  -49.4 dB

**99.9% of its energy from 100 Hz to 4 kHz is in the fundamental.** The
recipe is `band_only(0,420)`, and at C4 that range catches f0 and nothing
else — 1 of 6 harmonics. So the m is 90 ms of sine, and the vowel that
follows holds **0.0%** of its energy at the fundamental. A beep that opens
into a voice, which is exactly what it sounds like.

The same holds at every pitch in the phrase: at G4 the m still passes only
f0, and only because 392 Hz sits at the very edge of the 362 Hz band. A
note much higher and the m would vanish entirely.

Two related numbers:

- **m is −3.5 dB relative to the vowel.** Rule 1 asks for −10 to −15. Its
  amp is 0.8, against 0.11–0.30 for every fricative and plosive.
- **m, n, w, l and r are not diction-scaled.** Every other recipe
  multiplies by `dic`; these five do not. So **the diction-0 "vowels only"
  control is not vowels only** — the nasals and approximants play through
  it at full level. Worth knowing when A/Bing the pair: the control is
  "no fricatives or plosives", not "no consonants".

Verdict: the wider band won. But widening it to a *fixed* 0–1100 Hz only fixed
it where we happened to be listening.

## Are we tuning for one song?

Asked at the right moment, and the answer was: partly.

The m **diagnosis** generalised — m and n pass ≤1 harmonic at every pitch, and
**0 above C5**, where the nasal is simply silent. Amazing Grace didn't cause
that; it only revealed it.

The m **fix** did not generalise. A fixed 0–1100 Hz band gives 4/3/3/2
harmonics at A3–G4 — the six notes of this phrase — and 1/1/1 at C5–G5. It is a
**ratio problem, not a frequency problem**: a nasal murmur is "the low
harmonics of whatever note is sounding", so the band has to track f0. The v2
recipe is `0.8·f0 .. 5·f0`, which holds 3–5 harmonics from A3 to C6 with a
steady 7–8 bands lit, so loudness doesn't drift with pitch either.

**Not everything should be pitch-relative.** `b`, `d` and `g` keep absolute
bands: their spectral region is a place-of-articulation cue tied to the vocal
tract — the velar pinch for `g`, the alveolar region for `d` — and tracking f0
would move them off the cue that identifies them. They are also 20 ms
transients rather than 90 ms sustains, so a thin harmonic count reads as a blip
rather than a tone.

What the coverage sweep also exposed, which no amount of listening to this
phrase would have:

- **`b` is worse than `m` was** — sine-like at 5 of 8 pitches, and silent at
  three of them — and it does not appear in this phrase, so it has never been
  heard.
- **`f`, `b` and `w` have never been rendered** in anything auditioned.
- **Nothing above G4 had been tested**, for any consonant.

So gate 6 exists: any *sustained* voiced consonant must pass ≥2 harmonics
across A3–C6. It fails on the frozen reference (m, n) and passes on v2, and it
would have caught the whole class without a single listen. `tools/` now also
renders a consonant matrix — 15 consonants × 4 pitches — so tuning decisions
are made against the space rather than against whichever syllables a song
happens to contain.

**_(to fill in)_** `b` at C5 and above. Flagged, not retuned.

## Judge it on songs, not on drills

The consonant matrix — 15 consonants x 4 pitches, played as isolated syllables
— turned out to be useless as a listening test. Sixty context-free
consonant-vowel pairs is an engineering artifact, not something an ear can form
an opinion about. It stays in `tools/` because it is useful for *measuring*,
but the systematic sweep is gate 6's job, not a person's.

The lesson: **give the ear music, and let the gates do the coverage.** When a
consonant has never been heard, the fix is to write a song that uses it, not to
drill it. House of the Rising Sun was coded for exactly that — it carries `b`
in "been / poor / boy" and `w` in "one", both of which had never been rendered,
plus a minor key and a different pitch range.

### Gaps in the recipe table

Coding a second lyric exposed which English consonants have no recipe at all:

    p  v  th  sh  j  y  ng

`poor` is currently voiced as `b`, which is wrong — `p` is unvoiced and `b` is
voiced — and "There / They / the" all use `d` for `th`. Those are stand-ins,
not transcriptions. Worth knowing before the eSpeak path lands, since eSpeak
will produce the real phoneme set and these approximations disappear.

`f` still has no song to appear in — neither lyric contains one.

## The buzz: every note was missing its fundamental

"There's like a buzz noise." There was, and it was not the consonants.

The vowel spectrum is a 3-formant Gaussian projected onto the bands with sigma
0.20 in log-frequency. F1 sits at 530–730 Hz. A fundamental an octave and a
half below F1 is about **4.5 sigma out**, so the projection assigns it
essentially nothing:

    "ma"  (cc 80,  C4, f0 262 Hz)   band gain at f0 = 0.0005
    "the" (cc 38,  A3, f0 220 Hz)   band gain at f0 = 0.0000
    "grace" (cc 96, E4, f0 330 Hz)  band gain at f0 = 0.2233

Measured in the render, H1 came out at **−46 dB** relative to the loudest
harmonic. A harmonic stack with the root removed is the classic missing-
fundamental timbre — thin, nasal, buzzy. That is the buzz.

A real vocal tract is roughly **flat below F1**, not Gaussian-rolled-off: the
tube's transfer function approaches a constant under the first resonance. The
Gaussian is simply the wrong model down there. Flooring the sub-F1 bands at
0.35 restores H1 to 0 dB.

**Correction to an earlier reading of mine.** I first attributed this to rule
5's alternating polarity, having measured H1 at −46.3 dB with it and −12.4 dB
without. That was the wrong cause. A pure-tone sweep shows alternating polarity
is *better* at almost every note fundamental (+7 to +11 dB at B3–E5). What it
actually does is cancel the skirt leakage from the F1-region bands, which was
the only thing partially restoring a fundamental the projection had already
deleted. Two effects, and the projection is the primary one.

Verdict: both 0.35 and 0.60 fixed it. Took **0.35** — the smaller departure
from the reference model, and enough to put H1 back at 0 dB. `VOWEL_FLOOR` in
`vocoder_render.py` carries it per recipe set, so 0.60 is one edit away.

This reorders the whole hunt. We had been tuning consonants on top of a vowel
that was missing its root — the same shape of mistake as tuning consonants on
top of aliasing, which is the lesson this file already records. **Fix the
thing underneath first.** Every consonant verdict taken before this floor
landed was made against a broken vowel and may want revisiting.

Verdict on the z: **voicing 0.25, no voice bar.** Flatness goes 0.077 -> 0.313,
against 0.155 for the `s` beside it, so it stops being twice as tonal as a
fricative and starts being frication.

Worth recording the architectural limit behind it: **one voicing value covers
the whole spectrum**, so the engine cannot do what a real /z/ does — a voiced
bar low down and noisy frication up high, at the same time. The voice-bar
variant faked it by adding a band at the fundamental; it measured identically
to plain low-voicing and was not preferred. If voiced fricatives ever need to
be better than this, per-band voicing is the change, and it is not a small one.

## The verdict log

Deliverables 1 and 2 passed the listening gate with recipe set **v2**. The
original experiment found five defects by ear and then measured them; this
round found four more the same way, and the log is the point.

| # | Heard as | Measured | Change |
|---|---|---|---|
| 1 | "the M sounds weird" | nasal was 99.9% fundamental — a sine. 1 harmonic at every pitch, 0 above C5 | m/n band → pitch-relative `0.8·f0 .. 5·f0` |
| 2 | "too electronic", "a buzz" on the z | voicing 0.65 = 65% sawtooth. Flatness 0.077 vs 0.155 for the `s` beside it | z voicing → 0.25 |
| 3 | "there's like a buzz noise" | **every note missing its fundamental.** H1 46 dB down; band gain at f0 was 0.0005 on "ma", 0.0000 on "the" | sub-F1 bands floored at 0.35 |
| 4 | "the matrix doesn't help" | — | judge on songs; coverage is gate 6's job |

Three things this round taught that outlast the specific fixes:

**Fix the thing underneath first.** The missing fundamental was under every
consonant verdict given before it. That is the same mistake as tuning
consonants on top of aliasing, which this file already records from the
original experiment — and it happened again anyway, because a broken layer
does not announce itself, it just makes everything above it sound slightly
wrong.

**A diagnosis can generalise while its fix does not.** The nasal defect was
structural and present at every pitch; the first fix for it was tuned to the
six notes we happened to be listening to. Coverage has to be measured, not
auditioned.

**Give the ear music, not drills.** The 15×4 consonant matrix was unusable as a
listening test. Systematic coverage is what gates are for; a person needs a
song.

### Still open

- **`f` fails the fricative gate** at −20.2 dB (2–8 kHz) and −23.0 dB in its own
  band, against a −8 to −18 window. It is the only recipe stacking a sub-unity
  band gain (0.7) with the lowest amplitude (0.16). Neither lyric contains an
  `f`, so it has never been heard.
- **`k` reads out of spec but is not.** Its band sits mostly below the 2–8 kHz
  measurement window; in its own range it is −15.8 dB. The rule's single window
  does not suit a plosive centred at 1.2–2.4 kHz.
- **`b` is sine-like at 5 of 8 pitches** and silent at three. Flagged, not
  retuned — it is a 20 ms transient, not a 90 ms sustain.
- **No recipes for p, v, th, sh, j, y, ng.** `poor` is currently voiced as `b`,
  which is wrong, and th is `d` throughout. These disappear with eSpeak.
- **The m re-check** (`m_recheck_OLDnasal` vs `NEWnasal`) was never separately
  ruled on. The new nasal passes gate 6 and sounds right, so it stays, but
  whether the old one would now be acceptable on the fixed vowel is unanswered.

**_(to fill in)_** Verdict on the reference render, and on whether mode 2
should be aligned to the house sound or stay as the reference has it.
