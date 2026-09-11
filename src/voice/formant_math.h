/*
 * formant_math.h — the vowel morph, as pure arithmetic.
 *
 * Deliberately free of any Teensy Audio Library dependency so it can be
 * compiled and checked on a host machine: tools/parity_check.cpp diffs it
 * against the original sketch's applyVowel() across a full vowel sweep.
 * That is what proves a refactor left the timbre alone.
 */
#pragma once

#include <math.h>

#include "config.h"
#include VOICE_PRESET_HEADER   // defines VOWELS[] and NUM_VOWELS

// Gains are scaled by this on the way into the formant mixer.
const float FORMANT_MIX_SCALE = 0.9f;

struct FormantTargets {
  float freq[3];
  float gain[3];
};

// vowelPos is a fractional index into VOWELS. formantScale multiplies all
// three center frequencies — 1.0 is the reference voice, lower reads as a
// physically bigger singer.
inline void formantTargetsFor(float vowelPos, float formantScale,
                              FormantTargets &out) {
  const float hi = (float)(NUM_VOWELS - 1);
  float pos = vowelPos < 0.0f ? 0.0f : (vowelPos > hi ? hi : vowelPos);
  int   i   = (int)pos;
  int   j   = (i + 1 < NUM_VOWELS - 1) ? (i + 1) : (NUM_VOWELS - 1);
  float t   = pos - i;

  for (int k = 0; k < 3; k++) {
    // Geometric interpolation of frequencies sounds smoother than linear
    out.freq[k] = VOWELS[i].f[k] * powf(VOWELS[j].f[k] / VOWELS[i].f[k], t)
                  * formantScale;
    out.gain[k] = (VOWELS[i].g[k] + (VOWELS[j].g[k] - VOWELS[i].g[k]) * t)
                  * FORMANT_MIX_SCALE;
  }
}

// Equal temperament, A4 = 440 Hz. Fractional notes are meaningful: pitch bend
// and per-voice detune are both folded in before this is called.
inline float midiToFreq(float note) {
  return 440.0f * powf(2.0f, (note - 69.0f) / 12.0f);
}
