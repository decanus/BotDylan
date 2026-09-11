# Bot Dylan

A desktop robot that sings by itself. There is no vocoder and no human vocal
input anywhere in the signal path: a band-limited sawtooth "glottis" runs
through three parallel bandpass filters tuned to vowel formants, with a
vibrato LFO on the oscillator's FM input, white noise for breath, and an ADSR
envelope on the output. MIDI notes drive the voice and the jaw servo from the
same events, so mouth sync is automatic and cannot drift. Three MIDI inputs
are live at once — USB device, DIN/TRS serial, and the Teensy 4.1's USB host
header — so a laptop, a Digitakt and an OP-1 can all sing through it without
repatching.

## Hardware

- **Teensy 4.1** (Arduino framework, Teensy Audio Library)
- Audio out via **MQS on pin 12** → PAM8403 amp → 4–8 Ω speaker
- **MG90S jaw servo** on pin 3, on its own 5 V supply
- **H11L1 optocoupler** for DIN/TRS MIDI in on pin 0 (RX1)

A Teensy 4.0 works too: set `ENABLE_USB_HOST 0` in `src/config.h` and
`board = teensy40` in `platformio.ini`. The 4.0 has no USB host header.

## Wiring

```
                          ┌──────────────────────────┐
                          │       TEENSY 4.1         │
                          │                          │
   MIDI DIN / TRS-A       │                          │
   ┌───────────┐          │                          │
   │  pin 4 ───┼─ 220R ─→ │ 1          H11L1       6 ├─→ 3.3V
   │  pin 5 ───┼────────→ │ 2  (optocoupler)       5 ├─→ GND
   └───────────┘          │ ▲                      4 ├─┬─→ pin 0 (RX1)
     1N4148 across 1–2    │ └ diode cathode to 1     │ │
     (cathode → pin 1)    └──────────────────────────┘ └─ 470R ─→ 3.3V
                                                            (pull-up)

   pin 12 (MQS) ──────→ PAM8403 "L" in ──→ ┌─────────┐
   GND          ──────→ PAM8403 GND        │ speaker │  4–8 Ω, 2–3 W
   VIN (5V)     ──────→ PAM8403 5V    ───→ └─────────┘

   pin 3        ──────→ MG90S jaw servo signal
   SEPARATE 5V  ──────→ MG90S V+          ← do not run the servo off the Teensy
   GND ───────────────→ MG90S GND         ← tie all grounds together

   USB device port  ──→ computer / DAW            (MIDI input 1)
   USB host header  ──→ OP-1 field, EP-133 USB    (MIDI input 3)
```

The DIN circuit is the standard PJRC optocoupler front end. An EP-133 K.O. II
reaches it over TRS Type A through a TRS-A-to-DIN adapter; a Digitakt goes in
over DIN directly.

## MIDI implementation chart

All three inputs are read every pass through `loop()` and land on the same
handlers, so the table below applies identically to each.

| Message | Range | Response |
|---|---|---|
| Note On | any channel (OMNI) | Monophonic, last-note priority. Sets pitch, opens the gate, opens the jaw. Velocity 0 is treated as Note Off. |
| Note Off | any channel | Falls back to the most recent held note (legato), or releases the envelope and closes the jaw if none. Stack depth 10. |
| Velocity | 1–127 | Loudness (`0.25 + 0.5 × vel`) and mouth openness (`0.35 + 0.65 × vel`). |
| CC 1 (mod wheel) | 0–127 | Vowel morph `oo → oh → ah → eh → ee`, interpolated between table entries. |
| CC 2 (breath) | 0–127 | Breath/air noise level, `0.02` to `0.27`. |
| CC 123 | — | All notes off: clears the stack, releases the envelope, closes the jaw. |
| Pitch bend | ±8192 | ±2 semitones. |
| Channel | — | OMNI; nothing is filtered by channel yet. |

Digitakt tip: p-lock CC1 per step and each note gets its own vowel — that is
as close to lyrics as the current firmware gets.

## Build and flash

```sh
pio run              # build
pio run -t upload    # build and flash
```

The Teensy normally reboots into the bootloader on its own; if it does not,
press the button on the board when the upload waits for it. To flash a
prebuilt hex without PlatformIO:

```sh
teensy_loader_cli --mcu=TEENSY41 -w -v .pio/build/teensy41/firmware.hex
```

`-D USB_MIDI_SERIAL` in `platformio.ini` is the equivalent of the Arduino
IDE's **Tools → USB Type → "Serial + MIDI"**. Without it there is no `usbMIDI`
object and MIDI input 1 will not compile.

> The build in this repo is verified clean. Flashing has **not** been
> confirmed on hardware from this checkout — no Teensy was attached when the
> refactor was done.

## Layout

```
src/
  main.cpp              wiring documentation, setup(), loop()
  config.h              pins, input flags, jaw trim, preset selection
  voice/
    audio_graph.h/.cpp  every Audio Library object + connection, one TU
    voice.h/.cpp        formant engine, note priority, jaw target
    vowel.h             struct Vowel
    presets/warm.h      the default vowel formant table
  face/
    jaw.h/.cpp          eased servo motion model
  midi_io/
    midi_io.h/.cpp      three inputs, one MIDI map
```

Audio Library objects have to be globals constructed at static-init time, so
they all live in `audio_graph.cpp` — one file, fixed construction order, graph
documented at the top. Add a node there and `extern` it in the header.

`face/` deliberately knows nothing about `voice/`; `main.cpp` passes the vowel
position into `jawUpdate()`. Eyes, when they arrive, become a sibling of
`jaw.*` with the same shape.

## Adding a voice preset

A preset is one header containing nothing but tuning data.

1. Copy `src/voice/presets/warm.h` to e.g. `src/voice/presets/choir.h` and
   rename the header comment.
2. Retune `VOWELS[]`. Each entry is `{ name, {F1,F2,F3} in Hz, {g1,g2,g3} }`.
   F1/F2 carry vowel identity; F3 mostly carries "who is singing". Gains are
   relative and get scaled by `0.9` before hitting the mixer.
3. Select it, either permanently in `src/config.h`:

   ```c
   #define VOICE_PRESET_HEADER "voice/presets/choir.h"
   ```

   or per-build in `platformio.ini`:

   ```ini
   build_flags = -D VOICE_PRESET_HEADER='"voice/presets/choir.h"'
   ```

The table is included by `voice.cpp` alone, so nothing else needs touching.

**Keep it at five vowels, ordered closed → open → closed.** The jaw's mouth
shaping hardcodes index 2 as the most open vowel and half-table as the span
(`jaw.cpp`). A preset of a different length still compiles and still sings,
but the mouth shaping will be wrong. See NOTES.md.
