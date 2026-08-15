# Fan AC Dimmer + RGB LED Firmware (ESP32-WROOM)

Firmware for an ESP32-WROOM that controls both the fan speed dimmer and the
RGB LED strip directly from live heart rate, read over Bluetooth Low Energy
from a chest strap (e.g. Garmin HRM 200). Zwift/`run.py` are no longer
involved in either control path - `run.py`'s own LED publishing must stay
disabled (see below) so the two don't fight over the same MQTT topics.

> [!WARNING]
> This module switches **mains voltage (AC)** directly. Incorrect wiring
> can cause electric shock or fire. Only proceed if you are comfortable
> working with mains voltage, keep the board enclosed, and disconnect
> power before touching any wiring.

## How it works

- **Heart rate source**: [src/ble_hrm.cpp](src/ble_hrm.cpp) uses
  [NimBLE-Arduino](https://github.com/h2zero/NimBLE-Arduino) as a BLE
  central, scanning for and connecting to any device advertising the
  standard BLE Heart Rate Service (`0x180D`) - pin it to one specific strap
  via `HRM_MAC_ADDRESS` in `config.h` if there's a risk of connecting to
  someone else's. If no heart rate notification arrives for
  `HRM_STALE_TIMEOUT_MS`, the reading is treated as stale.
  - Scanning uses repeated bounded windows (`scan->start(5, onScanComplete)`,
    restarted on every window end), not an indefinite scan
    (`scan->start(0, ...)`) - the latter hangs forever during
    `NimBLEDevice` init on this hardware/library version. Found by bisecting
    a silent boot hang with `Serial.println` breadcrumbs.
  - `NimBLEClient::connect()` itself has a bug in this library version: its
    retry loop for `BLE_HS_EBUSY` (scan not fully stopped yet) busy-spins
    `ble_gap_connect()` with no delay, which can take 30-40+ seconds of real
    time to clear on its own - every connect attempt looked hung until this
    resolved. [patch_nimble.py](patch_nimble.py) patches a small delay into
    that retry loop directly in `NimBLE-Arduino`'s installed source (it's a
    `lib_deps` dependency, not vendored under `lib/`, so the patch is
    reapplied automatically via `extra_scripts` after every install/update
    rather than living in a copy that could go stale). With the fix, connect
    now resolves in a few seconds.
- **Fan curve**: a continuous linear mapping from BPM to fan duty cycle,
  computed locally in [src/main.cpp](src/main.cpp) (`HRM_BASE_SPEED` /
  `HRM_MIN_BPM` / `HRM_MAX_BPM` / `HRM_MAX_SPEED` in `config.h`) - the
  firmware-side equivalent of what `fan_speed.py` used to do for the
  power-based curve. Below `HRM_MIN_BPM` the fan turns off entirely rather
  than idling at `HRM_BASE_SPEED`.
- **RGB LED**: published to the same Tasmota MQTT topics
  `settings.py`/`run.py` used to drive from Zwift power
  (`MQTT_ENABLE_ALL_TOPIC` / `MQTT_DIMMER_TOPIC` / `MQTT_BASE_COLOR_TOPIC`),
  now computed from HR zones instead (`HR_ZONE1_MIN`..`HR_ZONE5_MIN` in
  `config.h`), reusing the exact same 6-color palette
  [power_to_color.py](../../power_to_color.py) used for power zones
  (grey below zone 1, then blue/green/yellow/orange/tomato for Z1-Z5). The
  LED stays on (grey) whenever the strap is connected, even at rest -
  mirroring how the old power-driven LED stayed lit at 0W while "online" -
  and only publishes when the color actually changes, to avoid spamming
  MQTT on every BLE notification (arrives roughly once a second).
- **Safety**: the BLE link itself is the fan's kill switch - no connection,
  a stale reading, or BPM below `HRM_MIN_BPM` forces it off immediately.
  The LED additionally has an MQTT Last Will on `MQTT_ENABLE_ALL_TOPIC`
  (`connectMqtt()` in `main.cpp`), so if this ESP32 crashes/loses power
  without disconnecting cleanly, the broker turns the LED off automatically
  rather than leaving it stuck on the last color shown.
