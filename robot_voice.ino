/*
 * ROBOT VOICE — self-singing formant synth for Teensy 4.1 (or 4.0)
 * =================================================================
 * A MIDI-controlled singing voice, no vocoder, no human vocal input.
 * The same MIDI notes that make the sound also drive the jaw servo,
 * so mouth sync is automatic and perfect.
 *
 * THREE MIDI INPUTS, all active simultaneously:
 *   1. USB device  — plug Teensy into a computer/DAW (USB Type must be
 *                    set to "Serial + MIDI" in Arduino Tools menu)
 *   2. DIN/TRS serial — Digitakt DIN out, or EP-133 K.O. II TRS out
 *                    (Type A) via TRS-A-to-DIN adapter, into pin 0 (RX1)
 *                    through an optocoupler (circuit below)
 *   3. USB host   — Teensy 4.1 only: OP-1 field (or EP-133 USB) plugs
 *                    straight into the 4.1's USB host header
 *
 * DIN MIDI INPUT CIRCUIT (H11L1 optocoupler — the standard PJRC circuit)
 * ----------------------------------------------------------------------
 *   DIN pin 4 --- 220R --- H11L1 pin 1 (anode)
 *   DIN pin 5 ------------ H11L1 pin 2 (cathode)
 *   1N4148 diode across pins 1-2 (cathode of diode to pin 1)
 *   H11L1 pin 6 (Vcc) -> 3.3V     H11L1 pin 5 (GND) -> GND
 *   H11L1 pin 4 (Vo)  -> Teensy pin 0 (RX1), with 470R pull-up to 3.3V
 *
 * AUDIO + SERVO WIRING
 * --------------------
 * Audio out : MQS pin 12 -> PAM8403 amp "L" in, amp GND -> GND,
 *             amp 5V -> VIN. Amp out -> 4-8 ohm 2-3W speaker.
 * Jaw servo : signal -> pin 3, SEPARATE 5V supply, grounds tied together.
 *
 * PLAYING IT
 * ----------
 * - MIDI notes (monophonic, last-note priority, legato): pitch + gate
 * - Velocity: loudness + mouth openness
 * - CC1 (mod wheel): vowel morph OO -> OH -> AH -> EH -> EE
 *     Digitakt tip: p-lock CC1 per step = a vowel per note ("lyrics")
 * - CC2: breath/air amount
 * - Pitch bend: +/- 2 semitones for scoops and falls
 *
 * Libraries (all bundled with Teensyduino): Audio, PWMServo, MIDI,
 * USBHost_t36.
 */

#include <Audio.h>
#include <PWMServo.h>

// ===== INPUT CONFIG ========================================================
#define ENABLE_DIN_MIDI 1   // Digitakt / EP-133 via optocoupler on RX1
#define ENABLE_USB_HOST 1   // Teensy 4.1 host port (OP-1 field) — set 0 on 4.0

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

// ===== VOWEL FORMANT TABLE =================================================
// F1/F2/F3 center frequencies (Hz) + per-formant gains. CC1 morphs
// left-to-right through this list. Retune freely — this is the accent.
struct Vowel {
  const char *name;
  float f[3];
  float g[3];
};

const Vowel VOWELS[] = {
  { "oo", { 300,  870, 2240 }, { 1.00, 0.35, 0.12 } },
  { "oh", { 570,  840, 2410 }, { 1.00, 0.45, 0.15 } },
  { "ah", { 730, 1090, 2440 }, { 1.00, 0.60, 0.20 } },
  { "eh", { 530, 1840, 2480 }, { 1.00, 0.50, 0.22 } },
  { "ee", { 270, 2290, 3010 }, { 1.00, 0.30, 0.28 } },
};
const int NUM_VOWELS = sizeof(VOWELS) / sizeof(VOWELS[0]);

// ===== STATE ===============================================================
PWMServo jawServo;
const int JAW_PIN        = 3;
const int JAW_CLOSED_DEG = 12;   // trim these two to your linkage
const int JAW_OPEN_DEG   = 68;

float vowelPos     = 2.0f;       // fractional index into VOWELS; start "ah"
float breathLevel  = 0.06f;
float bendSemis    = 0.0f;
int   currentNote  = -1;
float noteVelocity = 0.0f;

int noteStack[10];               // last-note priority / legato
int noteStackLen = 0;

float jawActual = 0.0f;          // 0 closed .. 1 open
float jawTarget = 0.0f;

elapsedMillis controlTimer;

// ===== VOICE CORE ==========================================================
float midiToFreq(float note) {
  return 440.0f * powf(2.0f, (note - 69.0f) / 12.0f);
}

