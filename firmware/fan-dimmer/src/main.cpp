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

uint8_t fanSpeedPercent = 0;
bool fanEnabled = false;
uint8_t fanAppliedPercent = 0;

// Master on/off override for Home Assistant; defaults ON so the fan works without it.
bool fanRemoteEnabled = true;

const unsigned long STATUS_BLINK_INTERVAL_MS = 400;
unsigned long lastStatusToggle = 0;
bool statusLedState = false;

const unsigned long FAN_BLINK_SLOWEST_MS = 1000; // half-period at 0% speed
const unsigned long FAN_BLINK_FASTEST_MS = 60;   // half-period at 100% speed
unsigned long lastFanToggle = 0;
bool fanLedState = false;

bool ledEnabled = false;
char lastPublishedColor[8] = "";

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

// Hysteresis around HRM_MIN_BPM avoids the fan clicking on/off when BPM hovers near it.
void updateFanFromHrm() {
    int bpm = currentBpm();
    int turnOffBelowBpm = HRM_MIN_BPM - HRM_HYSTERESIS_BPM;
    bool bpmOk = fanEnabled ? bpm > turnOffBelowBpm : bpm >= HRM_MIN_BPM;
    bool shouldRun = fanRemoteEnabled && hrmHealthy() && bpmOk;

    if (!shouldRun) {
        if (fanEnabled) {
            fanDimmer.setState(OFF);
            fanEnabled = false;
            fanAppliedPercent = 0;
            fanDimmer.setPower(0);
            fanSpeedPercent = 0;
            Serial.println(fanRemoteEnabled ? "HRM disconnected/stale/below threshold - fan forced OFF"
                                             : "Fan remote switch OFF - fan forced OFF");
        }
        return;
    }

    if (!fanEnabled) {
        fanDimmer.setState(ON);
        fanEnabled = true;
        Serial.println("HRM connected - fan enabled");
    }
    fanAppliedPercent = (uint8_t) computeFanTargetFromBpm(bpm);
    fanDimmer.setPower(fanAppliedPercent);
    fanSpeedPercent = fanAppliedPercent;
}

// LED stays on (grey at rest) whenever the strap is connected; publishes only on change.
void updateLed() {
    if (WiFi.status() != WL_CONNECTED || !mqttClient.connected()) {
        return;
    }

    if (!hrmHealthy()) {
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

void publishFanPowerState() {
    if (!mqttClient.connected()) {
        return;
    }
    mqttClient.publish(MQTT_FAN_POWER_STATE_TOPIC, fanRemoteEnabled ? "ON" : "OFF", true);
}

void onMqttMessage(char *topic, byte *payload, unsigned int length) {
    if (strcmp(topic, MQTT_FAN_POWER_COMMAND_TOPIC) != 0) {
        return;
    }
    bool turnOn = !((length == 3 && strncasecmp((const char *) payload, "OFF", 3) == 0) ||
                     (length == 1 && payload[0] == '0'));
    if (turnOn != fanRemoteEnabled) {
        fanRemoteEnabled = turnOn;
        Serial.printf("Fan remote switch -> %s\n", fanRemoteEnabled ? "ON" : "OFF");
    }
    publishFanPowerState();
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
    // Last Will turns the LED off if this ESP32 crashes/loses power uncleanly.
    if (mqttClient.connect(MQTT_CLIENT_ID, MQTT_LOGIN, MQTT_PASSWORD, MQTT_ENABLE_ALL_TOPIC, 0, true, "0")) {
        Serial.println("MQTT connected");
        ledEnabled = false;
        lastPublishedColor[0] = '\0';
        mqttClient.subscribe(MQTT_FAN_POWER_COMMAND_TOPIC);
        publishFanPowerState();
    }
}

void publishStatus() {
    if (!mqttClient.connected()) {
        return;
    }
    // currentBpm() holds the last reading forever; only report it while healthy.
    bool healthy = hrmHealthy();
    char payload[128];
    snprintf(payload, sizeof(payload), "{\"bpm\":%d,\"connected\":%s,\"fan_speed\":%d}", healthy ? currentBpm() : 0,
              healthy ? "true" : "false", fanSpeedPercent);
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
    mqttClient.setCallback(onMqttMessage);
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
