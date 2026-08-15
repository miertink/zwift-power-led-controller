Import("env")

# NimBLEClient::connect() busy-spins with no delay while waiting for the scan to actually
# stop, taking 30-40+ seconds to clear on its own. This re-applies a delay fix to the
# installed (not vendored) NimBLE-Arduino source after every lib install/update.
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
                // Scan was still running, stop it and try again - delay so the
                // controller has time to actually finish stopping before the retry.
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
