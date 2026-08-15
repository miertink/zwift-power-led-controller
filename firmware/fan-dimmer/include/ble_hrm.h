#pragma once

#include <Arduino.h>

// BLE central that connects to a heart rate strap advertising the standard BLE Heart Rate
// Service (0x180D) - e.g. a Garmin HRM 200 - and keeps the latest BPM reading available.
// This is the sole source driving fan speed now; there is no MQTT subscription involved.

void hrmBegin();

// Drives the scan/connect/reconnect state machine. Call every loop() iteration.
void hrmLoop();

bool hrmIsConnected();

// Latest heart rate reading in BPM. Only meaningful when hrmIsConnected() and not stale.
int hrmGetBpm();

// True once more than timeoutMs has passed since the last heart rate notification (strap
// off, out of range, or BLE link lost) - or if never connected at all.
bool hrmIsStale(unsigned long timeoutMs);