void applyVowel() {
  float pos = constrain(vowelPos, 0.0f, (float)(NUM_VOWELS - 1));
  int   i   = (int)pos;
  int   j   = min(i + 1, NUM_VOWELS - 1);
  float t   = pos - i;

  for (int k = 0; k < 3; k++) {
    // Geometric interpolation of frequencies sounds smoother than linear
    float freq = VOWELS[i].f[k] * powf(VOWELS[j].f[k] / VOWELS[i].f[k], t);
    float gain = VOWELS[i].g[k] + (VOWELS[j].g[k] - VOWELS[i].g[k]) * t;
    switch (k) {
      case 0: formant1.frequency(freq); formantMix.gain(0, gain * 0.9f); break;
      case 1: formant2.frequency(freq); formantMix.gain(1, gain * 0.9f); break;
      case 2: formant3.frequency(freq); formantMix.gain(2, gain * 0.9f); break;
    }
  }
}

void updatePitch() {
  if (currentNote >= 0) {
    glottis.frequency(midiToFreq((float)currentNote + bendSemis));
  }
}

void startNote(int note, int velocity) {
  currentNote  = note;
  noteVelocity = velocity / 127.0f;
  updatePitch();
  glottis.amplitude(0.25f + 0.5f * noteVelocity);
  env.noteOn();
  jawTarget = 0.35f + 0.65f * noteVelocity;
}

void releaseOrFall() {
  if (noteStackLen > 0) {
    currentNote = noteStack[--noteStackLen];   // legato fall-back
    updatePitch();
  } else {
    env.noteOff();
    currentNote = -1;
    jawTarget = 0.0f;
  }
}

// ===== SHARED MIDI HANDLERS (all three inputs land here) ==================
void onNoteOn(byte ch, byte note, byte vel) {
  if (vel == 0) { onNoteOff(ch, note, 0); return; }
  if (currentNote >= 0 && noteStackLen < 10) {
    noteStack[noteStackLen++] = currentNote;
  }
  startNote(note, vel);
}

void onNoteOff(byte ch, byte note, byte vel) {
  for (int i = 0; i < noteStackLen; i++) {          // held background note?
    if (noteStack[i] == note) {
      for (int j = i; j < noteStackLen - 1; j++) noteStack[j] = noteStack[j + 1];
      noteStackLen--;
      return;
    }
  }
  if (note == currentNote) releaseOrFall();
}

void onControlChange(byte ch, byte cc, byte val) {
  switch (cc) {
    case 1:
      vowelPos = (val / 127.0f) * (NUM_VOWELS - 1);
      applyVowel();
      break;
    case 2:
      breathLevel = 0.02f + (val / 127.0f) * 0.25f;
      sourceMix.gain(1, breathLevel);
      break;
    case 123:                                       // all notes off
      noteStackLen = 0;
      env.noteOff();
      currentNote = -1;
      jawTarget = 0.0f;
      break;
  }
}

void onPitchChange(byte ch, int bend) {
  bendSemis = (bend / 8192.0f) * 2.0f;
  updatePitch();
}

// ===== SETUP / LOOP ========================================================
void setup() {
  AudioMemory(24);

  glottis.begin(WAVEFORM_BANDLIMIT_SAWTOOTH);
  glottis.frequencyModulation(0.12f);   // vibrato depth
  glottis.amplitude(0.0f);

  vibratoLFO.begin(WAVEFORM_SINE);
  vibratoLFO.frequency(5.2f);
  vibratoLFO.amplitude(0.35f);

  breath.amplitude(1.0f);
  sourceMix.gain(0, 0.85f);
  sourceMix.gain(1, breathLevel);

  formant1.resonance(4.0f);
  formant2.resonance(5.0f);
  formant3.resonance(5.0f);
  applyVowel();

  env.attack(45);
  env.decay(120);
  env.sustain(0.85f);
  env.release(260);

  jawServo.attach(JAW_PIN);
  jawServo.write(JAW_CLOSED_DEG);

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

void loop() {
  usbMIDI.read();
#if ENABLE_DIN_MIDI
  DINMIDI.read();
#endif
#if ENABLE_USB_HOST
  usbHost.Task();
  hostMIDI.read();
#endif

  // 200 Hz control rate: ease jaw toward target; vowel affects mouth shape
  if (controlTimer >= 5) {
    controlTimer = 0;

    float vowelOpenness = 1.0f - 0.35f * fabsf(vowelPos - 2.0f) / 2.0f;
    float target = jawTarget * vowelOpenness;

    float rate = (target > jawActual) ? 0.30f : 0.12f;   // fast open, slow close
    jawActual += (target - jawActual) * rate;

    int deg = JAW_CLOSED_DEG + (int)((JAW_OPEN_DEG - JAW_CLOSED_DEG) * jawActual);
    jawServo.write(deg);
  }
}
