/*
 * choir.h — the singers together.
 *
 * Owns what is shared: the vowel position (a choir sings the same syllable),
 * the breath level, and the mapping from MIDI channel to singer. Also owns
 * the jaw target, so that face/ stays independent of voice/.
 *
 * Channel allocation: MIDI channel 1 -> soprano, 2 -> alto, 3 -> bass, and
 * anything else -> soprano, so the robot still works as a plain mono
 * instrument when nothing is set up.
 */
#pragma once

void choirBegin();

// Control-rate tick (200 Hz): advances glide timing and per-voice smoothing.
void choirUpdate();

void choirNoteOn(int channel, int note, int velocity);
void choirNoteOff(int channel, int note);
void choirAllNotesOff();

void choirSetVowelCC(int value);
void choirSetBreathCC(int value);
void choirSetGlideCC(int value);         // latched, consumed by the next note-on
void choirSetVibratoRateCC(int value);
void choirSetPitchBend(int channel, int bend);

float choirVowelPos();
