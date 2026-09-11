/*
 * choir.cpp — shared vowel, channel allocation, jaw target.
 */

#include <Arduino.h>

#include "face/jaw.h"
#include "house_sound.h"
#include "voice/audio_graph.h"
#include "voice/choir.h"
#include "voice/formant_math.h"

static float vowelPos = VOWEL_START;

// MIDI channels are 1-based here (both usbMIDI and the MIDI library hand
// them over that way). Out-of-range channels sing soprano.
static int voiceForChannel(int channel) {
  int idx = channel - 1;
  return (idx >= 0 && idx < VOICE_COUNT) ? idx : 0;
}

static bool anySounding() {
  for (int i = 0; i < VOICE_COUNT; i++) {
    if (VOICES[i]->sounding()) return true;
  }
  return false;
}

void choirBegin() {
  AudioMemory(AUDIO_MEMORY_BLOCKS);
  breath.amplitude(BREATH_SOURCE_AMP);   // the shared bed every voice taps
  for (int i = 0; i < VOICE_COUNT; i++) VOICES[i]->begin();
}

void choirNoteOn(int channel, int note, int velocity) {
  if (velocity == 0) { choirNoteOff(channel, note); return; }
  int idx = voiceForChannel(channel);
  VOICES[idx]->noteOn(note, velocity);

  // The jaw follows the soprano; the lower voices only open it off its rest.
  if (idx == 0) {
    jawSetTarget(JAW_VEL_BASE + JAW_VEL_SCALE * (velocity / 127.0f));
  } else if (jawTarget() == 0.0f) {
    jawSetTarget(JAW_IDLE_OPEN);
  }
}

void choirNoteOff(int channel, int note) {
  VOICES[voiceForChannel(channel)]->noteOff(note);
  if (!anySounding()) jawSetTarget(0.0f);
}

void choirAllNotesOff() {
  for (int i = 0; i < VOICE_COUNT; i++) VOICES[i]->allNotesOff();
  jawSetTarget(0.0f);
}

void choirSetVowelCC(int value) {
  vowelPos = (value / 127.0f) * (NUM_VOWELS - 1);
  for (int i = 0; i < VOICE_COUNT; i++) VOICES[i]->setVowel(vowelPos);
}

void choirSetBreathCC(int value) {
  float level = BREATH_CC_BASE + (value / 127.0f) * BREATH_CC_SPAN;
  for (int i = 0; i < VOICE_COUNT; i++) VOICES[i]->setBreath(level);
}

void choirSetPitchBend(int channel, int bend) {
  VOICES[voiceForChannel(channel)]->setPitchBend((bend / 8192.0f) * PITCH_BEND_SEMIS);
}

float choirVowelPos() {
  return vowelPos;
}
