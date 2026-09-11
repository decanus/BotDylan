/*
 * voice.cpp — formant synthesis and note handling.
 *
 * Every number in here is a tuning decision. Change one and the robot sounds
 * like someone else; NOTES.md is the log of why each is what it is.
 */

#include <Arduino.h>

#include "config.h"
#include "face/jaw.h"
#include "house_sound.h"
#include "voice/audio_graph.h"
#include "voice/formant_math.h"   // pulls in the selected preset's VOWELS[]
#include "voice/voice.h"

// ===== STATE ===============================================================
static float vowelPos     = VOWEL_START;   // fractional index into VOWELS
static float breathLevel  = BREATH_DEFAULT;
static float bendSemis    = 0.0f;
static int   currentNote  = -1;
static float noteVelocity = 0.0f;

static int noteStack[NOTE_STACK_SIZE];  // last-note priority / legato
static int noteStackLen = 0;

// ===== VOICE CORE ==========================================================
static float midiToFreq(float note) {
  return 440.0f * powf(2.0f, (note - 69.0f) / 12.0f);
}

static void applyVowel() {
  FormantTargets t;
  formantTargetsFor(vowelPos, 1.0f, t);
  formant1.frequency(t.freq[0]); formantMix.gain(0, t.gain[0]);
  formant2.frequency(t.freq[1]); formantMix.gain(1, t.gain[1]);
  formant3.frequency(t.freq[2]); formantMix.gain(2, t.gain[2]);
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
  glottis.amplitude(GLOTTIS_AMP_BASE + GLOTTIS_AMP_SCALE * noteVelocity);
  env.noteOn();
  jawSetTarget(JAW_VEL_BASE + JAW_VEL_SCALE * noteVelocity);
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
  breathLevel = BREATH_CC_BASE + (value / 127.0f) * BREATH_CC_SPAN;
  sourceMix.gain(1, breathLevel);
}

void voiceSetPitchBend(int bend) {
  bendSemis = (bend / 8192.0f) * PITCH_BEND_SEMIS;
  updatePitch();
}

float voiceVowelPos() {
  return vowelPos;
}

// ===== SETUP ===============================================================
void voiceBegin() {
  AudioMemory(24);

  glottis.begin(WAVEFORM_BANDLIMIT_SAWTOOTH);
  glottis.frequencyModulation(VIBRATO_FM_OCTAVES);   // vibrato depth
  glottis.amplitude(0.0f);

  vibratoLFO.begin(WAVEFORM_SINE);
  vibratoLFO.frequency(VIBRATO_HZ);
  vibratoLFO.amplitude(VIBRATO_LFO_AMP);

  breath.amplitude(1.0f);
  sourceMix.gain(0, SOURCE_GLOTTIS_GAIN);
  sourceMix.gain(1, breathLevel);

  formant1.resonance(FORMANT_Q1);
  formant2.resonance(FORMANT_Q2);
  formant3.resonance(FORMANT_Q3);
  applyVowel();

  env.attack(ENV_ATTACK_MS);
  env.decay(ENV_DECAY_MS);
  env.sustain(ENV_SUSTAIN);
  env.release(ENV_RELEASE_MS);
}
