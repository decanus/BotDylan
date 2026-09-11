/*
 * blink.cpp — one-shot lid envelope on a randomised timer.
 *
 * Unlike jaw.cpp and brow.cpp there is no easing here. A blink is a gesture
 * with a beginning and an end, not a value chasing a target, so it is written
 * as a little state machine over elapsed milliseconds: shut, open, wait.
 *
 * Time is accumulated from CONTROL_INTERVAL_MS rather than read from millis().
 * The caller already guarantees the control rate, and counting ticks keeps the
 * whole model testable without a clock.
 *
 * Parity: this mirrors the simulator's blink exactly, including the doubled
 * blink and the sliver of eye that never quite closes. See README.
 */

#include <Arduino.h>
#include <PWMServo.h>

#include "config.h"
#include "face/blink.h"
#include "house_sound.h"

#if ENABLE_LID_SERVO
static PWMServo lidServo;
#endif

static float openness = 1.0f;   // 1 open .. BLINK_MIN_OPEN shut
static int   phaseMs = -1;      // ms into the current blink; -1 = waiting
static int   waitMs = 0;        // ms left before the next one
static bool  doubleQueued = false;

static void scheduleNext() {
  // A blink occasionally comes in pairs. random() is unseeded on purpose: a
  // fixed power-up sequence is easier to watch on the bench, and nothing here
  // needs unpredictability — only the absence of an obvious period.
  if (!doubleQueued && random(1000) < (long)(BLINK_DOUBLE_CHANCE * 1000.0f)) {
    doubleQueued = true;
    waitMs = BLINK_DOUBLE_GAP_MS;
  } else {
    doubleQueued = false;
    waitMs = (int)random(BLINK_GAP_MIN_MS, BLINK_GAP_MAX_MS);
  }
}

void blinkBegin() {
  scheduleNext();
#if ENABLE_LID_SERVO
  lidServo.attach(LID_PIN);
  lidServo.write(LID_OPEN_DEG);
#endif
}

float blinkOpenness() {
  return openness;
}

void blinkNow() {
  phaseMs = 0;
}

void blinkUpdate() {
  if (phaseMs < 0) {
    waitMs -= CONTROL_INTERVAL_MS;
    if (waitMs <= 0) phaseMs = 0;
    openness = 1.0f;
  } else if (phaseMs >= BLINK_MS) {
    openness = 1.0f;
    phaseMs = -1;
    scheduleNext();
  } else {
    // Shuts over the first BLINK_CLOSE_FRAC of the envelope, opens over the
    // rest — so it snaps closed and drifts back up.
    const float p = (float)phaseMs / BLINK_MS;
    const float raw = (p < BLINK_CLOSE_FRAC)
                    ? 1.0f - p / BLINK_CLOSE_FRAC
                    : (p - BLINK_CLOSE_FRAC) / (1.0f - BLINK_CLOSE_FRAC);
    openness = raw < BLINK_MIN_OPEN ? BLINK_MIN_OPEN : raw;
    phaseMs += CONTROL_INTERVAL_MS;
  }

#if ENABLE_LID_SERVO
  int deg = LID_OPEN_DEG + (int)((LID_SHUT_DEG - LID_OPEN_DEG) * (1.0f - openness));
  lidServo.write(deg);
#else
  (void)openness;   // tracked now, driven once a servo is wired
#endif
}
