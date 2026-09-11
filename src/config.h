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
