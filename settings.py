#  ZWIFT
"""Check https://zwiftinsider.com/find-zwift-id/"""
USERNAME = 'yourusername'
PASSWORD = 'yourpassword'
PLAYER_ID = yourid

#  MQTT Enable (in case you want to see how to works without using MQTT, set USE_MQTT = False)
USE_MQTT = True

#  MQTTT BROKER
MQTT_HOST_NAME = "ipofyourmqttbroker"
MQTT_CLIENT_NAME = "clientname"
MQTT_LOGIN = "user"
MQTT_PW = "password"

#  CONSTANTS AND CONFIGURATIONS
MQTT_CONNECT_RETRY_INTERVAL = 5  # Seconds
MQTT_ZWIFT_REQUEST_INTERNAL = 4  # Seconds -> Zwift does not allow shorter request cycle
BUFFER_SIZE = 3  # Ring buffer size that acts as weight factor to smooth out cycling power oscilation
# Short keepalive so that if this script crashes/loses power without disconnecting cleanly,
# the broker notices and fires the Last Will (MQTT_ENABLE_ALL_TOPIC -> Offline) quickly -
# the fan-dimmer firmware treats that as a kill switch and stops the fan.
MQTT_KEEPALIVE_SECONDS = 15

#  MQTT TOPICS - should be set acc. to led-controller-device (see documentation from device)
MQTT_ENABLE_ALL_TOPIC = "cmnd/Zwift/led_enableAll"
MQTT_DIMMER_TOPIC = "cmnd/Zwift/led_dimmer"
MQTT_BASE_COLOR_TOPIC = "cmnd/Zwift/led_basecolor_rgb"
MQTT_INFO_TOPIC = "Zwift/user_info"

#  POWER ZONES & COLORS (Zwift Standard)
# Example usage
THRESHOLDS = [59, 75, 89, 104, 118]  # Define thresholds for 5 levels
DEADBAND = 5                         # Define deadband to avoid oscillation around thresholds
OVERRUN_LIMIT = 1000                 # Define overrun limit

#  FAN (AC DIMMER) CONTROL - should be set acc. to fan-dimmer device (see firmware/fan-dimmer)
MQTT_FAN_ENABLE_TOPIC = "cmnd/Fan/power"  # ON/OFF fan dimmer, mirrors MQTT_ENABLE_ALL_TOPIC
MQTT_FAN_SPEED_TOPIC = "cmnd/Fan/speed"   # Fan duty cycle 0-100, sent every ride update

# Which telemetry drives the fan speed. Only "power" is implemented today;
# add a new FanSpeedStrategy subclass in fan_speed.py + a branch in
# get_fan_speed_strategy() to support e.g. heart rate or virtual speed later.
FAN_SOURCE = "power"
FAN_BASE_SPEED = 50             # Fan duty cycle (%) at/below FAN_MIN_POWER_WATTS - idle baseline airflow
FAN_MIN_POWER_WATTS = 50       # Watts at/below which the fan sits at FAN_BASE_SPEED
FAN_MAX_POWER_WATTS = 240       # Watts at/above which the fan sits at FAN_MAX_SPEED
FAN_MAX_SPEED = 100             # Fan duty cycle (%) at/above FAN_MAX_POWER_WATTS
# Time constant (seconds) of the exponential smoothing applied to the fan speed: after this many
# seconds the fan has covered ~63% of the way to a new target speed, ~95% after 3x this value.
# Higher = smoother/slower to react, lower = snappier but closer to raw power swings.
FAN_SMOOTHING_SECONDS = 10
