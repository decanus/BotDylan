/*
 * midi_io.cpp — USB device, DIN/TRS serial, and USB host, all at once.
 *
 * The handlers below are deliberately thin: they own the MIDI *map* (which
 * CC does what, which channel to listen to) and nothing else. Everything they
 * do lands in voice/, so all three inputs behave identically.
 *
 * Per-channel filtering (e.g. one Digitakt track per robot) belongs at the
 * top of these handlers — the channel byte is already here for it.
 */

#include <Arduino.h>

#include "config.h"
#include "midi_io/midi_io.h"
#include "voice/choir.h"

#if ENABLE_DIN_MIDI
#include <MIDI.h>
MIDI_CREATE_INSTANCE(HardwareSerial, Serial1, DINMIDI);
#endif

#if ENABLE_USB_HOST
#include <USBHost_t36.h>
USBHost usbHost;
USBHub hub1(usbHost);
MIDIDevice_BigBuffer hostMIDI(usbHost);
#endif

// ===== SHARED MIDI HANDLERS (all three inputs land here) ==================
static void onNoteOn(byte ch, byte note, byte vel) {
  choirNoteOn(ch, note, vel);
}

static void onNoteOff(byte ch, byte note, byte vel) {
  choirNoteOff(ch, note);
}

static void onControlChange(byte ch, byte cc, byte val) {
  switch (cc) {
    case 1:                                         // mod wheel: vowel morph
      choirSetVowelCC(val);
      break;
    case 2:                                         // breath / air
      choirSetBreathCC(val);
      break;
    case 3:                                         // glide onset, per note
      choirSetGlideCC(val);
      break;
    case 4:                                         // vibrato rate
      choirSetVibratoRateCC(val);
      break;
    case 123:                                       // all notes off
      choirAllNotesOff();
      break;
  }
}

static void onPitchChange(byte ch, int bend) {
  choirSetPitchBend(ch, bend);
}

// ===== SETUP / READ ========================================================
void midiBegin() {
  // Input 1: USB device (computer/DAW)
  usbMIDI.setHandleNoteOn(onNoteOn);
  usbMIDI.setHandleNoteOff(onNoteOff);
  usbMIDI.setHandleControlChange(onControlChange);
  usbMIDI.setHandlePitchChange(onPitchChange);

#if ENABLE_DIN_MIDI
  // Input 2: DIN/TRS serial (Digitakt, EP-133)
  DINMIDI.begin(MIDI_CHANNEL_OMNI);
  DINMIDI.turnThruOff();
  DINMIDI.setHandleNoteOn(onNoteOn);
  DINMIDI.setHandleNoteOff(onNoteOff);
  DINMIDI.setHandleControlChange(onControlChange);
  DINMIDI.setHandlePitchBend([](byte ch, int bend) { onPitchChange(ch, bend); });
#endif

#if ENABLE_USB_HOST
  // Input 3: USB host (OP-1 field) — Teensy 4.1 host header
  usbHost.begin();
  hostMIDI.setHandleNoteOn(onNoteOn);
  hostMIDI.setHandleNoteOff(onNoteOff);
  hostMIDI.setHandleControlChange(onControlChange);
  hostMIDI.setHandlePitchChange(onPitchChange);
#endif
}

void midiRead() {
  usbMIDI.read();
#if ENABLE_DIN_MIDI
  DINMIDI.read();
#endif
#if ENABLE_USB_HOST
  usbHost.Task();
  hostMIDI.read();
#endif
}
