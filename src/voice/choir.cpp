/*
 * choir.cpp — shared vowel, channel allocation, jaw target.
 */

#include <Arduino.h>

#include "face/brow.h"
#include "face/jaw.h"
#include "house_sound.h"
#include "voice/audio_graph.h"
#include "voice/choir.h"
#include "voice/formant_math.h"

// vowelTarget is where CC1 says the vowel should be. vowelPos is where it is
// being commanded right now — during a glide those differ, and the one-pole
// smoothing in each Voice does the actual travelling.
static int mode = MODE_FORMANT;
static int lyricCursor = 0;

static float vowelTarget = VOWEL_START;
static float vowelPos    = VOWEL_START;

// CC3 latches a glide for the NEXT note-on, then clears.
enum GlideKind { GLIDE_NONE = 0, GLIDE_W, GLIDE_L };
static GlideKind pendingGlide = GLIDE_NONE;
static bool          glideActive = false;
static elapsedMillis glideTimer;

// MIDI channels are 1-based here (both usbMIDI and the MIDI library hand
// them over that way). Out-of-range channels sing soprano.
static int voiceForChannel(int channel) {
  int idx = channel - 1;
  return (idx >= 0 && idx < VOICE_COUNT) ? idx : 0;
}

static void pushVowel() {
  for (int i = 0; i < VOICE_COUNT; i++) VOICES[i]->setVowel(vowelPos);
}

static bool anySounding() {
  for (int i = 0; i < VOICE_COUNT; i++) {
    if (VOICES[i]->sounding()) return true;
  }
  return false;
}

int choirMode() { return mode; }

void choirResetLyric() { lyricCursor = 0; }

void choirSetModeCC(int value) {
  int next = (value < 64) ? MODE_FORMANT : MODE_VOCODER;
  if (next == mode) return;
  // Silence whichever engine is handing over, so a mode change never leaves a
  // note hanging on the engine that just stopped being addressed.
  for (int i = 0; i < VOICE_COUNT; i++) VOICES[i]->allNotesOff();
  vocoder.allNotesOff();
  jawSetTarget(0.0f);
  browSetTarget(0.0f);
  lyricCursor = 0;
  mode = next;
}

void choirBegin() {
  AudioMemory(AUDIO_MEMORY_BLOCKS);
  breath.amplitude(BREATH_SOURCE_AMP);   // the shared bed every voice taps
  for (int i = 0; i < VOICE_COUNT; i++) {
    VOICES[i]->begin();
    voiceMix.gain(i, VOICE_DEFS[i].level);
  }
  vocoder.begin();
  voiceMix.gain(3, VOCODER_LEVEL);
}

void choirNoteOn(int channel, int note, int velocity) {
  if (velocity == 0) { choirNoteOff(channel, note); return; }

  if (mode == MODE_VOCODER) {
    const VocEnvelope *e = &ag_index[lyricCursor % ag_count];
    lyricCursor++;
    // Duration is unknown at note-on from live MIDI, so the envelope is sized
    // for a comfortable sung note and cut short by the note-off if it comes
    // sooner. A sequencer that knows its own note lengths could do better.
    vocoder.noteOn(note, velocity, e->syllable, 900.0f);
    jawSetTarget(JAW_VEL_BASE + JAW_VEL_SCALE * (velocity / 127.0f));
    browSetTarget(BROW_VEL_BASE + BROW_VEL_SCALE * (velocity / 127.0f));
    return;
  }

  int idx = voiceForChannel(channel);

  // Articulation: start the vowel somewhere else and let it travel. The whole
  // choir glides together, because the choir sings one syllable.
  if (pendingGlide != GLIDE_NONE) {
    vowelPos = (pendingGlide == GLIDE_W) ? GLIDE_START_W : GLIDE_START_L;
    pushVowel();
    glideActive = true;
    glideTimer  = 0;
    pendingGlide = GLIDE_NONE;          // latched for one note only
  }

  VOICES[idx]->noteOn(note, velocity);

  // The jaw follows the soprano; the lower voices only open it off its rest.
  if (idx == 0) {
    jawSetTarget(JAW_VEL_BASE + JAW_VEL_SCALE * (velocity / 127.0f));
  } else if (jawTarget() == 0.0f) {
    jawSetTarget(JAW_IDLE_OPEN);
  }
  // Brows lift for any voice, not just the soprano, and further on a harder
  // note — the same drive the jaw uses.
  browSetTarget(BROW_VEL_BASE + BROW_VEL_SCALE * (velocity / 127.0f));
}

void choirNoteOff(int channel, int note) {
  if (mode == MODE_VOCODER) {
    vocoder.noteOff();
    jawSetTarget(0.0f);
    browSetTarget(0.0f);
    return;
  }
  VOICES[voiceForChannel(channel)]->noteOff(note);
  if (!anySounding()) {
    jawSetTarget(0.0f);
    browSetTarget(0.0f);
  }
}

void choirAllNotesOff() {
  vocoder.allNotesOff();
  lyricCursor = 0;
  for (int i = 0; i < VOICE_COUNT; i++) VOICES[i]->allNotesOff();
  pendingGlide = GLIDE_NONE;
  glideActive  = false;
  jawSetTarget(0.0f);
  browSetTarget(0.0f);
}

void choirSetVowelCC(int value) {
  vowelTarget = (value / 127.0f) * (NUM_VOWELS - 1);
  if (!glideActive) {                   // a glide owns the vowel until it lands
    vowelPos = vowelTarget;
    pushVowel();
  }
}

void choirSetGlideCC(int value) {
  pendingGlide = (value == 0) ? GLIDE_NONE : (value < 64 ? GLIDE_W : GLIDE_L);
}

void choirSetVibratoRateCC(int value) {
  float hz = VIBRATO_CC_MIN + (value / 127.0f) * VIBRATO_CC_SPAN;
  for (int i = 0; i < VOICE_COUNT; i++) VOICES[i]->setVibratoRate(hz);
}

void choirUpdate() {
  if (mode == MODE_VOCODER) { vocoder.update(); return; }
  if (glideActive && glideTimer >= (unsigned)GLIDE_MS) {
    glideActive = false;
    vowelPos    = vowelTarget;          // release it toward the note's vowel
    pushVowel();
  }
  for (int i = 0; i < VOICE_COUNT; i++) VOICES[i]->update();
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
