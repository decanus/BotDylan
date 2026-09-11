# Bot Dylan — mechanical design spec (v1)

Requirements for the printed and fabricated parts, derived from the firmware, the face spec, and the
reference build. CAD source of truth: `hardware/botdylan.scad` (parametric OpenSCAD, once started).

## Design intent

**An open frame that shows its working.** Two rails, a top bar and a base plate; a head block carrying
two large eyeballs in cowls; a hinged jaw plate; brow arms above the head; and a deck underneath
holding the Teensy, the amp, the speaker and the wiring loom in plain sight. The electronics are not
hidden — they are the point. Nothing about this is a sealed shell with a removable back panel.

The face still has to read clearly on camera at arm's length, so the eyes stay oversized and the jaw
stays visibly hinged. Everything else is structure.

## Proportions (from the reference build)

`tools/simulator.html` draws the machine as it will be built, in a 200 × 250 viewBox. **The drawing is
proportional, not dimensioned** — it was drawn from the reference build, not measured off it — so the
table below gives drawing units as the primary figure and a provisional millimetre column beside it.

The mm column is anchored on **one** part: the speaker, drawn as a ⌀48-unit circle and assumed to be a
50 mm driver, giving **≈1.04 mm/unit**. Re-anchor the moment a real speaker is in hand, and keep the
factor as a single OpenSCAD variable so everything rescales from that one number.

| Feature                  | Drawing (units)        | Provisional (mm) | Notes                                       |
|--------------------------|------------------------|------------------|---------------------------------------------|
| Frame, outer             | 172 w × 209 h          | 179 × 218        | Base plate is the widest part                |
| Rails                    | 7 wide, 206 tall       | 7 × 214          | Two uprights, x 22 and x 171                 |
| Top bar                  | 156 × 7                | 162 × 7          | Ties the rails; brow arms clear it           |
| Base plate / deck        | 172 × 11               | 179 × 11         | Carries everything electronic                |
| Head block               | 136 × 62, r 6          | 142 × 65         | The only part that reads as a "head"         |
| Eyeball                  | ⌀48, centres 64 apart  | ⌀50, 67 apart    | Printed spheres, the whole ball turns        |
| Eye span (outer)         | 112 of 136             | 117              | **82% of the head block** — eyes dominate    |
| Pupil                    | ⌀20                    | ⌀21              | 42% of the eyeball                           |
| Cowl                     | 10 deep over the eye   | 10               | Hood over the top of each ball               |
| Brow arm                 | 48 long, 4 thick       | 50 × 4           | Above the head block, ends at y 30           |
| Brow travel              | 4 → 8.5 max            | 4 → 9            | Lift + wander; capped so it stays off the bar |
| Jaw plate                | 68 × 17, r 3           | 71 × 18          | Hinged; drops to open                        |
| Jaw drop                 | 17                     | **18**           | `RIG.jawDrop` — full travel                  |
| Mouth cavity             | 60 × 26                | 62 × 27          | Revealed behind the jaw plate                |
| Neck post                | 16 × 30                | 17 × 31          | Head block down to the deck                  |
| Speaker                  | ⌀48                    | ⌀50              | **The scale anchor**                         |

Two things worth noticing in that table. The eyes span **82% of the head block**, which is the single
strongest thing about the face — a conventional "expressive robot" target is somewhere above half the
face width, and this clears that comfortably. And the jaw plate and the mouth cavity agree by
construction: the cavity is a real 60 × 26 opening that the plate uncovers, not a stylised shape drawn
independently of the mechanism, so there is no gap between what the drawing shows and what the hinge
does.

## What must fit on the deck (buy-list components, measure before modeling)

The deck is visible from the front, so component placement is an aesthetic decision as much as a
packaging one. The reference build puts the speaker left and the board right.

| Component            | Approx. envelope (mm)    | Mounting notes                                   |
|----------------------|--------------------------|--------------------------------------------------|
| Teensy 4.1           | 61 × 18 × 10 (with pins) | On the deck board; USB port reachable from outside |
| PAM8403 amp board    | ~21 × 18 × 5             | Beside the Teensy on the same board               |
| Speaker 2–3 W        | 40–57 mm dia             | Deck left, facing forward, in a printed baffle ring |
| MG90S servo × 3      | 23 × 12.2 × 29 each      | Jaw, brows, lids — see below                      |
| DIN-5 panel socket   | ~16 mm panel hole        | Rear of the deck                                  |
| Perfboard (DIN opto) | ~30 × 20                 | Near the DIN socket                               |
| Servo 5 V supply     | external                 | Rear cable entry with strain relief               |

