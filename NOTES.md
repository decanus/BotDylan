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
