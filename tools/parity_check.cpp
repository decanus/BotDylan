/*
 * parity_check.cpp — proves the vowel morph still computes what it always did.
 *
 * Compiles on the host (no Teensy, no Audio Library) because formant_math.h
 * is deliberately dependency-free. It sweeps the whole vowel range and
 * compares the current formantTargetsFor() against a verbatim transcription
 * of applyVowel() from the original sketch at cbe372d, bit for bit.
 *
 *   c++ -std=c++17 -I src tools/parity_check.cpp -o /tmp/parity && /tmp/parity
 *
 * A refactor that changes the timbre fails here. Build-size parity is a
 * proxy; this is evidence.
 */

#include <cmath>
#include <cstdio>
#include <cstring>

#include "voice/formant_math.h"

// Verbatim applyVowel() from cbe372d, with Arduino's constrain()/min()
// macros expanded to their definitions. Do not "clean up" this function —
// its whole job is to be the old code.
static void originalApplyVowel(float vowelPos, float *freqOut, float *gainOut) {
  float lo = 0.0f, hi = (float)(NUM_VOWELS - 1);
  float pos = (vowelPos < lo) ? lo : ((vowelPos > hi) ? hi : vowelPos);
  int   i   = (int)pos;
  int   j   = ((i + 1) < (NUM_VOWELS - 1)) ? (i + 1) : (NUM_VOWELS - 1);
  float t   = pos - i;

  for (int k = 0; k < 3; k++) {
    float freq = VOWELS[i].f[k] * powf(VOWELS[j].f[k] / VOWELS[i].f[k], t);
    float gain = VOWELS[i].g[k] + (VOWELS[j].g[k] - VOWELS[i].g[k]) * t;
    freqOut[k] = freq;
    gainOut[k] = gain * 0.9f;   // the old call site's scale factor
  }
}

int main() {
  const int STEPS = 40001;          // -0.5 .. 4.5, well past both clamps
  int checked = 0, mismatches = 0;

  for (int s = 0; s < STEPS; s++) {
    float pos = -0.5f + (5.0f * s) / (STEPS - 1);

    float oldF[3], oldG[3];
    originalApplyVowel(pos, oldF, oldG);

    FormantTargets now;
    formantTargetsFor(pos, 1.0f, now);   // 1.0 == the reference voice

    for (int k = 0; k < 3; k++) {
      checked += 2;
      if (memcmp(&oldF[k], &now.freq[k], sizeof(float)) != 0) {
        if (mismatches < 10)
          printf("  FREQ pos=%.5f k=%d  old=%.9g  new=%.9g\n",
                 pos, k, oldF[k], now.freq[k]);
        mismatches++;
      }
      if (memcmp(&oldG[k], &now.gain[k], sizeof(float)) != 0) {
        if (mismatches < 10)
          printf("  GAIN pos=%.5f k=%d  old=%.9g  new=%.9g\n",
                 pos, k, oldG[k], now.gain[k]);
        mismatches++;
      }
    }
  }

  printf("vowel sweep: %d float comparisons, %d mismatches\n", checked, mismatches);

  // The formant scale must be exactly neutral at 1.0, and must actually
  // scale otherwise — a silent no-op here would hide a broken bass voice.
  FormantTargets a, b;
  formantTargetsFor(2.0f, 1.0f, a);
  formantTargetsFor(2.0f, 0.82f, b);
  bool scaled = true;
  for (int k = 0; k < 3; k++) {
    if (b.freq[k] != a.freq[k] * 0.82f) scaled = false;
    if (b.gain[k] != a.gain[k])         scaled = false;   // gains must not scale
  }
  printf("formant scale 0.82 applied to freqs only: %s\n", scaled ? "yes" : "NO");

  if (mismatches == 0 && scaled) {
    printf("PARITY OK\n");
    return 0;
  }
  printf("PARITY FAILED\n");
  return 1;
}
