# Fan AC Dimmer + RGB LED Firmware (ESP32-WROOM)

Standalone ESP32-WROOM firmware that reads live heart rate over Bluetooth
Low Energy from a chest strap (e.g. Garmin HRM 200) and uses it to drive
two things directly, with no other device or service involved:

- an AC dimmer controlling a fan's speed
- an RGB LED strip's color, via MQTT to a Tasmota-flashed controller

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
- **Fan curve**: a continuous linear mapping from BPM to fan duty cycle,
  computed locally in [src/main.cpp](src/main.cpp) (`HRM_BASE_SPEED` /
  `HRM_MIN_BPM` / `HRM_MAX_BPM` / `HRM_MAX_SPEED` in `config.h`). Below
  `HRM_MIN_BPM` the fan turns off entirely rather than idling at
  `HRM_BASE_SPEED`; `HRM_HYSTERESIS_BPM` keeps it from clicking on/off when
  BPM hovers right around that threshold.
- **Remote on/off**: an optional Home Assistant MQTT switch
  (`MQTT_FAN_POWER_COMMAND_TOPIC` / `MQTT_FAN_POWER_STATE_TOPIC` in
  `config.h`) overrides the fan on top of the BPM curve - see "Home
  Assistant" below. Defaults to ON, so the fan works normally if it's never
  configured.
- **RGB LED**: published over MQTT to a Tasmota RGB controller
  (`MQTT_ENABLE_ALL_TOPIC` / `MQTT_DIMMER_TOPIC` / `MQTT_BASE_COLOR_TOPIC`
  in `config.h`), colored by heart-rate zone (`HR_ZONE1_MIN`..`HR_ZONE5_MIN`
  in `config.h`): grey at rest, then blue/green/yellow/orange/tomato for
  zones 1-5. The LED stays on (grey) whenever the strap is connected, even
  at rest, and only publishes when the color actually changes, to avoid
  spamming MQTT on every BLE notification (arrives roughly once a second).
- **Safety**: the BLE link itself is the fan's kill switch - no connection,
  a stale reading, or BPM below `HRM_MIN_BPM` forces it off immediately.
  The LED additionally has an MQTT Last Will on `MQTT_ENABLE_ALL_TOPIC`, so
  if this ESP32 crashes/loses power without disconnecting cleanly, the
  broker turns the LED off automatically rather than leaving it stuck on
  the last color shown.
- **AC dimming**: zero-cross phase-angle approach via the vendored
  [RBDdimmer](lib/RBDdimmer) library, with fixes on top of upstream (see
  "Known issues & tuning" below).
- **Status telemetry**: current BPM/fan speed/connection state are
  published to `MQTT_STATUS_TOPIC` every few seconds (BPM reports as 0 once
  the strap is disconnected/stale, rather than freezing on the last
  reading), and logged to the serial monitor every 2 seconds. WiFi is
  retried in the background if unavailable at boot or dropped later; the
  fan keeps working regardless (BLE control is independent of it), but the
  RGB LED needs it since Tasmota only speaks MQTT.

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
- `HRM_BASE_SPEED`/`HRM_MIN_BPM`/`HRM_MAX_BPM`/`HRM_MAX_SPEED`/
  `HRM_HYSTERESIS_BPM` - tune these to your actual riding HR range and
  fan's safe ceiling
- `HR_ZONE1_MIN`..`HR_ZONE5_MIN` - your actual HR zone boundaries, for the
  LED color

## Build & flash

Requires [PlatformIO](https://platformio.org/). The programming port is
preconfigured to `COM4`.

```
pio run -t upload
pio device monitor
```

## Home Assistant

Two things can be exposed to Home Assistant over MQTT - a switch to
override the fan on/off, and sensors reading `MQTT_STATUS_TOPIC`'s BPM/fan
speed. Add to `configuration.yaml`:

```yaml
mqtt:
  switch:
    - name: "Fan Dimmer"
      unique_id: fan_dimmer_power
      command_topic: "cmnd/FanDimmer/power"
      state_topic: "stat/FanDimmer/power"
      payload_on: "ON"
      payload_off: "OFF"
      optimistic: false
      retain: false # don't persist OFF - the fan must default ON if HA goes unused

  sensor:
    - name: "Fan Dimmer BPM"
      unique_id: fan_dimmer_bpm
      state_topic: "tele/FanDimmer/status"
      value_template: "{{ value_json.bpm }}"
      unit_of_measurement: "bpm"
      icon: mdi:heart-pulse
      state_class: measurement

    - name: "Fan Dimmer Speed"
      unique_id: fan_dimmer_speed
      state_topic: "tele/FanDimmer/status"
      value_template: "{{ value_json.fan_speed }}"
      unit_of_measurement: "%"
      icon: mdi:fan
      state_class: measurement
```

Then reload MQTT (or restart Home Assistant). The switch is
non-optimistic - it only flips once the ESP32 confirms the change on
`stat/FanDimmer/power` - and its command isn't retained, so a reboot with
Home Assistant unavailable/unconfigured always leaves the fan on its
normal BPM-driven behavior rather than stuck off.

## Known issues & tuning

- **Indefinite BLE scan hangs on boot**: `scan->start(0, ...)` ("scan
  forever") never returns on this hardware/library version. Worked around
  by scanning in repeated bounded windows instead
  (`scan->start(5, onScanComplete)`, restarted on every window end).
- **`NimBLEClient::connect()` can take 30-40+ seconds**: its retry loop for
  `BLE_HS_EBUSY` (scan not fully stopped yet) busy-spins `ble_gap_connect()`
  with no delay, which can take dozens of retries and tens of seconds to
  clear on its own - every connect attempt looked hung until this was
  found. [patch_nimble.py](patch_nimble.py) patches a small delay into that
  retry loop directly in `NimBLE-Arduino`'s installed source (it's a
  `lib_deps` dependency, not vendored under `lib/`, so the patch is
  reapplied automatically via `extra_scripts` after every install/update
  rather than living in a copy that could go stale). With the fix, connect
  resolves in a few seconds.
- **Zero-cross bounce/noise**: a software debounce in `isr_ext()` (see
  [include/zc_diag.h](include/zc_diag.h)) ignores zero-cross triggers
  arriving less than `ZC_DEBOUNCE_US` apart - measured electrical
  bounce/noise on the zero-cross signal (6-600us apart) was jittering the
  phase-cut angle cycle to cycle.
- **TRIAC latching near full power**: a widened TRIAC gate pulse
  (`pulseWidth`, ~350-375us instead of ~90us) - too short a pulse fired
  very close to the zero-cross (near-100% power) could fail to latch
  against an inductive motor load's slower current rise, causing
  intermittent skipped half-cycles.
- **Fan braking on its own speed switch**: even with both fixes above,
  motors with their own manual speed switch (Low/Mid/High) can still
  "brake"/stall on some switch positions above a certain duty - measured
  live on this fan's High position, hence `HRM_MAX_SPEED` capped at 85
  rather than 100. Re-measure if the switch position or fan changes; see
  the comment above `HRM_MAX_SPEED` in `config.h`.