The servo supply is separate from the Teensy (see the wiring diagram in the README), so the deck needs
room for two power paths and a common ground tie, not one.

Rule: model every component as a placeholder block in CAD first and confirm fit plus wire-routing
volume (~20% spare) before shaping anything.

## Mechanisms

### Jaw (built into the reference)
- Hinged jaw plate on a horizontal pivot behind the mouth line; 3 mm rod or printed pins.
- Driven by one MG90S. The firmware sweeps **`JAW_CLOSED_DEG` 12° → `JAW_OPEN_DEG` 68°, i.e. 56° of
  servo travel** (`src/config.h`); size the horn and pushrod so that sweep produces the **18 mm** drop
  in the table.
- Both constants are marked "trim these two to your linkage" — the linkage does not have to hit 56°
  exactly, but the closer it is to the full sweep, the finer the resolution.
- Fast-open/slow-close comes from firmware. The mechanism needs low friction and zero slop, and the
  servo must be re-centrable and the horn re-indexable without disassembly.

### Eyebrows
- Two brow arms above the head block, on one MG90S through a shared linkage.
- Travel is **small and inverted**: `BROW_DOWN_DEG` 80° → `BROW_UP_DEG` 62°, so raised is the *lower*
  servo angle and the whole expressive range is **18°**. Get the linkage direction right in CAD — a
  mirrored bell-crank turns every raised brow into a frown, and the firmware constants are trim
  values, not a fix for inverted geometry.
- The simulator gives each brow an independent wander and caps the total at 8.5 units so the arm stays
  off the frame's top bar. **The mechanism must respect that ceiling physically too** — a hard stop,
  not a software limit, or a mis-trimmed servo drives the arm into the bar.
- One servo drives both, so the per-side asymmetry in the simulator is currently expressive licence
  the hardware cannot reproduce. Either accept synchronised brows on the real bot, or budget a fourth
  servo. Decide before cutting the linkage.

### Eyelids (must-have — the robot blinks)
Blinking is the cheapest thing a face can do to look alive while it is doing nothing else, and it is
the only motion that survives silence. `src/face/blink.cpp` owns its own timer; nothing sets a target.

- The eyeballs are **printed spheres in cowls**, which is what makes a lid straightforward: the lid is
  a **shell riding on the ball**, rotating about the ball's own centre. Stowed, it hides inside the
  cowl; shut, it has swept the aperture.
- **One shaft through both eye centres** carries both lids — 67 mm apart — so a single MG90S blinks
  both eyes in sync with no visible linkage.
- **Gear the linkage, do not drive the lid 1:1.** `LID_OPEN_DEG`..`LID_SHUT_DEG` in `config.h` is a
  placeholder 85° that the servo cannot sweep in the 56 ms the blink allows. Size the linkage so
  roughly **34°** of servo produces the full lid travel — a step-up at the lid, the opposite of the
  reduction the brows need. See the open question below for the alternative.
- The lid never fully closes: `BLINK_MIN_OPEN` leaves a 5% sliver. That is a firmware constant, but it
  also means **the mechanism does not need a hard shut stop** — do not design the lid to seat.
- The cowl already hoods the top of each eye, so it is the natural parking place. Size the cowl depth
  around the lid shell rather than treating it as decoration.

### Eyes
- v1: fixed spheres, pupils printed or painted, position chosen once.
- The simulator saccades the gaze and gives each eye a slightly different aim. **No servo budget
  exists for that**, and two eyes aiming independently needs two servos. Gaze stays simulator-only
  until there is a reason to spend them.
- Later: round LCDs in place of the printed balls make both gaze and blink free in software and
  reclaim the lid servo. That changes the face, not just the wiring.

**Servo budget: three, all spoken for** — jaw, brows, lids. Independent brows or any gaze cost a
fourth and fifth.

## Acoustics

- The speaker sits on the deck, facing forward, **not** behind the mouth. The voice comes from below
  the face and that is fine — it is what the reference build does, and an open frame has no cavity to
  fire a mouth grille through.
- Give the driver a printed baffle ring so it is not radiating off a bare plate, and decouple it from
  the deck with foam tape if the deck buzzes.
- Keep servo mounts off the speaker baffle where possible; servo whine transmits through structure.
  Rubber grommets or foam tape at the tabs if it appears.
- An open frame is acoustically leaky by design. Expect less bass than a sealed head would give, and
  do not try to fix it by boxing the frame in — that is a different robot.

## Serviceability

The open frame does most of this for free, which is the main practical argument for it.

