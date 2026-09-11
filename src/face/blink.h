/*
 * blink.h — the eyelids.
 *
 * The odd one out in face/. The jaw and the brows are given a target by
 * whoever owns the sound, and ease toward it; the lids own their own timing
 * and nobody sets a target at all. The reasoning lives beside the constants
 * in house_sound.h.
 *
 * Openness rather than lid position, so this reads the same way round as the
 * simulator it mirrors — see FACE.blink* in tools/simulator.html.
 *
 * The pin is reserved before the hardware exists (see ENABLE_LID_SERVO in
 * config.h); the motion model runs regardless.
 */
#pragma once

void blinkBegin();

// 1.0 = eyes open .. BLINK_MIN_OPEN = shut. Read-only: the lids drive
// themselves. Also the value to drive round eye displays with, if the head
// ends up with those instead of servos.
float blinkOpenness();

// Call at the control rate (200 Hz).
void blinkUpdate();
