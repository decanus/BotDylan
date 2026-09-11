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

// ===== THE VOICES ==========================================================
// One entry per singer. formantScale multiplies all three formant centre
// frequencies: below 1.0 reads as a physically bigger person, which is what
// makes the bass a bass rather than a transposed soprano.
struct VoiceDef {
  const char *name;
  float vibratoHz;
  float detuneCents;
  float formantScale;
  float level;          // gain into the output mixer
};

//              name       vibrato  detune  formant  mix
//                              Hz    cents    scale  level
const VoiceDef VOICE_DEFS[] = {
  { "soprano",     5.0f,   0.0f,   1.00f, 0.42f },
  { "alto",        4.6f,  +4.0f,   0.93f, 0.30f },
  { "bass",        4.3f,  -3.0f,   0.82f, 0.34f },
};
const int VOICE_COUNT = sizeof(VOICE_DEFS) / sizeof(VOICE_DEFS[0]);

// ===== GLOTTAL SOURCE ======================================================
const float GLOTTIS_AMP_BASE   = 0.22f;  // amplitude at velocity 0
const float GLOTTIS_AMP_SCALE  = 0.5f;   // ...plus this much at velocity 127
const float SOURCE_GLOTTIS_GAIN = 0.85f; // glottis level into the source mixer

// ===== VIBRATO =============================================================
// Depth is proportional, not absolute: frequencyModulation() is in octaves,
// so the vibrato is a constant width in CENTS across the whole range. A fixed
// Hz deviation would make low notes wobble far wider than high ones.
const float VIBRATO_LFO_AMP   = 0.35f;
const float VIBRATO_FM_OCTAVES = 0.12f;

// ===== BREATH ==============================================================
// Breath is OFF by default now: the constant noise bed made the tone muddier,
// and removing it was one of the clearest wins of the session. CC2 still
// sweeps it in from silence for anyone who wants the air back.
const float BREATH_SOURCE_AMP = 1.0f;   // the noise generator's own level
const float BREATH_DEFAULT  = 0.0f;     // ...and how much of it each voice takes
const float BREATH_CC_BASE  = 0.0f;
const float BREATH_CC_SPAN  = 0.27f;

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
const float JAW_OPEN_RATE    = 0.28f;   // fast open, slow close
const float JAW_CLOSE_RATE   = 0.11f;
const float JAW_VEL_BASE     = 0.35f;   // openness at velocity 0
const float JAW_VEL_SCALE    = 0.65f;   // ...plus this much at velocity 127
const float JAW_VOWEL_NARROW = 0.35f;   // how far closed vowels close the mouth

// ===== ARTICULATION ========================================================
// Vowels and pitch are smoothed with a one-pole filter at the control rate,
// matching setTargetAtTime() in the simulator: these are TIME CONSTANTS, not
// ramp durations, so the value gets ~63% of the way there in this long.
const float VOWEL_SMOOTH_MS = 35.0f;
const float PORTAMENTO_MS   = 25.0f;
const float INITIAL_PITCH_HZ = 200.0f;   // so the first note does not swoop up from 0

// A glide starts the vowel somewhere else and lets the smoothing carry it to
// the note's real vowel. This is the whole articulation system: no consonant
// noise, just formant motion. See NOTES.md on why noise was rejected.
const int   GLIDE_MS      = 110;
const float GLIDE_START_W = 0.0f;   // "oo"
const float GLIDE_START_L = 1.2f;   // just past "oh"

// CC4 sweeps the soprano 2..9 Hz; the other voices keep their ratio to it.
const float VIBRATO_CC_MIN  = 2.0f;
const float VIBRATO_CC_SPAN = 7.0f;

// ===== CONTROL / MIDI ======================================================
const int   CONTROL_INTERVAL_MS = 5;    // 200 Hz control rate
const float PITCH_BEND_SEMIS    = 2.0f;
const int   NOTE_STACK_SIZE     = 10;
const float VOWEL_START         = 2.0f; // "ah"

// ===== JAW, POLYPHONIC =====================================================
// The jaw follows the soprano. When only the lower voices sound there is no
// velocity to follow, so the mouth sits at a neutral opening rather than shut.
const float JAW_IDLE_OPEN = 0.45f;

// ===== BROWS ===============================================================
// The brows lift while anything is singing and settle back after, and lift
// further on a harder note, so a phrase has expression rather than one move at
// the top of the song. 0.5 at velocity 0, 1.0 at velocity 127; the simulator
// draws the same thing as 4..8 SVG units.
//
// The original 2 units of travel measured 2.11 px on screen and read as no
// movement at all. See NOTES.md.
//
// Expressed as a TIME CONSTANT, not a per-tick rate, and this matters: the
// simulator eases 0.08 per animation frame at ~60 fps, which is a ~200 ms time
// constant. Copying the number 0.08 to a 200 Hz control loop would ease 3.3x
// too fast. Same number, different tick rate, different feel. See NOTES.md.
const float BROW_SMOOTH_MS  = 200.0f;
const float BROW_VEL_BASE   = 0.5f;   // raised this much at velocity 0
const float BROW_VEL_SCALE  = 0.5f;   // ...plus this much at velocity 127

// ===== AUDIO ENGINE ========================================================
// Blocks for the Audio Library. Each voice is waveform + LFO + 3 filters +
// 2 mixers + envelope, so this has to grow with the choir. Watch
// AudioMemoryUsageMax() after changing it.
const int AUDIO_MEMORY_BLOCKS = 60;
