#pragma once

#include <Arduino.h>

// Tracks zero-cross interrupt timing: debounces electrical bounce/noise and reports
// min/avg/max interval + glitch count over Serial.

// Records one zero-cross sample; returns false if it's too soon after the last accepted
// one to be genuine (debounced as noise). Call from the zero-cross ISR. IRAM-safe.
bool IRAM_ATTR zcDiagRecordSample();

void zcDiagReportAndReset();
