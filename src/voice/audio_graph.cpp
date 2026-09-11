/*
 * audio_graph.cpp — the signal path, and nothing else.
 *
 * Every Audio Library object and every connection lives here, at global
 * scope, in one translation unit. Add a node (a consonant noise burst, a
 * second formant bank) by declaring it here and extern'ing it in the header.
 */

#include "voice/audio_graph.h"

// ===== AUDIO GRAPH =========================================================
// vibrato LFO -> FM input of sawtooth "glottis"
// glottis + breath noise -> source mixer -> three parallel bandpass filters
// -> formant mixer -> envelope -> MQS output
AudioSynthWaveform          vibratoLFO;
AudioSynthWaveformModulated glottis;
AudioSynthNoiseWhite        breath;
AudioMixer4                 sourceMix;
AudioFilterStateVariable    formant1;
AudioFilterStateVariable    formant2;
AudioFilterStateVariable    formant3;
AudioMixer4                 formantMix;
AudioEffectEnvelope         env;
AudioOutputMQS              audioOut;

AudioConnection p1(vibratoLFO, 0, glottis, 0);
AudioConnection p2(glottis, 0, sourceMix, 0);
AudioConnection p3(breath,  0, sourceMix, 1);
AudioConnection p4(sourceMix, 0, formant1, 0);
AudioConnection p5(sourceMix, 0, formant2, 0);
AudioConnection p6(sourceMix, 0, formant3, 0);
AudioConnection p7(formant1, 1, formantMix, 0);   // port 1 = bandpass out
AudioConnection p8(formant2, 1, formantMix, 1);
AudioConnection p9(formant3, 1, formantMix, 2);
AudioConnection p10(formantMix, 0, env, 0);
AudioConnection p11(env, 0, audioOut, 0);
