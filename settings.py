#  ZWIFT
"""Check https://zwiftinsider.com/find-zwift-id/"""
USERNAME = 'miertink.vix@hotmail.com'
PASSWORD = '***REDACTED-ROTATED-PASSWORD***'
PLAYER_ID = 2061115
# PLAYER_ID = 5097474

#  MQTTT BROKER
MQTT_HOST_NAME = "192.168.68.10"
MQTT_CLIENT_NAME = "MieRTinK"
MQTT_LOGIN = "tht"
MQTT_PW = "***REDACTED-ROTATED-PASSWORD***"

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
POWER_ZONES = [
    ((0, 59), "D3D3D3"),
    ((60, 75), "0000FF"),
    ((76, 89), "00FF00"),
    ((90, 104), "FFFF00"),
    ((105, 118), "FFA07A"),
    ((119, 1000), "FF6347")
]

# MISC
HYSTERESIS = 5
last_color = None