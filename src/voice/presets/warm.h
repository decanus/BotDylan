/*
 * warm.h — the default voice. Classic sung-vowel formants.
 *
 * These are the values the robot has always had; treat this file as the
 * reference the other presets are heard against.
 */
#pragma once

#include "voice/vowel.h"

// ===== VOWEL FORMANT TABLE =================================================
// F1/F2/F3 center frequencies (Hz) + per-formant gains. CC1 morphs
// left-to-right through this list. Retune freely — this is the accent.
const Vowel VOWELS[] = {
  { "oo", { 300,  870, 2240 }, { 1.00, 0.35, 0.12 } },
  { "oh", { 570,  840, 2410 }, { 1.00, 0.45, 0.15 } },
  { "ah", { 730, 1090, 2440 }, { 1.00, 0.60, 0.20 } },
  { "eh", { 530, 1840, 2480 }, { 1.00, 0.50, 0.22 } },
  { "ee", { 270, 2290, 3010 }, { 1.00, 0.30, 0.28 } },
};
const int NUM_VOWELS = sizeof(VOWELS) / sizeof(VOWELS[0]);
