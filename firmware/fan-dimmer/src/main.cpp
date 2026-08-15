#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <RBDdimmer.h>
#include <math.h>

#include "ble_hrm.h"
#include "config.h"
#include "zc_diag.h"

WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);
dimmerLamp fanDimmer(DIMMER_OUTPUT_PIN, DIMMER_ZC_PIN);

const unsigned long ZC_DIAG_REPORT_INTERVAL_MS = 5000;
unsigned long lastZcDiagReport = 0;

// Fan state, tracked separately from the dimmer so the fan speed LED can reflect it
uint8_t fanSpeedPercent = 0;
bool fanEnabled = false;

// Fan power ramp: steps the dimmer's actually-applied power toward the target gradually
// instead of jumping straight to it. Going from off/low straight to a high duty can make
// the motor start with a loud stutter before it catches; this ramps over ~2.5s (40%/s)
// regardless of how abruptly the target changes.
uint8_t fanTargetPercent = 0;
uint8_t fanAppliedPercent = 0;
unsigned long lastFanRampStep = 0;
const unsigned long FAN_RAMP_STEP_INTERVAL_MS = 100;
const uint8_t FAN_RAMP_STEP_SIZE = 4; // %/step -> 40%/s, ~2.5s for a full 0-100 ramp

// Status LED: blinks while scanning/connecting to the HRM strap, solid ON once a fresh
// heart rate reading is coming in
const unsigned long STATUS_BLINK_INTERVAL_MS = 400;
unsigned long lastStatusToggle = 0;
bool statusLedState = false;

// Fan LED: blink half-period maps fan speed 0-100% between these two extremes
const unsigned long FAN_BLINK_SLOWEST_MS = 1000; // half-period at 0% speed
const unsigned long FAN_BLINK_FASTEST_MS = 60;   // half-period at 100% speed
unsigned long lastFanToggle = 0;
bool fanLedState = false;

// RGB LED (Tasmota, over MQTT): on whenever the HRM is healthy, color reflects the HR zone
bool ledEnabled = false;
char lastPublishedColor[8] = "";

// WiFi/MQTT: required for the RGB LED (Tasmota only speaks MQTT), not for the fan (BLE is
// self-contained). Retried periodically rather than blocking anything if unavailable.
unsigned long lastWifiRetry = 0;
const unsigned long WIFI_RETRY_INTERVAL_MS = 10000;
const unsigned long STATUS_PUBLISH_INTERVAL_MS = 4000;
unsigned long lastStatusPublish = 0;

const unsigned long BPM_LOG_INTERVAL_MS = 2000;
unsigned long lastBpmLog = 0;

int currentBpm() {
    return hrmGetBpm();
}

bool hrmHealthy() {
    return hrmIsConnected() && !hrmIsStale(HRM_STALE_TIMEOUT_MS);
}

int computeFanTargetFromBpm(int bpm) {
    if (bpm <= HRM_MIN_BPM) {
        return HRM_BASE_SPEED;
    }
    if (bpm >= HRM_MAX_BPM) {
        return HRM_MAX_SPEED;
    }
    float ratio = (float) (bpm - HRM_MIN_BPM) / (float) (HRM_MAX_BPM - HRM_MIN_BPM);
    return (int) roundf(HRM_BASE_SPEED + ratio * (HRM_MAX_SPEED - HRM_BASE_SPEED));
}

// Same 6-color palette power_to_color.py used for Zwift power zones, now keyed off HR
// zones instead (see HR_ZONE*_MIN in config.h).
const char *computeHrZoneColor(int bpm) {
    if (bpm < HR_ZONE1_MIN) return "D3D3D3"; // resting - Light Grey
    if (bpm < HR_ZONE2_MIN) return "0000FF"; // Z1 - Blue
    if (bpm < HR_ZONE3_MIN) return "00FF00"; // Z2 - Green
    if (bpm < HR_ZONE4_MIN) return "FFFF00"; // Z3 - Yellow
    if (bpm < HR_ZONE5_MIN) return "FFA500"; // Z4 - Orange
    return "FF6347";                         // Z5 - Tomato
}

