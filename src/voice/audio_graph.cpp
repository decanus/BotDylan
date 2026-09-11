/*
 * audio_graph.cpp — the signal path, and nothing else.
 *
 * Per voice (built inside the Voice class, see voice.cpp):
 *   vibrato LFO -> FM input of sawtooth "glottis"
 *   glottis + shared breath noise -> source mixer
 *   -> three parallel bandpass filters -> formant mixer -> envelope
 *
 * Shared here:
 *   every voice's envelope -> voice mixer -> MQS output
 *
 * Everything is at global scope because the Audio Library requires static
 * storage, and in one translation unit so construction order is fixed.
 */

#include "voice/audio_graph.h"

AudioSynthNoiseWhite breath;
AudioMixer4          voiceMix;
AudioOutputMQS       audioOut;

AudioConnection cMixToOut(voiceMix, 0, audioOut, 0);

// Each singer takes the shared breath bed, the mixer, and its own port on it.
// Named instances rather than an array: Voice is non-copyable, and this keeps
// the port numbers visible next to the voice they belong to.
Voice voiceSoprano(VOICE_DEFS[0], breath, voiceMix, 0);
Voice voiceAlto   (VOICE_DEFS[1], breath, voiceMix, 1);
Voice voiceBass   (VOICE_DEFS[2], breath, voiceMix, 2);

// Mode 2 takes the mixer's fourth channel, so it sits alongside the choir
// rather than replacing it. Only one mode sounds at a time.
VocoderVoice vocoder(voiceMix, 3);

Voice *const VOICES[] = { &voiceSoprano, &voiceAlto, &voiceBass };
static_assert(sizeof(VOICES) / sizeof(VOICES[0]) == VOICE_COUNT,
              "VOICES[] must match VOICE_DEFS[]");
