#include "zc_diag.h"

// A clean half-cycle is ~8333us (60Hz) to ~10000us (50Hz); flag well outside that as a glitch.
#define ZC_GLITCH_LOW_US 6000
#define ZC_GLITCH_HIGH_US 11500

// Measured bounce was 6-610us apart, well under a real half-cycle - anything faster is noise.
#define ZC_DEBOUNCE_US 2000

static volatile uint32_t lastZcMicros = 0;
static volatile bool haveLastSample = false;
static volatile uint32_t intervalMin = 0xFFFFFFFF;
static volatile uint32_t intervalMax = 0;
static volatile uint32_t intervalSum = 0;
static volatile uint32_t intervalCount = 0;
static volatile uint32_t glitchCount = 0;
static volatile uint32_t lastGlitchIntervalUs = 0;

static volatile uint32_t lastAcceptedMicros = 0;
static volatile bool haveAccepted = false;

bool IRAM_ATTR zcDiagRecordSample() {
    uint32_t now = micros();
    if (haveLastSample) {
        uint32_t interval = now - lastZcMicros;
        if (interval < intervalMin) intervalMin = interval;
        if (interval > intervalMax) intervalMax = interval;
        intervalSum += interval;
        intervalCount++;
        if (interval < ZC_GLITCH_LOW_US || interval > ZC_GLITCH_HIGH_US) {
            glitchCount++;
            lastGlitchIntervalUs = interval;
        }
    }
    lastZcMicros = now;
    haveLastSample = true;

    bool accept = true;
    if (haveAccepted && (now - lastAcceptedMicros) < ZC_DEBOUNCE_US) {
        accept = false;
    }
    if (accept) {
        lastAcceptedMicros = now;
        haveAccepted = true;
    }
    return accept;
}

void zcDiagReportAndReset() {
    noInterrupts();
    uint32_t minUs = intervalMin;
    uint32_t maxUs = intervalMax;
    uint32_t sum = intervalSum;
    uint32_t count = intervalCount;
    uint32_t glitches = glitchCount;
    uint32_t lastGlitch = lastGlitchIntervalUs;
    intervalMin = 0xFFFFFFFF;
    intervalMax = 0;
    intervalSum = 0;
    intervalCount = 0;
    glitchCount = 0;
    interrupts();

    if (count == 0) {
        Serial.println("ZC diag: no zero-cross samples in this window");
        return;
    }
    uint32_t avg = sum / count;
    Serial.printf(
        "ZC diag: %u samples, interval min=%uus avg=%uus max=%uus, %u glitches (last=%uus)\n",
        (unsigned) count, (unsigned) minUs, (unsigned) avg, (unsigned) maxUs, (unsigned) glitches, (unsigned) lastGlitch
    );
}
