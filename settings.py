#  ZWIFT
"""Check https://zwiftinsider.com/find-zwift-id/"""
USERNAME = 'yourusername'
PASSWORD = 'yourpassword'
PLAYER_ID = yourid

# MQTT Enable
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
