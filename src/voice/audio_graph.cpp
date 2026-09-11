/*
 * audio_graph.cpp — the signal path, and nothing else.
 *
 * Per voice (built inside the Voice class, see voice.cpp):
 *   vibrato LFO -> FM input of sawtooth "glottis"
 *   glottis + shared breath noise -> source mixer
 *   -> three parallel bandpass filters -> formant mixer -> envelope
 *
 * Shared here:
 *   every voice's envelope -> MQS output
 *
 * Everything is at global scope because the Audio Library requires static
 * storage, and in one translation unit so construction order is fixed.
 */

#include "voice/audio_graph.h"

AudioSynthNoiseWhite breath;
AudioOutputMQS       audioOut;

// One singer for now. Each takes the shared breath bed, and the output node
// plus the port it should land on.
Voice voiceSoprano(VOICE_DEFS[0], breath, audioOut, 0);

Voice *const VOICES[] = { &voiceSoprano };
static_assert(sizeof(VOICES) / sizeof(VOICES[0]) == VOICE_COUNT,
              "VOICES[] must match VOICE_DEFS[]");
