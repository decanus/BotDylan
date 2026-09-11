/*
 * voice.h — the singing voice: formant engine plus note priority.
 *
 * Owns the note stack (monophonic, last-note priority, legato) as well as
 * the synthesis, and drives the jaw target as a side effect of note events
 * so that mouth sync can never fall out of step with the sound.
 *
 * The CC-valued setters take raw 0..127 MIDI values on purpose: the vowel
 * table size stays private to voice.cpp, and the scaling arithmetic stays in
 * one place. midi_io/ decides WHICH CC does what; voice/ decides what it does.
 */
#pragma once

#include <Arduino.h>

void voiceBegin();

// Note events. velocity 0 is treated as a note-off, per MIDI convention.
void voiceNoteOn(int note, int velocity);
void voiceNoteOff(int note);
void voiceAllNotesOff();

// Continuous controllers, raw MIDI ranges.
void voiceSetVowelCC(int value);    // 0..127, morphs oo -> oh -> ah -> eh -> ee
void voiceSetBreathCC(int value);   // 0..127, breath/air amount
void voiceSetPitchBend(int bend);   // -8192..8191, +/- 2 semitones

// Fractional index into the vowel table; the jaw uses it for mouth shape.
float voiceVowelPos();