const char *hrZoneLabel(int bpm) {
    if (bpm < HR_ZONE1_MIN) return "resting";
    if (bpm < HR_ZONE2_MIN) return "Z1";
    if (bpm < HR_ZONE3_MIN) return "Z2";
    if (bpm < HR_ZONE4_MIN) return "Z3";
    if (bpm < HR_ZONE5_MIN) return "Z4";
    return "Z5";
}

void updateStatusLed() {
    if (hrmHealthy()) {
        digitalWrite(STATUS_LED_PIN, HIGH);
        return;
    }
    unsigned long now = millis();
    if (now - lastStatusToggle >= STATUS_BLINK_INTERVAL_MS) {
        lastStatusToggle = now;
        statusLedState = !statusLedState;
        digitalWrite(STATUS_LED_PIN, statusLedState);
    }
}

void updateFanRamp() {
    if (fanAppliedPercent == fanTargetPercent) {
        return;
    }
    unsigned long now = millis();
    if (now - lastFanRampStep < FAN_RAMP_STEP_INTERVAL_MS) {
        return;
    }
    lastFanRampStep = now;

    int next = fanAppliedPercent;
    if (fanAppliedPercent < fanTargetPercent) {
        next += FAN_RAMP_STEP_SIZE;
        if (next > fanTargetPercent) next = fanTargetPercent;
    } else {
        next -= FAN_RAMP_STEP_SIZE;
        if (next < fanTargetPercent) next = fanTargetPercent;
    }
    fanAppliedPercent = (uint8_t) next;
    fanDimmer.setPower(fanAppliedPercent);
    fanSpeedPercent = fanAppliedPercent;
}

void updateFanLed() {
    if (!fanEnabled) {
        digitalWrite(FAN_LED_PIN, LOW);
        return;
    }
    unsigned long halfPeriod = map(fanSpeedPercent, 0, 100, FAN_BLINK_SLOWEST_MS, FAN_BLINK_FASTEST_MS);
    unsigned long now = millis();
    if (now - lastFanToggle >= halfPeriod) {
        lastFanToggle = now;
        fanLedState = !fanLedState;
        digitalWrite(FAN_LED_PIN, fanLedState);
    }
}

// The BLE link itself is the safety net that used to be run.py's MQTT Last Will kill
// switch: no heart rate (or below HRM_MIN_BPM - not actually working out), no fan - forced
// off immediately rather than left spinning at whatever speed was last commanded.
void updateFanFromHrm() {
    bool healthy = hrmHealthy() && currentBpm() >= HRM_MIN_BPM;

    if (!healthy) {
        if (fanEnabled) {
            fanDimmer.setState(OFF);
            fanEnabled = false;
            fanTargetPercent = 0;
            fanAppliedPercent = 0;
            fanDimmer.setPower(0);
            fanSpeedPercent = 0;
            Serial.println("HRM disconnected/stale/below threshold - fan forced OFF");
        }
        return;
    }

    if (!fanEnabled) {
        fanDimmer.setState(ON);
        fanEnabled = true;
        Serial.println("HRM connected - fan enabled");
    }
    fanTargetPercent = (uint8_t) computeFanTargetFromBpm(currentBpm());
}

// RGB LED stays on whenever the strap is connected (even resting/grey, mirroring how the
// old Zwift-power LED stayed lit at 0W while still "online"); only goes off when the HRM
// itself is unhealthy. Publishes only on change to avoid spamming MQTT on every BLE
// notification (arrives roughly once a second).
void updateLed() {
    if (WiFi.status() != WL_CONNECTED || !mqttClient.connected()) {
        return;
    }

    bool healthy = hrmHealthy();
    if (!healthy) {
        if (ledEnabled) {
            mqttClient.publish(MQTT_ENABLE_ALL_TOPIC, "0");
            ledEnabled = false;
            lastPublishedColor[0] = '\0';
            Serial.println("HRM disconnected/stale - LED forced OFF");
        }
        return;
    }

    if (!ledEnabled) {
        mqttClient.publish(MQTT_ENABLE_ALL_TOPIC, "1");
        mqttClient.publish(MQTT_DIMMER_TOPIC, "100");
        ledEnabled = true;
    }

    const char *color = computeHrZoneColor(currentBpm());
    if (strcmp(color, lastPublishedColor) != 0) {
        mqttClient.publish(MQTT_BASE_COLOR_TOPIC, color);
        strncpy(lastPublishedColor, color, sizeof(lastPublishedColor));
        Serial.printf("LED color -> %s (bpm=%d)\n", color, currentBpm());
    }
}

