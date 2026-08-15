#pragma once

#include <Arduino.h>

// Temporary diagnostic: tracks the time between consecutive zero-cross interrupts to check
// whether they're arriving cleanly and regularly (a real 50/60Hz half-cycle is ~10000us /
// ~8333us) or are jittery/missed/duplicated - which would point at WiFi-induced interrupt
// latency or noise coupling into the zero-cross detector, rather than the dimming algorithm
// itself, as the source of the irregular low-pitched noise reported on top of the normal
// phase-cut buzz.

// Records one zero-cross sample and returns whether it should be treated as a genuine
// zero-cross (true) or ignored as electrical bounce/noise (false - it arrived too soon
// after the last accepted one to be a real half-cycle). Call from the zero-cross ISR.
// IRAM-safe.
bool IRAM_ATTR zcDiagRecordSample();

// Prints a summary (sample count, min/avg/max interval, glitch count) over Serial for the
// samples recorded since the last call, then resets the aggregation window.
void zcDiagReportAndReset();