- Everything on the deck is reachable without disassembly: Teensy USB port, USB host cable, DIN-5
  socket, servo-power inlet.
- All wiring connectorized (Dupont or JST) — no soldered runs between subassemblies.
- Head block, jaw, brow and lid assemblies each come off as modules for re-printing without touching
  the deck.
- The wiring loom up the neck post is **visible**, so route it deliberately: it reads as detail when
  it is tidy and as a mistake when it is not.

## Printing guidance

- Material: PLA is fine for everything; PETG for the jaw pivot and lid shaft parts if PLA creaks.
- Clearances: 0.25–0.3 mm sliding, 0.15–0.2 mm press — but print a tolerance coupon on YOUR printer
  first and set the CAD clearance variables from it.
- Orientation: eyeballs printed as two hemispheres and glued, or in a vase-mode shell; hinge and shaft
  holes printed vertically for roundness; the head block face-down to keep the visible face clean.
- Fasteners: M3 heat-set inserts where parts are opened repeatedly; self-tapping into bosses elsewhere.
- Keep every dimension a named OpenSCAD variable; magic numbers are banned in the .scad the same way
  they are in the firmware.

## Build order (each stage is useful alone)

1. **Deck** — base plate with mounts for Teensy, amp, speaker and DIN board. No frame, no head.
   Turns the breadboard bring-up into a tidy, movable unit. Print this the week parts arrive.
2. **Frame** — rails and top bar onto the deck. Now it stands up and the proportions become real.
3. **Jaw test rig** — jaw plate, pivot, linkage, servo mount. Iterate here until the motion looks
   alive; this is where most reprints happen, and where two open firmware questions get answered.
4. **Eye and lid module** — one ball, one cowl, one lid shell, one shaft, one servo. Prove the lid
   vanishes into the cowl when open, then settle the servo-speed problem below before sizing the
   linkage: a 56 ms close over the placeholder 85° sweep is about 2.5× faster than an MG90S goes.
5. **Brow module** — one servo, two arms, shared linkage, hard stop at the top-bar ceiling.
6. **Head block** — integrates eyes, lids, jaw and brows onto the neck post.
7. **Finish** — cable routing, feet, any paint or vinyl detailing.

A cardboard or foam mockup of the frame and head proportions is REQUIRED before stage 6 — eye size and
brow height get judged by eye at real scale, not on a screen.

## Open questions this build answers

Nothing in this repo has run on hardware yet. Each of these is mechanical as much as it is firmware,
and each is mirrored in NOTES.md, which is the repo's register of open questions:

- **Does the jaw read as a syllable or a twitch?** The jaw rates were copied from the simulator as
  per-tick numbers, but the firmware ticks at 200 Hz against the simulator's ~60 fps, so the hardware
  jaw opens in 15 ms where the tuned version takes 51 ms. The fix (time constants rather than per-tick
  rates) is written up and deliberately **not applied** — it is a decision for the first real listen.
  The **jaw test rig is that listen**. Build it before deciding.
- **Can an MG90S follow a 200 Hz control rate?** Linkage mass and slop are part of the answer, so it
  belongs to the jaw test rig too.
- **The lid servo cannot do 56 ms, and something has to give.** This one is not really open — the
  arithmetic already says no. The blink shuts in 56 ms (40% of `BLINK_MS`), the placeholder sweep in
  `config.h` is 85°, and an MG90S at ~100 ms per 60° needs about **142 ms** for that. It is 2.5×
  short, not marginal. Two ways out, and the eye and lid module is where one gets chosen:
  **gear the linkage** so roughly 34° of servo drives the full lid travel — a step-up at the lid,
  the opposite of what the brows need — or **lengthen `BLINK_MS`** to about 354 ms and accept a
  slower blink. Gearing keeps parity with the simulator and is the better answer if the lid is light
  enough to move that fast; lengthening is the safe fallback. Do not wire a servo to the placeholder
  angles and expect it to track.
- **Do the brows move together or independently?** The simulator deliberately makes them disagree, and
  one servo cannot. Either the hardware accepts synchronised brows or it buys a fourth servo, and the
  brow module is where that gets decided.
- **What is the real scale?** Every millimetre in this document hangs off one assumed 50 mm speaker.
  Measure the actual driver first and re-anchor before anything is printed at final size.

## Out of scope for v1

Gaze actuation, independent brows, round LCD eyes, neck/tilt articulation, battery power, the
multi-robot choir variants. Design nothing that blocks them (leave deck space and wiring headroom),
build none of them yet.
