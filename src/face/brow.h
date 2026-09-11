/*
 * brow.h — the eyebrows.
 *
 * Same shape as jaw.h on purpose: a target somebody else sets, and an eased
 * motion model that runs at the control rate. Knows nothing about the voice.
 *
 * The pin is reserved before the hardware exists (see ENABLE_BROW_SERVO in
 * config.h); the motion model runs regardless, so wiring a servo later is a
 * one-line change rather than a port.
 */
#pragma once

void browBegin();

// 0.0 = resting .. 1.0 = fully raised.
void browSetTarget(float target);
float browTarget();

// Call at the control rate (200 Hz).
void browUpdate();
