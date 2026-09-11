/*
 * voice.cpp — formant synthesis and note handling.
 *
 * Every number in here is a tuning decision. Change one and the robot sounds
 * like someone else; NOTES.md is the log of why each is what it is.
 */

#include <Arduino.h>

#include "config.h"
#include "face/jaw.h"
#include "voice/audio_graph.h"
#include "voice/voice.h"
#include "voice/vowel.h"

// The compile-time voice selection, e.g. voice/presets/warm.h. Defines
// VOWELS[] and NUM_VOWELS, and is included by this file alone.
#include VOICE_PRESET_HEADER

// ===== STATE ===============================================================
static float vowelPos     = 2.0f;       // fractional index into VOWELS; start "ah"
static float breathLevel  = 0.06f;
static float bendSemis    = 0.0f;
static int   currentNote  = -1;
static float noteVelocity = 0.0f;

static const int NOTE_STACK_SIZE = 10;
static int noteStack[NOTE_STACK_SIZE];  // last-note priority / legato
static int noteStackLen = 0;

// ===== VOICE CORE ==========================================================
static float midiToFreq(float note) {
  return 440.0f * powf(2.0f, (note - 69.0f) / 12.0f);
}

static void applyVowel() {
  float pos = constrain(vowelPos, 0.0f, (float)(NUM_VOWELS - 1));
  int   i   = (int)pos;
  int   j   = min(i + 1, NUM_VOWELS - 1);
  float t   = pos - i;

  for (int k = 0; k < 3; k++) {
    // Geometric interpolation of frequencies sounds smoother than linear
    float freq = VOWELS[i].f[k] * powf(VOWELS[j].f[k] / VOWELS[i].f[k], t);
    float gain = VOWELS[i].g[k] + (VOWELS[j].g[k] - VOWELS[i].g[k]) * t;
    switch (k) {
      case 0: formant1.frequency(freq); formantMix.gain(0, gain * 0.9f); break;
      case 1: formant2.frequency(freq); formantMix.gain(1, gain * 0.9f); break;
      case 2: formant3.frequency(freq); formantMix.gain(2, gain * 0.9f); break;
    }
  }
}

static void updatePitch() {
  if (currentNote >= 0) {
    glottis.frequency(midiToFreq((float)currentNote + bendSemis));
  }
}

static void startNote(int note, int velocity) {
  currentNote  = note;
  noteVelocity = velocity / 127.0f;
  updatePitch();
  glottis.amplitude(0.25f + 0.5f * noteVelocity);
  env.noteOn();
  jawSetTarget(0.35f + 0.65f * noteVelocity);
}

static void releaseOrFall() {
  if (noteStackLen > 0) {
    currentNote = noteStack[--noteStackLen];   // legato fall-back
    updatePitch();
  } else {
    env.noteOff();
    currentNote = -1;
    jawSetTarget(0.0f);
  }
}

// ===== PUBLIC API ==========================================================
void voiceNoteOn(int note, int velocity) {
  if (velocity == 0) { voiceNoteOff(note); return; }
  if (currentNote >= 0 && noteStackLen < NOTE_STACK_SIZE) {
    noteStack[noteStackLen++] = currentNote;
  }
  startNote(note, velocity);
}

void voiceNoteOff(int note) {
  for (int i = 0; i < noteStackLen; i++) {          // held background note?
    if (noteStack[i] == note) {
      for (int j = i; j < noteStackLen - 1; j++) noteStack[j] = noteStack[j + 1];
      noteStackLen--;
      return;
    }
  }
  if (note == currentNote) releaseOrFall();
}

void voiceAllNotesOff() {
  noteStackLen = 0;
  env.noteOff();
  currentNote = -1;
  jawSetTarget(0.0f);
}

void voiceSetVowelCC(int value) {
  vowelPos = (value / 127.0f) * (NUM_VOWELS - 1);
  applyVowel();
}

void voiceSetBreathCC(int value) {
  breathLevel = 0.02f + (value / 127.0f) * 0.25f;
  sourceMix.gain(1, breathLevel);
}

void voiceSetPitchBend(int bend) {
  bendSemis = (bend / 8192.0f) * 2.0f;
  updatePitch();
}

float voiceVowelPos() {
  return vowelPos;
}

// ===== SETUP ===============================================================
void voiceBegin() {
  AudioMemory(24);

  glottis.begin(WAVEFORM_BANDLIMIT_SAWTOOTH);
  glottis.frequencyModulation(0.12f);   // vibrato depth
  glottis.amplitude(0.0f);

  vibratoLFO.begin(WAVEFORM_SINE);
  vibratoLFO.frequency(5.2f);
  vibratoLFO.amplitude(0.35f);

  breath.amplitude(1.0f);
  sourceMix.gain(0, 0.85f);
  sourceMix.gain(1, breathLevel);

  formant1.resonance(4.0f);
  formant2.resonance(5.0f);
  formant3.resonance(5.0f);
  applyVowel();

  env.attack(45);
  env.decay(120);
  env.sustain(0.85f);
  env.release(260);
}