- **AC dimming**: zero-cross phase-angle approach via the vendored
  [RBDdimmer](lib/RBDdimmer) library, with fixes on top of upstream:
  - A software debounce in `isr_ext()` (see [include/zc_diag.h](include/zc_diag.h))
    that ignores zero-cross triggers arriving less than `ZC_DEBOUNCE_US`
    apart - measured electrical bounce/noise on the zero-cross signal
    (6-600us apart) was jittering the phase-cut angle cycle to cycle.
  - A widened TRIAC gate pulse (`pulseWidth`, ~350-375us instead of
    ~90us) - too short a pulse fired very close to the zero-cross
    (near-100% power) could fail to latch against an inductive motor
    load's slower current rise, causing intermittent skipped half-cycles.
  - Even with both fixes, motors with their own manual speed switch
    (Low/Mid/High) can still "brake"/stall on some switch positions above a
    certain duty - measured live on this fan's High position, hence
    `HRM_MAX_SPEED` capped at 85 rather than 100. Re-measure if the switch
    position or fan changes; see the comment above `HRM_MAX_SPEED` in
    `config.h`.
- **Startup ramp**: `updateFanRamp()` in `main.cpp` steps the applied power
  toward the target at ~40%/s instead of jumping straight to it - an abrupt
  jump to high power made the motor start with a loud stutter before
  catching.
- **Status telemetry**: current BPM/fan speed/connection state are
  published to `MQTT_STATUS_TOPIC` every few seconds for monitoring. WiFi
  is retried in the background if unavailable at boot or dropped later;
  the fan keeps working regardless (BLE control is independent of it), but
  the RGB LED needs it since Tasmota only speaks MQTT.

## Wiring (ESP32-WROOM <-> RobotDyn AC Dimmer module)

| ESP32 pin      | Dimmer module pin |
|----------------|--------------------|
| 3V3            | VCC                |
| GND            | GND                |
| GPIO26 (D26)   | PSM (gate signal)  |
| GPIO27 (D27)   | Z-C (zero-cross)   |

The fan is wired to the dimmer module's AC load output in series with mains,
exactly as the module's own documentation describes.

## Status LEDs (onboard, not the RGB strip)

Two low-voltage indicator LEDs (regular 5mm LED + ~220-330 ohm resistor,
GPIO -> resistor -> anode -> cathode -> GND):

| ESP32 pin     | Purpose   | Behavior                                                                 |
|---------------|-----------|---------------------------------------------------------------------------|
| GPIO32 (D32)  | Status    | Blinks (~1.25 Hz) while scanning/connecting to the HRM strap; solid ON once a fresh heart rate reading is coming in |
| GPIO33 (D33)  | Fan speed | Off while the fan is disabled; otherwise blinks at a rate proportional to fan speed - slow (~0.5 Hz) at 0-10%, fast (~8 Hz) at 90-100% |

## Configure

`include/config.h` is gitignored (it holds real credentials). Copy
[include/config.h.example](include/config.h.example) to `include/config.h`
and fill in:

- `WIFI_SSID`/`WIFI_PASSWORD` and `MQTT_HOST`/`MQTT_LOGIN`/`MQTT_PASSWORD` -
  required for the RGB LED, optional for the fan
- `HRM_MAC_ADDRESS` once you know your strap's BLE address (optional but
  recommended - leave empty to accept the first Heart Rate Service found)
- `HRM_BASE_SPEED`/`HRM_MIN_BPM`/`HRM_MAX_BPM`/`HRM_MAX_SPEED` - tune these
  to your actual riding HR range and fan's safe ceiling
- `HR_ZONE1_MIN`..`HR_ZONE5_MIN` - your actual HR zone boundaries, for the
  LED color

Also make sure `run.py` on the Raspberry Pi isn't also publishing to the
same LED topics (`sudo systemctl stop zwiftlight && sudo systemctl disable
zwiftlight` if it was previously running as a service) - both writing to
`MQTT_BASE_COLOR_TOPIC` would fight each other.

## Build & flash

Requires [PlatformIO](https://platformio.org/). The programming port is
preconfigured to `COM4`.

```
pio run -t upload
pio device monitor
```
