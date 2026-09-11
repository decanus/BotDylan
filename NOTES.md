# Tuning notes

A log of musical decisions — what each number does, why it is what it is, and
what made the robot sound sung rather than robotic.

Seeded from the original sketch's comments and from the values themselves.
Sections marked **_(to fill in)_** are waiting on your ear; nothing in the
code recorded a reason for them, so nothing is asserted here.

---

## Vibrato — 5.2 Hz, depth 0.12, LFO amplitude 0.35

```c
glottis.frequencyModulation(0.12f);   // vibrato depth
vibratoLFO.frequency(5.2f);
vibratoLFO.amplitude(0.35f);
```

The LFO feeds the FM input of the sawtooth, so depth is the product of
`frequencyModulation` (octaves at full scale) and the LFO's own amplitude.

Human singing vibrato sits around 5–7 Hz. 5.2 Hz is at the slow end of that
band — slower reads as controlled and adult, faster as nervous or operatic.

**_(to fill in)_** Why 5.2 and not 5.5 or 6? Was this landed on by ear or
picked off a reference? Note what it sounded like on either side.

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
breathLevel = 0.06f;             // default breath, CC2 overrides
// CC2: breathLevel = 0.02f + (val / 127.0f) * 0.25f;
```

Breath sits at 6% by default, and CC2 sweeps 2%–27%. Noise is what keeps a
sustained note from sounding like a held organ chord.

**_(to fill in)_** Whether breath should duck during the sustain and rise on
attack/release, which is what real breath does.

---

## Velocity mapping

```c
glottis.amplitude(0.25f + 0.5f * noteVelocity);   // loudness
jawSetTarget(0.35f + 0.65f * noteVelocity);       // mouth
```

Both are offset-plus-scale rather than proportional: velocity 1 still makes
sound (0.25) and still opens the mouth (0.35). A quiet note that barely moves
the jaw looks broken.

The jaw opens proportionally *further* than the voice gets louder (0.65 span
vs 0.5) — the mouth is more expressive than the amplitude.

---

## Jaw motion

```c
float rate = (target > jawActual) ? 0.30f : 0.12f;   // fast open, slow close
```

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
