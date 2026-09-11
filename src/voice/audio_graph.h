/*
 * audio_graph.h — handles on the shared audio nodes and the singers.
 *
 * The Voice instances own their own nodes; what lives here is everything
 * they share. All of it is defined in audio_graph.cpp, which is the only
 * place the graph is built.
 */
#pragma once

#include <Audio.h>

#include "voice/voice.h"

extern AudioSynthNoiseWhite breath;      // one breath bed, shared by all
extern AudioMixer4          voiceMix;    // the choir summed
extern AudioOutputMQS       audioOut;

extern Voice *const VOICES[];            // VOICE_COUNT entries
