/*
 * jaw.h — the mouth. Eased open/close motion driven by note velocity.
 *
 * Deliberately knows nothing about the voice: main.cpp hands jawUpdate() the
 * current vowel position, rather than face/ reaching into voice/. Future face
 * parts (eyes, brows) become siblings of this file with the same shape.
 */
#pragma once

void jawBegin();

// 0.0 = closed .. 1.0 = fully open. The motion model eases toward this.
void jawSetTarget(float target);
float jawTarget();

// Call at the control rate (200 Hz). vowelPos is the fractional index into
// the vowel table — rounder vowels open the mouth further.
void jawUpdate(float vowelPos);
