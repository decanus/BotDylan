/*
 * BOT DYLAN — self-singing formant synth for Teensy 4.1 (or 4.0)
 * ===============================================================
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

/*
 * MODULE MAP (see README.md)
 * --------------------------
 *   config.h            pins, input flags, which voice preset is compiled in
 *   voice/audio_graph   the Audio Library objects + connections, all in one TU
 *   voice/voice         one singer: formant engine + note priority
 *   voice/choir         the singers together: shared vowel, channel map
 *   voice/presets/      vowel formant tables — the tuning data
 *   face/jaw            eased servo motion model
 *   midi_io/            the three inputs + the MIDI map
 *
 * Under PlatformIO the Arduino IDE's Tools > USB Type > "Serial + MIDI" is
 * set by -D USB_MIDI_SERIAL in platformio.ini.
 */

#include <Arduino.h>
#include <Audio.h>   // AudioProcessorUsage / AudioMemoryUsage

#include "config.h"
#include "face/jaw.h"
#include "house_sound.h"
#include "midi_io/midi_io.h"
#include "voice/choir.h"

elapsedMillis controlTimer;
#if ENABLE_PERF_REPORT
elapsedMillis perfTimer;
#endif

// ===== SETUP / LOOP ========================================================
void setup() {
#if ENABLE_PERF_REPORT
  Serial.begin(115200);
#endif
  choirBegin();   // audio memory, then every singer's nodes
  jawBegin();     // servo to its closed position
  midiBegin();    // USB device, DIN/TRS serial, USB host
}

void loop() {
  // Every pass, and nothing in here blocks.
  midiRead();

  // 200 Hz control rate: ease jaw toward target; vowel affects mouth shape
  if (controlTimer >= CONTROL_INTERVAL_MS) {
    controlTimer = 0;
    jawUpdate(choirVowelPos());
  }

#if ENABLE_PERF_REPORT
  // Guarded by `if (Serial)` so a disconnected host can never block the loop.
  if (perfTimer >= 2000) {
    perfTimer = 0;
    if (Serial) {
      // Serial.print rather than printf: printf drags in about 25 kB of
      // formatting machinery, for one diagnostic line. Tenths by hand.
      int cpu    = (int)(AudioProcessorUsage() * 10.0f);
      int cpuMax = (int)(AudioProcessorUsageMax() * 10.0f);
      Serial.print("audio cpu ");
      Serial.print(cpu / 10);    Serial.print('.'); Serial.print(cpu % 10);
      Serial.print("% (max ");
      Serial.print(cpuMax / 10); Serial.print('.'); Serial.print(cpuMax % 10);
      Serial.print("%)  mem ");
      Serial.print(AudioMemoryUsage());
      Serial.print(" (max ");
      Serial.print(AudioMemoryUsageMax());
      Serial.print(" of ");
      Serial.print(AUDIO_MEMORY_BLOCKS);
      Serial.println(")");
    }
  }
#endif
}
