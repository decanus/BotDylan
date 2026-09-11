/*
 * config.h — the knobs you are most likely to change.
 *
 * Board/input selection, jaw linkage trim, and which voice preset gets
 * compiled in. Nothing here affects the synthesis itself; the tuning that
 * shapes the sound lives in src/voice/presets/ and src/voice/voice.cpp.
 */
#pragma once

// ===== INPUT CONFIG ========================================================
#define ENABLE_DIN_MIDI 1   // Digitakt / EP-133 via optocoupler on RX1
#define ENABLE_USB_HOST 1   // Teensy 4.1 host port (OP-1 field) — set 0 on 4.0

// ===== VOICE PRESET ========================================================
// Which vowel formant table to compile in. Override from platformio.ini with
//   build_flags = -D VOICE_PRESET_HEADER='"voice/presets/choir.h"'
// See README "Adding a voice preset".
#ifndef VOICE_PRESET_HEADER
#define VOICE_PRESET_HEADER "voice/presets/warm.h"
#endif

// ===== JAW LINKAGE =========================================================
const int JAW_PIN        = 3;
const int JAW_CLOSED_DEG = 12;   // trim these two to your linkage
const int JAW_OPEN_DEG   = 68;

// ===== BROW ACTUATOR (reserved) ============================================
// Eyebrows are a first-class face feature, not a simulator flourish. The pin
// is claimed now so the firmware is ready before the head is; one micro servo
// driving both brows through a linkage is the intended build.
// Set ENABLE_BROW_SERVO to 1 once a servo is actually wired to BROW_PIN — the
// motion model tracks browTarget either way, so nothing else changes.
#define ENABLE_BROW_SERVO 0
const int BROW_PIN      = 4;
const int BROW_DOWN_DEG = 80;   // trim these two to your linkage
const int BROW_UP_DEG   = 62;

// ===== LID ACTUATOR (reserved) =============================================
// Blinking, ported from the simulator. One micro servo drives both lids off a
// shared shaft, the way the brows share one linkage. Reserved on the same
// terms as the brows: the motion model runs whether or not a servo is
// attached, so wiring one later is a one-line change.
//
// ⚠️ These two angles are a placeholder that the servo cannot actually hit.
// The blink shuts in the first BLINK_CLOSE_FRAC of BLINK_MS — 56 ms — and an
// MG90S is specified around 100 ms per 60 degrees, so the 85 degrees below
// would need about 142 ms. That is 2.5x too slow, not marginal.
//
// Two ways out, and the head has to pick one before this is wired:
//   - gear the linkage so a ~34 degree sweep drives the full lid travel, or
//   - lengthen BLINK_MS to about 354 ms and accept a slower blink.
// See hardware/head_spec.md. Trim these to whichever the linkage ends up being.
#define ENABLE_LID_SERVO 0
const int LID_PIN      = 5;
const int LID_OPEN_DEG = 20;
const int LID_SHUT_DEG = 105;

// ===== DIAGNOSTICS =========================================================
// Prints audio CPU and memory headroom over USB serial every couple of
// seconds, but only when a host is actually listening. Costs nothing when 0.
#define ENABLE_PERF_REPORT 1