void connectWifi() {
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    Serial.printf("Connecting to WiFi %s", WIFI_SSID);
    unsigned long start = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - start < 10000) {
        delay(500);
        Serial.print(".");
    }
    if (WiFi.status() == WL_CONNECTED) {
        Serial.printf("\nWiFi connected, IP: %s\n", WiFi.localIP().toString().c_str());
    } else {
        Serial.println("\nWiFi connect timed out - will keep retrying in the background");
    }
}

void connectMqtt() {
    if (mqttClient.connected()) {
        return;
    }
    // Last Will: if this ESP32 crashes/loses power without disconnecting cleanly, the
    // broker publishes "0" here automatically, turning the RGB LED off rather than leaving
    // it stuck on the last color shown.
    if (mqttClient.connect(MQTT_CLIENT_ID, MQTT_LOGIN, MQTT_PASSWORD, MQTT_ENABLE_ALL_TOPIC, 0, true, "0")) {
        Serial.println("MQTT connected");
        ledEnabled = false; // force a fresh enable+color publish on the next updateLed()
        lastPublishedColor[0] = '\0';
    }
    // Best-effort only: no retry loop/blocking here, fan control never depends on this.
}

void publishStatus() {
    if (!mqttClient.connected()) {
        return;
    }
    char payload[128];
    snprintf(payload, sizeof(payload), "{\"bpm\":%d,\"connected\":%s,\"fan_speed\":%d}", currentBpm(),
              hrmHealthy() ? "true" : "false", fanSpeedPercent);
    mqttClient.publish(MQTT_STATUS_TOPIC, payload);
}

void setup() {
    Serial.begin(115200);

    pinMode(STATUS_LED_PIN, OUTPUT);
    pinMode(FAN_LED_PIN, OUTPUT);
    digitalWrite(STATUS_LED_PIN, LOW);
    digitalWrite(FAN_LED_PIN, LOW);

    fanDimmer.begin(NORMAL_MODE, OFF);
    fanDimmer.setPower(0);

    hrmBegin();

    connectWifi();
    mqttClient.setServer(MQTT_HOST, MQTT_PORT);
    connectMqtt();
}

void loop() {
    hrmLoop();
    updateFanFromHrm();

    if (WiFi.status() != WL_CONNECTED) {
        unsigned long now = millis();
        if (now - lastWifiRetry >= WIFI_RETRY_INTERVAL_MS) {
            lastWifiRetry = now;
            WiFi.reconnect();
        }
    } else if (!mqttClient.connected()) {
        connectMqtt();
    } else {
        mqttClient.loop();
    }

    updateStatusLed();
    updateFanRamp();
    updateFanLed();
    updateLed();

    unsigned long now = millis();
    if (now - lastZcDiagReport >= ZC_DIAG_REPORT_INTERVAL_MS) {
        lastZcDiagReport = now;
        zcDiagReportAndReset();
    }
    if (now - lastStatusPublish >= STATUS_PUBLISH_INTERVAL_MS) {
        lastStatusPublish = now;
        publishStatus();
    }
    if (now - lastBpmLog >= BPM_LOG_INTERVAL_MS) {
        lastBpmLog = now;
        int bpmNow = currentBpm();
        Serial.printf("HRM: healthy=%d bpm=%d zone=%s -> fan target=%d%% applied=%d%%\n", hrmHealthy(), bpmNow,
                       hrZoneLabel(bpmNow), computeFanTargetFromBpm(bpmNow), fanAppliedPercent);
    }
}
