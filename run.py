from zwift import Client
from paho.mqtt import client as mqtt
from power_to_color import PowerToColor
from settings import *
import logging
import time
import json

# Set up logging
logging.basicConfig(level=logging.INFO)
# Logging.basicConfig(filename='/var/log/ZwiftLight.log', filemode='w', level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_mqtt():
    """Setup and configure the MQTT client."""
    try:
        mqtt_client = mqtt.Client(protocol=mqtt.MQTTv5)
        mqtt_client.username_pw_set(MQTT_LOGIN, MQTT_PW)
        mqtt_client.will_set(MQTT_ENABLE_ALL_TOPIC, payload="Offline", retain=True)
        mqtt_client.connect(MQTT_HOST_NAME)
        mqtt_client.publish(MQTT_ENABLE_ALL_TOPIC, payload="Online", retain=True)
        logger.info(f"MQTT client successfully connected to {MQTT_HOST_NAME}")
        return mqtt_client
    except:
        logger.error(f"MQTT client could not connect to {MQTT_HOST_NAME}, check settings.py")
        exit()


def publish_status(mqtt_client, topic, payload):
    """Publish status to the MQTT broker."""
    if USE_MQTT:
        mqtt_client.publish(topic, payload, retain=False)


def main():
    mqtt_client = None

    # If MQTT is enabled, set up the MQTT client
    if USE_MQTT:
        mqtt_client = setup_mqtt()

    # Zwift client setup
    """Login into Zwift and find if user is existent"""
    client = Client(USERNAME, PASSWORD)
    world = client.get_world(1)

    # Get user profile
    """Retrieve user profile information from Zwift and set user cycling power zone 7 (Z7)."""
    try:
        profile = client.get_profile()
        user_profile = profile.profile
        ftp_user_profile = int(user_profile["ftp"])
        logger.info(f'Login {PLAYER_ID}, user {USERNAME}, ftp {ftp_user_profile} - successfully done')
    except:
        logger.error(f'Error retrieving user profile, please check username, password and PLAYER_ID in settings.py')
        exit()

    # Some setup before the main routine
    """Set Z7 cycling power zone, cycling power smooth factor, and set some variables."""
    online = False
    error_count = 0

    # Main routine
    """Check online activity and publish into MQTT broker if enabled"""
    while not online:
        if USE_MQTT:
            mqtt_client.loop_start()

        try:
            world.player_status(PLAYER_ID)
            online = True
            error_count = 0
            logger.info(f'{PLAYER_ID} appears to be online, lets retrieve activity data - trying..')
            if USE_MQTT:
                publish_status(mqtt_client, MQTT_ENABLE_ALL_TOPIC, 1)
                publish_status(mqtt_client, MQTT_DIMMER_TOPIC, 100)
        except:
            online = False
            error_count += 1
            logger.info(f'{PLAYER_ID} appears to be offline - trying.. {error_count}')
            if USE_MQTT:
                publish_status(mqtt_client, MQTT_ENABLE_ALL_TOPIC, 0)
        time.sleep(MQTT_CONNECT_RETRY_INTERVAL)

        while online:
            try:
                status = world.player_status(PLAYER_ID)
                if status.sport == 0:
                    power_percentage = round(status.power / ftp_user_profile * 100)
                    p2z = PowerToColor(THRESHOLDS, DEADBAND, OVERRUN_LIMIT)
                    led_color_hex = p2z.switch_output(power_percentage)
                    msg_dict = {
                        'is_online': 1,
                        'sport': 'cycling',
                        'hr': status.heartrate,
                        'power': status.power,
                        'power percentage': power_percentage,
                        'rbg output color': led_color_hex,
                        'speed': float("{:.2f}".format(float(status.speed) / 1000000.0))
                    }
                    logger.info(msg_dict)

                    if USE_MQTT:
                        publish_status(mqtt_client, MQTT_BASE_COLOR_TOPIC, led_color_hex)
                        publish_status(mqtt_client, MQTT_INFO_TOPIC, payload=json.dumps(msg_dict))
            except:
                online = False
                logger.info(f'{PLAYER_ID} appears to have gone offline')

            time.sleep(MQTT_ZWIFT_REQUEST_INTERNAL)

        if USE_MQTT:
            mqtt_client.loop_stop()
        time.sleep(MQTT_CONNECT_RETRY_INTERVAL)


if __name__ == "__main__":
    main()
