/*
 * midi_io.h — the three MIDI inputs, one set of handlers.
 *
 * midiRead() must be called every pass through loop() and never blocks.
 */
#pragma once

void midiBegin();
void midiRead();
