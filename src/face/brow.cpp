/*
 * brow.cpp — eased brow motion.
 *
 * Nothing snaps: the brows drift up while the robot sings and settle back
 * after, which is what separates an expressive face from a twitching one.
 */

#include <Arduino.h>
#include <PWMServo.h>

#include "config.h"
#include "face/brow.h"
#include "house_sound.h"

#if ENABLE_BROW_SERVO
static PWMServo browServo;
#endif

static float browActual = 0.0f;   // 0 resting .. 1 raised
static float browTargetValue = 0.0f;
static float browAlpha = 1.0f;

void browBegin() {
  // One-pole coefficient for a CONTROL_INTERVAL_MS tick, from the time
  // constant rather than from the simulator's per-frame number.
  browAlpha = 1.0f - expf(-(float)CONTROL_INTERVAL_MS / BROW_SMOOTH_MS);
#if ENABLE_BROW_SERVO
  browServo.attach(BROW_PIN);
  browServo.write(BROW_DOWN_DEG);
#endif
}

void browSetTarget(float target) {
  browTargetValue = target;
}

float browTarget() {
  return browTargetValue;
}

void browUpdate() {
  browActual += (browTargetValue - browActual) * browAlpha;
#if ENABLE_BROW_SERVO
  int deg = BROW_DOWN_DEG + (int)((BROW_UP_DEG - BROW_DOWN_DEG) * browActual);
  browServo.write(deg);
#else
  (void)browActual;   // tracked now, driven once a servo is wired
#endif
}
