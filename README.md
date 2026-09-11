# Bot Dylan

**Try it in a browser: [decanus.github.io/BotDylan](https://decanus.github.io/BotDylan/)** —
no install, no build. Click "Start audio", then pick a song.

A desktop robot that sings by itself, in three-part harmony. There is no
vocoder and no human vocal input anywhere in the signal path: each voice is a
band-limited sawtooth "glottis" through three parallel bandpass filters tuned
to vowel formants, with a vibrato LFO on the oscillator's FM input and an ADSR
envelope. Soprano, alto and bass share one vowel position — a choir sings the
same syllable — but differ in vibrato rate, detune and formant scale, which is
what makes the bass read as a bigger person rather than a transposed soprano.
Articulation is done entirely by formant motion, never by added noise. MIDI
notes drive the voices and the jaw servo from the same events, so mouth sync
is automatic. Three MIDI inputs are live at once — USB device, DIN/TRS serial,
and the Teensy 4.1's USB host header — so a laptop, a Digitakt and an OP-1 can
all sing through it without repatching.

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
handlers, so the table applies identically to each.

**Channel allocation** is one channel per voice. Anything outside 1–3 plays
the soprano, so the robot still works as a plain mono instrument out of the box.

| Channel | Voice | Vibrato | Detune | Formant scale | Mix |
|---|---|---|---|---|---|
| 1 | Soprano | 5.0 Hz | 0 ¢ | 1.00 | 0.42 |
| 2 | Alto | 4.6 Hz | +4 ¢ | 0.93 | 0.30 |
| 3 | Bass | 4.3 Hz | −3 ¢ | 0.82 | 0.34 |
| other | → Soprano | | | | |

| Message | Range | Response |
|---|---|---|
| Note On | per channel | Monophonic per voice, last-note priority. Velocity 0 is treated as Note Off. |
| Note Off | per channel | Falls back to the most recent held note on that voice (legato), or releases it. Stack depth 10 per voice. |
| Velocity | 1–127 | Loudness (`0.22 + 0.5 × vel`) and, on the soprano, mouth openness (`0.35 + 0.65 × vel`). |
| CC 1 | 0–127 | Vowel morph `oo → oh → ah → eh → ee`, shared by all three voices, smoothed over 35 ms. |
| CC 2 | 0–127 | Breath/air noise, `0.00`–`0.27`. **Default 0** — breath is off unless you ask for it. |
| CC 3 | 0 / 1–63 / 64–127 | Glide onset for the next note: none / `w` (starts at "oo") / `l` (starts just past "oh"). Latched, consumed by the next Note On, then cleared. |
| CC 4 | 0–127 | Vibrato rate, 2–9 Hz on the soprano; the other voices keep their ratio to it. |
| CC 123 | — | All notes off, on every voice. Closes the jaw and clears any latched glide. |
| Pitch bend | ±8192 | ±2 semitones, on the bent channel's voice only. |

The jaw follows the soprano. If only the alto or bass are sounding there is no
velocity to track, so the mouth holds at a neutral 0.45 rather than sitting
shut, and closes fully only once nothing is sounding.

Digitakt tip: p-lock CC1 per step and each note gets its own vowel; p-lock CC3
alongside it and each note gets its own articulation. That is as close to
lyrics as the firmware gets, and deliberately so — see NOTES.md on consonants.

## The live page

**Live at [decanus.github.io/BotDylan](https://decanus.github.io/BotDylan/)**,
republished on every push to `main` by `.github/workflows/pages.yml`.

If you fork this, there is one manual step before the first deploy works: go to
**Settings → Pages → Build and deployment → Source** and choose
**"GitHub Actions"**. Until that is set the build job succeeds and the deploy
job fails with `HttpError: Not Found`.

How it is built:

- `index.html` is a **copy** of `tools/simulator.html`, never a build product.
  That is what keeps the page working from `file://` with no build step, and
  keeps a second copy of the simulator out of the repo.
- The sample MIDI files are **generated in CI**, not committed. They derive
  entirely from `songs/*.json`, and a committed derivative is exactly the kind
  of duplicate the parity rule exists to prevent. `.gitignore` covers `*.mid`.
- Both checks gate the deploy: `check_song_parity.js` and `verify_midi.py`. A
  drifted song or a malformed MIDI file never reaches the public page.

The page's "Sample MIDI files" links resolve only once published. Running the
simulator locally they will 404 — generate them yourself with
`python3 tools/song_to_midi.py`.

## Face specification

The expressive layer is **part of the spec, not decoration** — it carries the
robot's character, and a rebuild that drops it has lost something real. See
NOTES.md on how the eyebrows went missing once already.

**Source of truth: `tools/simulator.html`.** These values live there and are
mirrored into `src/face/` as the hardware catches up.

| Element | Behaviour | Parameters |
|---|---|---|
| Jaw | Eases toward a target, never snaps. Opens fast, closes lazily — a syllable starts abruptly and the mouth relaxes shut. Wider on louder notes, and narrowed by closed vowels. | open 0.28 / close 0.11 per control tick; openness `0.35 + 0.65 × velocity`; vowel narrowing up to 35% at the table's ends |
| Gaze | **Saccades**: the pupils hold, then flick somewhere new, horizontally and vertically. A slow drift runs underneath so a held gaze still breathes. Looks around more often while singing. | ±4.0 × ±2.2 units; hold 0.6–2.6 s (×0.6 while singing); flick eased 0.35; drift ±0.45 over 5.2 s |
| Blink | Random interval, shuts faster than it opens, occasionally doubles. Runs always, including at rest. | every 1.8–6.2 s; 140 ms, 40% closing / 60% opening; 18% chance of a second blink 90 ms later |
| Eyebrows | Lift while anything is singing and further on a harder note, plus an independent slow wander per side so the two are rarely level. Sometimes one lifts alone. | 4 units at velocity 0, 8 at 127; wander ±1.1 per side, 30% chance of a +1.4 single-brow raise; eased 0.08/frame; total capped at 8.5 so the brow stays inside the head |

Two rules run through all of it: **nothing snaps**, and **nothing repeats**.
Gaze, blinks and brow wander are all driven by random timers rather than a
clock, because a face that repeats exactly reads as a machine — the pupils used
to track a sine wave and looked like a searchlight. The jaw and the brow lift
stay tied to the notes; everything else is deliberately irregular.

Eyes and blinking exist in the simulator only for now. The firmware has jaw and
brow; when the head gets eyes (a second servo, or the round displays on the
roadmap) this table is the spec to port.

## The parity rule

`tools/simulator.html` is a standalone, dependency-free browser twin of the
voice, and it is **the reference implementation of the house sound**. Open it
straight from disk; it needs no server and no build step.

> **Any tuning change must be made in both `src/` and `tools/simulator.html`,
> in the same commit.**

The firmware keeps every tuned constant in one file, `src/house_sound.h`, to
make that rule followable rather than aspirational. Two checks back it up:

```sh
c++ -std=c++17 -I src tools/parity_check.cpp -o /tmp/parity && /tmp/parity
node tools/check_song_parity.js
python3 tools/song_to_midi.py --out /tmp/midi && python3 tools/verify_midi.py /tmp/midi/*.mid
python3 tools/roundtrip_test.py
```

Vocoder mode (experimental, branch `mode/vocoder`) has its own, which need the
venv from `tools/requirements-vocoder.txt`:

```sh
.venv-vocoder/bin/python tools/vocoder_render.py songs/amazing_grace.json --verify
.venv-vocoder/bin/python tools/vocoder_check.py
```

The first compiles the firmware's vowel math on the host — `formant_math.h` is
deliberately free of any Audio Library dependency — and diffs it against the
original sketch's `applyVowel()` across a 40001-step sweep, bit for bit. That
is how a refactor proves it left the timbre alone. The second checks the songs
against their copies inside the simulator.

Where the two implementations genuinely disagreed, the resolution is recorded
in NOTES.md: the simulator won on motion and levels, the firmware won on the
envelope and the vibrato model, where the browser version was an approximation
rather than a decision.

### The rule is different for vocoder mode

**For mode 2 the simulator is NOT the reference.** The WAV renders from
`tools/vocoder_render.py` are.

Mode 2 schedules 14 band envelopes at 10 ms frames in real time, and real-time
parameter scheduling in a browser — especially on mobile — introduces artifacts
the offline render does not have. The page is labelled a preview for that
reason. It is there to let you play the engine interactively, not to judge it.

The reference is instead pinned by a byte-for-byte test: `vocoder_render.py
--verify` reproduces `tools/vocoder_reference.py`'s output exactly, hash for
hash, inside the pinned environment. The simulator's mode 2 is cross-checked
against the Python engine rather than trusted — the two agree on band gains to
5e-07, which is float rounding.

Mode 1's audio engine is untouched by any of this, and verified so: all seven
of its functions and all four of its constant tables are byte-identical before
and after mode 2 was added.

## Songs

`songs/*.json` holds one object per note: `sop`/`alto`/`bass` (null for a
resting voice), `beats`, `vowelCC`, `syllable`, `velocity`, `glide`.

The simulator keeps its own embedded copies, because it has to run from
`file://` where fetching local JSON is blocked. **So every song exists twice.**
`node tools/check_song_parity.js` is what keeps the two honest; run it after
editing either.

Export to standard MIDI for the Digitakt or a DAW:

```sh
python3 tools/song_to_midi.py                     # every song
python3 tools/song_to_midi.py songs/ode_to_joy.json --out /tmp
```

Standard library only — nothing to install. Notes land on channels 1/2/3 per
voice, with CC1 and CC3 written just before each note-on so the firmware's
glide latch picks them up.

`tools/verify_midi.py` reads the output back with an independent parser — not
the writer's code, so a writer bug cannot hide — and checks the header, chunk
lengths, tempo against `quarterMs`, note-on/note-off balance, per-channel note
counts against the JSON, and that CC1 and CC3 precede every note-on.

## Teaching the robot songs

Four ways in. All of them end at `songs/*.json`, and all of them end at your
ear: **transcription output always gets a human listen before it enters
`songs/`.** The pipeline transcribes; you sign off on repertoire.

None of these tools fetch anything. They read local files you provide, and
that is a standing rule, not an implementation detail.

**1. A public-domain MIDI file**

```sh
python3 tools/midi_to_song.py hymn.mid -o songs/hymn.json
python3 tools/song_to_wav.py songs/hymn.json -o /tmp/hymn.wav   # listen
```

Channels 1/2/3 map straight to soprano/alto/bass. Anything else, the melody
track is taken as the soprano — `--track N` to override, `--unit quarter` if
the default eighth grid is too fine.

**2. Licensed MIDI, or sheet music entered in a DAW**

Same command. Export from the DAW with the voices on channels 1/2/3 and it
comes across intact, vowels and all.

**3. Sing or hum it**

```sh
python3 tools/audio_to_song.py hum.wav -o songs/new.json --bpm 96 --key Am
```

The default transcriber needs nothing installed and handles a clean
monophonic hum — a phone memo is the intended input. For a noisy or
polyphonic recording, install the extras and use the better models:

```sh
python3.12 -m venv .venv-audio
.venv-audio/bin/pip install -r tools/requirements-audio.txt
.venv-audio/bin/python tools/audio_to_song.py take.mp3 -o songs/new.json \
    --separate --transcriber basicpitch
```

Those extras pull in PyTorch — a couple of GB — and as of writing neither
supports Python 3.14, hence the explicit `python3.12`. Both the cleaned `.mid`
and the final `.json` are written, so a transcription that needs a human fix
can be opened in a DAW.

**4. Play it live**

Open the simulator, set the record tempo, hit **Record**, play, hit stop. It
downloads a song JSON. Works with a MIDI controller or the computer keys.

**Then the words**

```sh
python3 tools/lyrics_to_vowels.py songs/new.json \
    "A-ma-zing grace how sweet the sound" --compare   # dry run
python3 tools/lyrics_to_vowels.py songs/new.json "..." -o songs/new.json
```

Whitespace splits words, hyphens split syllables. A syllable/note count
mismatch is a hard error with a side-by-side alignment table — it will never
quietly truncate your lyric.

**And the checks**

```sh
python3 tools/roundtrip_test.py        # songs survive JSON -> MIDI -> JSON
python3 tools/audio_pipeline_test.py   # and survive being rendered and re-heard
node tools/check_song_parity.js        # songs match the simulator's copies
```

Adding a song to `songs/` means adding it to the simulator too, in the same
commit. That is the parity rule, and `check_song_parity.js` enforces it.

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

`ENABLE_PERF_REPORT` in `src/config.h` prints audio CPU and memory headroom
over USB serial every two seconds, guarded so a disconnected host can never
block the control loop. Use it to trim `AUDIO_MEMORY_BLOCKS`, which is
currently a generous guess at 60 rather than a measurement.

> The build in this repo is verified clean and the host-side parity checks
> pass. Nothing here has been **run on hardware** — no Teensy has been attached
> to this checkout, so audio, servo motion and the audio budget are all
> unconfirmed in the real world.

## Layout

```
src/
  main.cpp              wiring documentation, setup(), loop()
  config.h              pins, input flags, jaw trim, preset selection
  house_sound.h         EVERY tuned constant — mirrored in the simulator
  voice/
    voice.{h,cpp}       one singer: synthesis + last-note priority
    choir.{h,cpp}       the singers together: shared vowel, glide, channels
    audio_graph.{h,cpp} shared nodes and the three Voice instances
    formant_math.h      the vowel morph, host-compilable, no Audio Library
    vowel.h             struct Vowel
    presets/warm.h      the default vowel formant table
  face/
    jaw.{h,cpp}         eased servo motion model
  midi_io/
    midi_io.{h,cpp}     three inputs, one MIDI map
songs/                  song JSON (see above)
tools/
  simulator.html        the reference implementation
  parity_check.cpp      host check: vowel math vs. the original sketch
  check_song_parity.js  host check: songs vs. the simulator's copies
  song_to_midi.py       song JSON -> standard MIDI file
```

A `Voice` owns its audio nodes as members. The Audio Library needs
`AudioStream` objects in static storage, which a global instance satisfies;
`AudioConnection` members are declared *after* the nodes they join, because
members are constructed in declaration order. The shared nodes and the three
singers all live in `audio_graph.cpp`, so construction order stays fixed and
the graph is documented in one place.

`face/` deliberately knows nothing about `voice/`: `main.cpp` passes the vowel
position into `jawUpdate()`, and `choir.cpp` owns the jaw target. Eyes, when
they arrive, become a sibling of `jaw.*` with the same shape.

**Eyebrows are a first-class face feature**, not a simulator flourish. The
physical head should carry a brow actuator — one micro servo driving both brows
through a linkage is fine — or a deliberately angled static brow if it stays
passive. `src/face/` reserves a PWM pin and a `browTarget` in the motion model
now, mirroring the jaw, so the firmware side is ready before the hardware is.

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

The table is reached through `formant_math.h`, so nothing else needs touching.
All three voices use the same table; what makes them different is the per-voice
`formantScale` in `house_sound.h`, not a separate preset each.

Mirror the new table into `VOWELS` in `tools/simulator.html` in the same
commit — the parity rule covers presets too — and re-run the host check to
confirm the morph still behaves:

```sh
c++ -std=c++17 -I src tools/parity_check.cpp -o /tmp/parity && /tmp/parity
```

**Keep it at five vowels, ordered closed → open → closed.** Two things assume
it: the jaw's mouth shaping hardcodes index 2 as the most open vowel and
half-table as the span (`jaw.cpp`), and the glide start positions (0.0 for `w`,
1.2 for `l`) are points on this particular table. A preset of a different
length still compiles and still sings, but the mouth shaping and the glides
will both be wrong. See NOTES.md.
