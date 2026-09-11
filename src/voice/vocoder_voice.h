/*
 * vocoder_voice.h — mode 2: the 14-band stored-envelope vocoder.
 *
 * A second voice alongside the three formant voices. Pronunciation lives in
 * band envelopes rather than in events: per note, 14 log-spaced bands from
 * 220 Hz to 5.6 kHz get a gain trajectory at 10 ms frames, and a voicing
 * trajectory crossfades the excitation between the bandlimited sawtooth and
 * soft noise.
 *
 * Two rules from the listening experiment are load-bearing here and must not
 * be "simplified":
 *
 *   The carrier must be BANDLIMITED. A naive saw measured -36 dB of aliasing,
 *   clearly audible; bandlimited measures -85. The Audio Library's
 *   WAVEFORM_BANDLIMIT_SAWTOOTH gives this for free.
 *
 *   The band sum must ALTERNATE POLARITY — band 0 positive, band 1 negative,
 *   and so on. Measured over 400 Hz-6 kHz at Q=4.5, an all-positive sum
 *   ripples 9.3 dB and an alternating one 3.1 dB. Unlike the bandlimiting,
 *   this one has to be written out explicitly, which is what the negative
 *   mixer gains below are doing.
 *
 * Envelope data is compiled to flash by tools/envelopes_to_header.py.
 */
#pragma once

#include <Audio.h>

#include "house_sound.h"
#include "voice/envelopes_amazing_grace.h"

const int VOC_BANDS = 14;

class VocoderVoice {
 public:
  VocoderVoice(AudioStream &outDest, uint8_t outPort);

  void begin();
  void noteOn(int note, int velocity, const char *syllable, float durationMs);
  void noteOff();
  void allNotesOff();

  // Control rate: advances the envelope one frame when 10 ms have elapsed.
  void update();

  bool sounding() const { return sounding_; }
  float velocity() const { return velocity_; }

  // --- audio nodes: construction order matters, do not reorder ---
  AudioSynthWaveformModulated glottis;
  AudioSynthWaveform          vibratoLFO;
  AudioSynthNoiseWhite        noise;
  AudioMixer4                 excMix;          // saw + noise crossfade
  AudioFilterStateVariable    band[VOC_BANDS];
  AudioMixer4                 bandMix[4];      // 4 + 4 + 4 + 2
  AudioMixer4                 sumMix;

  // --- connections: declared after the nodes, on purpose ---
  AudioConnection cLfo, cGlottis, cNoise;
  AudioConnection cB0,  cB1,  cB2,  cB3,  cB4,  cB5,  cB6;
  AudioConnection cB7,  cB8,  cB9,  cB10, cB11, cB12, cB13;
  AudioConnection cM0,  cM1,  cM2,  cM3,  cM4,  cM5,  cM6;
  AudioConnection cM7,  cM8,  cM9,  cM10, cM11, cM12, cM13;
  AudioConnection cS0, cS1, cS2, cS3, cOut;

 private:
  const VocEnvelope *findSyllable(const char *syllable) const;
  void applyFrame(int frameIndex);

  bool  sounding_;
  float velocity_;
  int   currentNote_;
  const VocEnvelope *env_;
  int   frame_;            // frame index within the note
  int   noteFrames_;       // how many frames this note lasts
  elapsedMillis frameTimer_;
};
