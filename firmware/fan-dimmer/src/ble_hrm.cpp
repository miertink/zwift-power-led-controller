#include "ble_hrm.h"

#include <NimBLEDevice.h>

#include "config.h"

static const NimBLEUUID HEART_RATE_SERVICE_UUID((uint16_t) 0x180D);
static const NimBLEUUID HEART_RATE_MEASUREMENT_UUID((uint16_t) 0x2A37);

static NimBLEScan *scan = nullptr;
static NimBLEClient *client = nullptr;

static volatile bool connected = false;
static volatile int lastBpm = 0;
static volatile unsigned long lastHrUpdateMillis = 0;

// Set from the scan callback (BLE host task context); consumed from hrmLoop() (Arduino
// loop context) to actually connect.
static volatile bool pendingConnectRequest = false;
static NimBLEAdvertisedDevice *pendingDevice = nullptr;

// Bounded scan windows, restarted on every window end - see README (indefinite scans hang).
static void onScanComplete(NimBLEScanResults results) {
    if (connected || pendingConnectRequest) {
        return;
    }
    NimBLEDevice::getScan()->start(5, onScanComplete);
}

static bool addressMatches(const NimBLEAddress &address) {
    if (strlen(HRM_MAC_ADDRESS) == 0) {
        return true;
    }
    return strcasecmp(address.toString().c_str(), HRM_MAC_ADDRESS) == 0;
}

class HrmScanCallbacks : public NimBLEAdvertisedDeviceCallbacks {
    void onResult(NimBLEAdvertisedDevice *advertisedDevice) override {
        if (pendingConnectRequest) {
            return;
        }
        if (!advertisedDevice->isAdvertisingService(HEART_RATE_SERVICE_UUID)) {
            return;
        }
        if (!addressMatches(advertisedDevice->getAddress())) {
            return;
        }
        Serial.printf("HRM found: %s (%s)\n", advertisedDevice->getName().c_str(),
                       advertisedDevice->getAddress().toString().c_str());
        NimBLEDevice::getScan()->stop();
        pendingDevice = new NimBLEAdvertisedDevice(*advertisedDevice);
        pendingConnectRequest = true;
    }
};

static void onHrNotify(NimBLERemoteCharacteristic *characteristic, uint8_t *data, size_t length, bool isNotify) {
    if (length < 2) {
        return;
    }
    uint8_t flags = data[0];
    int bpm;
    if (flags & 0x01) {
        // 16-bit HR value
        if (length < 3) return;
        bpm = data[1] | (data[2] << 8);
    } else {
        // 8-bit HR value
        bpm = data[1];
    }
    lastBpm = bpm;
    lastHrUpdateMillis = millis();
}

class HrmClientCallbacks : public NimBLEClientCallbacks {
    void onConnect(NimBLEClient *pClient) override {
        Serial.println("HRM connected");
    }

    void onDisconnect(NimBLEClient *pClient) override {
        Serial.println("HRM disconnected");
        connected = false;
        NimBLEDevice::getScan()->start(5, onScanComplete);
    }
};

static HrmScanCallbacks scanCallbacks;
static HrmClientCallbacks clientCallbacks;

static void connectToPendingDevice() {
    NimBLEAdvertisedDevice *device = pendingDevice;
    pendingDevice = nullptr;
    pendingConnectRequest = false;

    if (client == nullptr) {
        client = NimBLEDevice::createClient();
        client->setClientCallbacks(&clientCallbacks, false);
    }

    if (!client->connect(device)) {
        Serial.println("HRM connect failed, resuming scan");
        delete device;
        NimBLEDevice::getScan()->start(5, onScanComplete);
        return;
    }

    NimBLERemoteService *service = client->getService(HEART_RATE_SERVICE_UUID);
    if (service == nullptr) {
        Serial.println("HRM has no Heart Rate Service, disconnecting");
        client->disconnect();
        delete device;
        return;
    }

    NimBLERemoteCharacteristic *characteristic = service->getCharacteristic(HEART_RATE_MEASUREMENT_UUID);
    if (characteristic == nullptr || !characteristic->canNotify()) {
        Serial.println("HRM has no notifiable Heart Rate Measurement characteristic, disconnecting");
        client->disconnect();
        delete device;
        return;
    }

    characteristic->subscribe(true, onHrNotify, false);
    connected = true;
    delete device;
}

void hrmBegin() {
    NimBLEDevice::init("");
    scan = NimBLEDevice::getScan();
    scan->setAdvertisedDeviceCallbacks(&scanCallbacks, false);
    scan->setActiveScan(true);
    scan->setInterval(100);
    scan->setWindow(100);
    scan->start(5, onScanComplete);
}

void hrmLoop() {
    if (pendingConnectRequest) {
        connectToPendingDevice();
    }
}

bool hrmIsConnected() {
    return connected;
}

int hrmGetBpm() {
    return lastBpm;
}

bool hrmIsStale(unsigned long timeoutMs) {
    if (lastHrUpdateMillis == 0) {
        return true;
    }
    return (millis() - lastHrUpdateMillis) > timeoutMs;
}
