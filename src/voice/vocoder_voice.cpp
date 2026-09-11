/*
 * vocoder_voice.cpp — mode 2's audio graph and envelope playback.
 */

#include <Arduino.h>

#include "voice/formant_math.h"
#include "voice/vocoder_voice.h"
#include <string.h>

// The same 14 log-spaced centres the tools use: 220 Hz to 5.6 kHz.
static const float VOC_CENTRE[VOC_BANDS] = {
  220.0000f,
  282.2010f,
  361.9881f,
  464.3336f,
  595.6153f,
  764.0146f,
  980.0257f,
  1257.1099f,
  1612.5346f,
  2068.4491f,
  2653.2651f,
  3403.4270f,
  4365.6833f,
  5600.0000f,
};
static const float VOC_Q = 4.5f;
static const float VOC_FRAME_MS = 10.0f;

// Each band's mixer channel, and which of the four sub-mixers it lands on.
static inline int mixerOf(int b)  { return b / 4; }
static inline int channelOf(int b){ return b % 4; }

VocoderVoice::VocoderVoice(AudioStream &outDest, uint8_t outPort)
    : cLfo(vibratoLFO, 0, glottis, 0),
      cGlottis(glottis, 0, excMix, 0),
      cNoise(noise, 0, excMix, 1),
      cB0(excMix, 0, band[0], 0),   cB1(excMix, 0, band[1], 0),
      cB2(excMix, 0, band[2], 0),   cB3(excMix, 0, band[3], 0),
      cB4(excMix, 0, band[4], 0),   cB5(excMix, 0, band[5], 0),
      cB6(excMix, 0, band[6], 0),   cB7(excMix, 0, band[7], 0),
      cB8(excMix, 0, band[8], 0),   cB9(excMix, 0, band[9], 0),
      cB10(excMix, 0, band[10], 0), cB11(excMix, 0, band[11], 0),
      cB12(excMix, 0, band[12], 0), cB13(excMix, 0, band[13], 0),
      // port 1 is the bandpass output
      cM0(band[0], 1, bandMix[0], 0),  cM1(band[1], 1, bandMix[0], 1),
      cM2(band[2], 1, bandMix[0], 2),  cM3(band[3], 1, bandMix[0], 3),
      cM4(band[4], 1, bandMix[1], 0),  cM5(band[5], 1, bandMix[1], 1),
      cM6(band[6], 1, bandMix[1], 2),  cM7(band[7], 1, bandMix[1], 3),
      cM8(band[8], 1, bandMix[2], 0),  cM9(band[9], 1, bandMix[2], 1),
      cM10(band[10], 1, bandMix[2], 2), cM11(band[11], 1, bandMix[2], 3),
      cM12(band[12], 1, bandMix[3], 0), cM13(band[13], 1, bandMix[3], 1),
      cS0(bandMix[0], 0, sumMix, 0), cS1(bandMix[1], 0, sumMix, 1),
      cS2(bandMix[2], 0, sumMix, 2), cS3(bandMix[3], 0, sumMix, 3),
      cOut(sumMix, 0, outDest, outPort),
      sounding_(false), velocity_(0.0f), currentNote_(-1),
      env_(nullptr), frame_(0), noteFrames_(0) {}

void VocoderVoice::begin() {
  glottis.begin(WAVEFORM_BANDLIMIT_SAWTOOTH);   // bandlimited: -85 dB vs -36
  glottis.frequencyModulation(VIBRATO_FM_OCTAVES);
  glottis.amplitude(0.0f);   // silent until a note arrives

  vibratoLFO.begin(WAVEFORM_SINE);
  vibratoLFO.frequency(VOICE_DEFS[0].vibratoHz);
  vibratoLFO.amplitude(VIBRATO_LFO_AMP);

  noise.amplitude(BREATH_SOURCE_AMP);
  excMix.gain(0, 1.0f);
  excMix.gain(1, 0.0f);

  for (int b = 0; b < VOC_BANDS; b++) {
    band[b].frequency(VOC_CENTRE[b]);
    band[b].resonance(VOC_Q);
    bandMix[mixerOf(b)].gain(channelOf(b), 0.0f);
  }
  for (int m = 0; m < 4; m++) sumMix.gain(m, 1.0f);
}

const VocEnvelope *VocoderVoice::findSyllable(const char *syllable) const {
  if (!syllable || !*syllable) return nullptr;
  for (int i = 0; i < ag_count; i++) {
    if (strcmp(ag_index[i].syllable, syllable) == 0) return &ag_index[i];
  }
  return nullptr;
}

void VocoderVoice::applyFrame(int frameIndex) {
  if (!env_) return;
  const uint8_t *f = ag_frames[env_->offset + frameIndex];
  for (int b = 0; b < VOC_BANDS; b++) {
    float g = f[b] / 255.0f * (GLOTTIS_AMP_BASE + GLOTTIS_AMP_SCALE * velocity_);
    // ALTERNATING POLARITY. Without the sign flip the bank ripples 9.3 dB
    // instead of 3.1 over 400 Hz-6 kHz. This is the explicit write-out the
    // spec calls for.
    bandMix[mixerOf(b)].gain(channelOf(b), (b & 1) ? -g : g);
  }
  float v = f[VOC_BANDS] / 255.0f;
  excMix.gain(0, v);                 // sawtooth
  excMix.gain(1, (1.0f - v) * 0.4f); // soft noise
}

void VocoderVoice::noteOn(int note, int velocity, const char *syllable,
                          float durationMs) {
  currentNote_ = note;
  velocity_ = velocity / 127.0f;
  glottis.frequency(midiToFreq((float)note));
  glottis.amplitude(1.0f);

  env_ = findSyllable(syllable);
  noteFrames_ = (int)(durationMs / VOC_FRAME_MS);
  frame_ = 0;
  frameTimer_ = 0;
  sounding_ = true;
  if (env_) applyFrame(0);
}

void VocoderVoice::noteOff() {
  // Rule 4: the note ends at exactly zero. A residual that held between notes
  // was audible as noise on the NEXT syllable's start.
  for (int b = 0; b < VOC_BANDS; b++) bandMix[mixerOf(b)].gain(channelOf(b), 0.0f);
  glottis.amplitude(0.0f);
  sounding_ = false;
  currentNote_ = -1;
  env_ = nullptr;
}

void VocoderVoice::allNotesOff() { noteOff(); }

void VocoderVoice::update() {
  if (!sounding_ || !env_) return;
  if (frameTimer_ < (unsigned)VOC_FRAME_MS) return;
  frameTimer_ = 0;

  frame_++;
  if (frame_ >= noteFrames_) { noteOff(); return; }

  // Time-stretch: consonant head and tail at natural speed, the vowel
  // steady-state stretched to fill the note. Stretching a consonant is what
  // makes synthetic singing sound drunk.
  int head = env_->nucleusStart;
  int tail = env_->frames - env_->nucleusEnd;
  int mid  = noteFrames_ - head - tail;
  int src;
  if (frame_ < head) {
    src = frame_;
  } else if (frame_ < head + mid && mid > 0) {
    int nucLen = env_->nucleusEnd - env_->nucleusStart;
    src = env_->nucleusStart + (nucLen > 0 ? ((frame_ - head) * nucLen) / mid : 0);
  } else {
    src = env_->nucleusEnd + (frame_ - head - mid);
  }
  if (src < 0) src = 0;
  if (src >= env_->frames) src = env_->frames - 1;
  applyFrame(src);
}
