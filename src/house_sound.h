/*
 * house_sound.h — every tuned constant, in one place.
 *
 * ┌──────────────────────────────────────────────────────────────────────┐
 * │ PARITY RULE                                                          │
 * │ These numbers are mirrored in tools/simulator.html, which is the     │
 * │ reference implementation of the house sound. Any tuning change must  │
 * │ be made in BOTH places, in the SAME commit. See README.              │
 * └──────────────────────────────────────────────────────────────────────┘
 *
 * The vowel formant table is the one thing that is not here: it lives in
 * voice/presets/ so that alternate voices are a single swappable file.
 * Why each of these values is what it is: see NOTES.md.
 */
#pragma once

// ===== GLOTTAL SOURCE ======================================================
const float GLOTTIS_AMP_BASE   = 0.25f;  // amplitude at velocity 0
const float GLOTTIS_AMP_SCALE  = 0.5f;   // ...plus this much at velocity 127
const float SOURCE_GLOTTIS_GAIN = 0.85f; // glottis level into the source mixer

// ===== VIBRATO =============================================================
// Depth is proportional, not absolute: frequencyModulation() is in octaves,
// so the vibrato is a constant width in CENTS across the whole range. A fixed
// Hz deviation would make low notes wobble far wider than high ones.
const float VIBRATO_HZ        = 5.2f;
const float VIBRATO_LFO_AMP   = 0.35f;
const float VIBRATO_FM_OCTAVES = 0.12f;

// ===== BREATH ==============================================================
const float BREATH_DEFAULT  = 0.06f;
const float BREATH_CC_BASE  = 0.02f;
const float BREATH_CC_SPAN  = 0.25f;

// ===== FORMANT FILTERS =====================================================
// F1 is left broader than F2/F3 — see NOTES.md.
const float FORMANT_Q1 = 4.0f;
const float FORMANT_Q2 = 5.0f;
const float FORMANT_Q3 = 5.0f;

// ===== ENVELOPE (ms, and a 0..1 sustain) ===================================
const int   ENV_ATTACK_MS  = 45;
const int   ENV_DECAY_MS   = 120;
const float ENV_SUSTAIN    = 0.85f;
const int   ENV_RELEASE_MS = 260;

// ===== JAW MOTION ==========================================================
const float JAW_OPEN_RATE    = 0.30f;   // fast open, slow close
const float JAW_CLOSE_RATE   = 0.12f;
const float JAW_VEL_BASE     = 0.35f;   // openness at velocity 0
const float JAW_VEL_SCALE    = 0.65f;   // ...plus this much at velocity 127
const float JAW_VOWEL_NARROW = 0.35f;   // how far closed vowels close the mouth

// ===== CONTROL / MIDI ======================================================
const int   CONTROL_INTERVAL_MS = 5;    // 200 Hz control rate
const float PITCH_BEND_SEMIS    = 2.0f;
const int   NOTE_STACK_SIZE     = 10;
const float VOWEL_START         = 2.0f; // "ah"
