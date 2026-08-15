Import("env")

# NimBLE-Arduino's NimBLEClient::connect() busy-spins ble_gap_connect() with no delay
# while waiting for an in-progress scan to actually stop at the controller level
# (BLE_HS_EBUSY case in the do/while loop). Without a delay this can take dozens of
# retries and 30-40+ seconds of real time to clear on its own, making every BLE HRM
# connect attempt look hung. Patched in directly since this is a lib_deps-managed
# dependency (re-downloaded into .pio/libdeps, not vendored under lib/) - this script
# re-applies the fix after every library install/update so it isn't silently lost.
import os

TARGET = os.path.join(env.subst("$PROJECT_LIBDEPS_DIR"), env.subst("$PIOENV"),
                       "NimBLE-Arduino", "src", "NimBLEClient.cpp")

OLD = """            case BLE_HS_EBUSY:
                // Scan was still running, stop it and try again
                if (!NimBLEDevice::getScan()->stop()) {
                    rc = BLE_HS_EUNKNOWN;
                }
                break;"""

NEW = """            case BLE_HS_EBUSY:
                // Scan was still running, stop it and try again. stop() only requests
                // the stop at the controller level - without a delay here this loop
                // busy-spins calling ble_gap_connect() again before the controller has
                // actually finished stopping, which can take dozens of retries (and tens
                // of seconds of real time) to clear on its own.
                if (!NimBLEDevice::getScan()->stop()) {
                    rc = BLE_HS_EUNKNOWN;
                } else {
                    vTaskDelay(pdMS_TO_TICKS(20));
                }
                break;"""

if os.path.isfile(TARGET):
    with open(TARGET, "r") as f:
        content = f.read()
    if OLD in content:
        with open(TARGET, "w") as f:
            f.write(content.replace(OLD, NEW))
        print("patch_nimble.py: applied EBUSY-retry-delay patch to NimBLEClient.cpp")
    elif NEW in content:
        pass  # already patched
    else:
        print("patch_nimble.py: WARNING - NimBLEClient.cpp EBUSY case not found as expected, skipping patch")
