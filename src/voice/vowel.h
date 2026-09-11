/*
 * vowel.h — the shape of one vowel in a formant preset.
 *
 * Preset tables in presets/ are arrays of these. Kept separate from the
 * tables themselves so a preset header is nothing but tuning data.
 */
#pragma once

// F1/F2/F3 center frequencies (Hz) + per-formant gains.
struct Vowel {
  const char *name;
  float f[3];
  float g[3];
};
