/*
 * audio_graph.h — handles on the Teensy Audio Library objects.
 *
 * The objects themselves and every AudioConnection between them are defined
 * in audio_graph.cpp, which is the ONLY place the graph is built. The Audio
 * Library requires these to be globals constructed at static-init time, and
 * keeping them in a single translation unit keeps their construction order
 * fixed and obvious.
 */
#pragma once

#include <Audio.h>

extern AudioSynthWaveform          vibratoLFO;
extern AudioSynthWaveformModulated glottis;
extern AudioSynthNoiseWhite        breath;
extern AudioMixer4                 sourceMix;
extern AudioFilterStateVariable    formant1;
extern AudioFilterStateVariable    formant2;
extern AudioFilterStateVariable    formant3;
extern AudioMixer4                 formantMix;
extern AudioEffectEnvelope         env;
extern AudioOutputMQS              audioOut;
