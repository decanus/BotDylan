/*
 * voice.h — one singer.
 *
 * Owns its own audio nodes as members. The Teensy Audio Library requires
 * AudioStream objects to live in static storage, which a global instance of
 * this class satisfies: the members are constructed as part of the global.
 * AudioConnection members MUST be declared after the nodes they join, because
 * members are constructed in declaration order.
 *
 * A Voice is monophonic with last-note priority. Three of them make the choir;
 * see choir.h for the shared vowel position and channel allocation.
 */
#pragma once

#include <Audio.h>

#include "house_sound.h"

class Voice {
 public:
  Voice(const VoiceDef &def, AudioStream &breathSrc,
        AudioStream &outDest, uint8_t outPort);

  void begin();

  void noteOn(int note, int velocity);
  void noteOff(int note);
  void allNotesOff();

  // The choir shares one vowel position. Normally the move is smoothed over
  // VOWEL_SMOOTH_MS; `immediate` snaps, which is only for start-up.
  void setVowel(float vowelPos, bool immediate = false);

  // Control-rate tick: advances the vowel and pitch smoothing one step.
  void update();
  void setBreath(float level);
  void setPitchBend(float semis);
  void setVibratoRate(float sopranoHz);   // scaled by this voice's ratio

  bool  sounding() const { return currentNote_ >= 0; }
  float velocity() const { return noteVelocity_; }
  const VoiceDef &def() const { return def_; }

  // --- audio nodes: construction order matters, do not reorder ---
  AudioSynthWaveform          vibratoLFO;
  AudioSynthWaveformModulated glottis;
  AudioMixer4                 sourceMix;
  AudioFilterStateVariable    formant1;
  AudioFilterStateVariable    formant2;
  AudioFilterStateVariable    formant3;
  AudioMixer4                 formantMix;
  AudioEffectEnvelope         env;

  // --- connections: declared after the nodes, on purpose ---
  AudioConnection cLfoToGlottis, cGlottisToSource, cBreathToSource;
  AudioConnection cSourceToF1, cSourceToF2, cSourceToF3;
  AudioConnection cF1ToMix, cF2ToMix, cF3ToMix;
  AudioConnection cMixToEnv, cEnvToOut;

 private:
  void writeFormants();
  void startNote(int note, int velocity);
  void releaseOrFall();
  void updatePitch();

  const VoiceDef &def_;
  int   currentNote_;
  // Smoothing state: cur_ chases tgt_ one control step at a time.
  float curFreq_[3], tgtFreq_[3];
  float curGain_[3], tgtGain_[3];
  float curPitch_, tgtPitch_;
  float vowelAlpha_, pitchAlpha_;
  float noteVelocity_;
  float bendSemis_;
  int   noteStack_[NOTE_STACK_SIZE];   // last-note priority / legato
  int   noteStackLen_;
};
