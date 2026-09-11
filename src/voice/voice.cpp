/*
 * voice.cpp — one singer's synthesis and note handling.
 *
 * Every number in here comes from house_sound.h, which is mirrored in
 * tools/simulator.html. NOTES.md is the log of why each is what it is.
 */

#include <Arduino.h>

#include "house_sound.h"
#include "voice/formant_math.h"
#include "voice/voice.h"

// The connections are built in the initialiser list so that they run after
// every node above them has been constructed. breathSrc and outDest are
// external: the noise bed and the output mixer are shared by the whole choir.
Voice::Voice(const VoiceDef &def, AudioStream &breathSrc,
             AudioStream &outDest, uint8_t outPort)
    : cLfoToGlottis(vibratoLFO, 0, glottis, 0),
      cGlottisToSource(glottis, 0, sourceMix, 0),
      cBreathToSource(breathSrc, 0, sourceMix, 1),
      cSourceToF1(sourceMix, 0, formant1, 0),
      cSourceToF2(sourceMix, 0, formant2, 0),
      cSourceToF3(sourceMix, 0, formant3, 0),
      cF1ToMix(formant1, 1, formantMix, 0),   // port 1 = bandpass out
      cF2ToMix(formant2, 1, formantMix, 1),
      cF3ToMix(formant3, 1, formantMix, 2),
      cMixToEnv(formantMix, 0, env, 0),
      cEnvToOut(env, 0, outDest, outPort),
      def_(def),
      currentNote_(-1),
      noteVelocity_(0.0f),
      bendSemis_(0.0f),
      noteStackLen_(0) {}

void Voice::begin() {
  glottis.begin(WAVEFORM_BANDLIMIT_SAWTOOTH);
  glottis.frequencyModulation(VIBRATO_FM_OCTAVES);   // vibrato depth
  glottis.amplitude(0.0f);

  vibratoLFO.begin(WAVEFORM_SINE);
  vibratoLFO.frequency(def_.vibratoHz);
  vibratoLFO.amplitude(VIBRATO_LFO_AMP);

  sourceMix.gain(0, SOURCE_GLOTTIS_GAIN);
  sourceMix.gain(1, BREATH_DEFAULT);

  formant1.resonance(FORMANT_Q1);
  formant2.resonance(FORMANT_Q2);
  formant3.resonance(FORMANT_Q3);
  setVowel(VOWEL_START);

  env.attack(ENV_ATTACK_MS);
  env.decay(ENV_DECAY_MS);
  env.sustain(ENV_SUSTAIN);
  env.release(ENV_RELEASE_MS);
}

// ===== SYNTHESIS ===========================================================
void Voice::setVowel(float vowelPos) {
  FormantTargets t;
  formantTargetsFor(vowelPos, def_.formantScale, t);
  formant1.frequency(t.freq[0]); formantMix.gain(0, t.gain[0]);
  formant2.frequency(t.freq[1]); formantMix.gain(1, t.gain[1]);
  formant3.frequency(t.freq[2]); formantMix.gain(2, t.gain[2]);
}

void Voice::setBreath(float level) {
  sourceMix.gain(1, level);
}

void Voice::setVibratoRate(float sopranoHz) {
  // Voices keep their relative vibrato character as the rate is automated.
  vibratoLFO.frequency(sopranoHz * (def_.vibratoHz / VOICE_DEFS[0].vibratoHz));
}

void Voice::updatePitch() {
  if (currentNote_ >= 0) {
    glottis.frequency(midiToFreq((float)currentNote_ + bendSemis_
                                 + def_.detuneCents / 100.0f));
  }
}

void Voice::setPitchBend(float semis) {
  bendSemis_ = semis;
  updatePitch();
}

// ===== NOTE PRIORITY =======================================================
void Voice::startNote(int note, int velocity) {
  currentNote_  = note;
  noteVelocity_ = velocity / 127.0f;
  updatePitch();
  glottis.amplitude(GLOTTIS_AMP_BASE + GLOTTIS_AMP_SCALE * noteVelocity_);
  env.noteOn();
}

void Voice::releaseOrFall() {
  if (noteStackLen_ > 0) {
    currentNote_ = noteStack_[--noteStackLen_];   // legato fall-back
    updatePitch();
  } else {
    env.noteOff();
    currentNote_ = -1;
  }
}

void Voice::noteOn(int note, int velocity) {
  if (velocity == 0) { noteOff(note); return; }
  if (currentNote_ >= 0 && noteStackLen_ < NOTE_STACK_SIZE) {
    noteStack_[noteStackLen_++] = currentNote_;
  }
  startNote(note, velocity);
}

void Voice::noteOff(int note) {
  for (int i = 0; i < noteStackLen_; i++) {          // held background note?
    if (noteStack_[i] == note) {
      for (int j = i; j < noteStackLen_ - 1; j++) noteStack_[j] = noteStack_[j + 1];
      noteStackLen_--;
      return;
    }
  }
  if (note == currentNote_) releaseOrFall();
}

void Voice::allNotesOff() {
  noteStackLen_ = 0;
  env.noteOff();
  currentNote_ = -1;
}
