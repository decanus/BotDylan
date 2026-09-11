/*
 * jaw.cpp — servo motion model.
 *
 * Asymmetric easing is the whole trick: the mouth snaps open and closes
 * lazily, which reads as a sung syllable rather than a servo twitch.
 */

#include <Arduino.h>
#include <PWMServo.h>

#include "config.h"
#include "face/jaw.h"

static PWMServo jawServo;

static float jawActual = 0.0f;   // 0 closed .. 1 open
static float jawTarget = 0.0f;

void jawBegin() {
  jawServo.attach(JAW_PIN);
  jawServo.write(JAW_CLOSED_DEG);
}

void jawSetTarget(float target) {
  jawTarget = target;
}

void jawUpdate(float vowelPos) {
  // Ease jaw toward target; vowel affects mouth shape.
  //
  // The 2.0f here is the index of "ah", the most open vowel, and the 2.0f
  // divisor is half the table length — so this assumes a 5-entry preset
  // centered on the open vowel. See NOTES.md before reshaping a preset.
  float vowelOpenness = 1.0f - 0.35f * fabsf(vowelPos - 2.0f) / 2.0f;
  float target = jawTarget * vowelOpenness;

  float rate = (target > jawActual) ? 0.30f : 0.12f;   // fast open, slow close
  jawActual += (target - jawActual) * rate;

  int deg = JAW_CLOSED_DEG + (int)((JAW_OPEN_DEG - JAW_CLOSED_DEG) * jawActual);
  jawServo.write(deg);
}
