/*
 * blink.cpp — one-shot lid envelope on a randomised timer.
 *
 * A little state machine over elapsed milliseconds: shut, open, wait. Why it
 * is shaped that way rather than easing toward a target like its siblings is
 * written down once, beside the constants, in house_sound.h.
 *
 * Time is accumulated from CONTROL_INTERVAL_MS rather than read from millis().
 * The caller already guarantees the control rate, and BLINK_MS is a multiple
 * of it, so the envelope lands on its endpoint exactly. The cost is that a
 * control tick that runs late is still counted as one interval, so a blink
 * stretches slightly whenever the loop does.
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

// Called when a blink ENDS. The simulator schedules from the moment a blink
// starts, so a gap measured from the end has to lose the envelope it just
// played or every interval runs BLINK_MS long. The doubled blink needs no such
// correction: its 90 ms is defined as the pause between the pair.
static void scheduleNext() {
  // A blink occasionally comes in pairs, and doubleQueued is the only record
  // that stops a pair becoming a triple. random() is unseeded on purpose: a
  // fixed power-up sequence is easier to watch on the bench, and nothing here
  // needs unpredictability — only the absence of an obvious period.
  doubleQueued = !doubleQueued && random(1000) < (long)(BLINK_DOUBLE_CHANCE * 1000.0f);
  waitMs = doubleQueued
         ? BLINK_DOUBLE_GAP_MS
         : (int)random(BLINK_GAP_MIN_MS, BLINK_GAP_MAX_MS) - BLINK_MS;
}

void blinkBegin() {
  // Deliberately not scheduleNext(): that can roll a doubled blink, and the
  // short gap is the pause BETWEEN a pair, never the wait before the first
  // blink of all. Rolling it here would open the eyes 90 ms after boot on
  // roughly one power-up in five.
  waitMs = (int)random(BLINK_GAP_MIN_MS, BLINK_GAP_MAX_MS);
#if ENABLE_LID_SERVO
  lidServo.attach(LID_PIN);
  lidServo.write(LID_OPEN_DEG);
#endif
}

float blinkOpenness() {
  return openness;
}

void blinkUpdate() {
  openness = 1.0f;                    // open, unless the envelope says otherwise
  if (phaseMs < 0) {                  // waiting for the next one
    waitMs -= CONTROL_INTERVAL_MS;
    if (waitMs <= 0) phaseMs = 0;
  } else if (phaseMs >= BLINK_MS) {   // just finished
    phaseMs = -1;
    scheduleNext();
  } else {
    // Shuts over the first BLINK_CLOSE_FRAC of the envelope and opens over the
    // rest, so it snaps closed and drifts back up.
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
#endif
}
