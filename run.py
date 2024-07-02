import logging
import colorsys
import time
import json
import numpy as np
from zwift import Client
from paho.mqtt import client as mqtt
from settings import *
from ringbuffer import RingBuffer


# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants and configurations
MQTT_CONNECT_RETRY_INTERVAL = 5  # seconds
MAX_RETRY_ATTEMPTS = 3  # Number of retry attempts
BUFFER_SIZE = 3  # Ring buffer size that acts as weight factor to smooth cycling power oscilation
MQTT_ENABLE_ALL_TOPIC = "cmnd/Zwift/led_enableAll"
MQTT_DIMMER_TOPIC = "cmnd/Zwift/led_dimmer"
MQTT_BASE_COLOR_TOPIC = "cmnd/Zwift/led_basecolor_rgb"
MQTT_INFO_TOPIC = "Zwift/user_info"


def setup_mqtt():
    """Setup and configure the MQTT client."""
    retry_attempts = 0
    mqtt_client = None

    while retry_attempts < MAX_RETRY_ATTEMPTS:
        try:
            mqtt_client = mqtt.Client(protocol=mqtt.MQTTv31)
            mqtt_client.username_pw_set(mqtt_login, mqtt_pw)
            mqtt_client.will_set(mqtt_topic_will, payload="Offline", retain=True)
            mqtt_client.connect(mqtt_host_name)
            mqtt_client.publish(mqtt_topic_will, payload="Online", retain=True)
            mqtt_client.publish(mqtt_topic, "Starting")
            logger.info("MQTT client connected successfully")
            return mqtt_client
        except Exception as e:
            logger.error(f"Error setting up MQTT client: {e}")
            retry_attempts += 1
            logger.info(f"Retry attempt {retry_attempts} in {MQTT_CONNECT_RETRY_INTERVAL} seconds...")
            time.sleep(MQTT_CONNECT_RETRY_INTERVAL)

    logger.error("Maximum retry attempts reached. MQTT client setup failed.")
    raise Exception("MQTT client setup failed after multiple retries.")


def find_player_by_id(data, player_id):
    """Check if player_id exists in data."""
    return any(friend['playerId'] == player_id for friend in data['friendsInWorld'])


def get_user_profile(client):
    """Retrieve user profile information from Zwift."""
    try:
        profile = client.get_profile()
        user_profile = profile.profile
        return user_profile["ftp"], user_profile["firstName"]
    except Exception as e:
        logger.error(f"Error retrieving user profile: {e}")
        raise


def convert_to_rgb(minimum, maximum, value):
    """Convert a value to a color using the color wheel in counter-clockwise direction."""
    value = np.clip(value, minimum, maximum)
    ratio = (value - minimum) / (maximum - minimum)
    hue = (0.8 - ratio) * 360
    rgb = colorsys.hsv_to_rgb(hue / 360, 1.0, 1.0)
    return [int(x * 255) for x in rgb]


def publish_status(mqtt_client, topic, payload):
    """Publish status to the MQTT broker."""
    mqtt_client.publish(topic, payload, retain=False)


def main():
    # Attempt to set up MQTT client
    try:
        mqtt_client = setup_mqtt()
    except Exception as e:
        logger.error(f"Failed to set up MQTT client: {e}")
        return

    # Zwift client setup
    client = Client(username, password)
    world = client.get_world(1)
    allplayers = world.players
    logger.info(f'Trying to find player {player_id}')

    user_found = find_player_by_id(allplayers, player_id)
    if not user_found:
        logger.error("User not found")
        time.sleep(MQTT_CONNECT_RETRY_INTERVAL)
        return

    # Get user profile
    try:
        ftp_user_profile, first_name = get_user_profile(client)
        user_zone7 = int(ftp_user_profile * 1.5)
        logger.info(f'FTP: {ftp_user_profile}, Zone 7: {user_zone7}')
    except Exception as e:
        logger.error(f"Error retrieving user profile: {e}")
        return

    ring_buffer = RingBuffer(BUFFER_SIZE)

    while True:
        try:
            mqtt_client.loop_start()
            error_count = 0
            online = False

            while not online and user_found:
                try:
                    world.player_status(player_id)
                    online = True
                    logger.info(f'{player_id}, {first_name} appears to be online, lets retrieve activity data - trying..')
                    publish_status(mqtt_client, MQTT_ENABLE_ALL_TOPIC, 1)
                    time.sleep(2)
                except Exception as e:
                    error_count += 1
                    logger.error(
                        f'{player_id} appears to be offline or error while retrieving player status - trying.. {error_count}')
                    logger.error(f'Error: {e}')
                    time.sleep(MQTT_CONNECT_RETRY_INTERVAL)
                    publish_status(mqtt_client, MQTT_ENABLE_ALL_TOPIC, 0)

            while online:
                try:
                    status = world.player_status(player_id)
                    if status.sport == 0:
                        ring_buffer.add(status.power)
                        power_avg = int(np.mean(ring_buffer.get()))
                        led_color = convert_to_rgb(0, user_zone7, power_avg)
                        led_color_hex = ''.join(f'{c:02x}' for c in led_color)
                        msg_dict = {'is_online': 1,
                                    'sport': 'cycling',
                                    'hr': status.heartrate,
                                    'power': status.power,
                                    'power average': power_avg,
                                    'speed': float("{:.2f}".format(float(status.speed) / 1000000.0))}
                        logger.info(msg_dict)
                        publish_status(mqtt_client, MQTT_INFO_TOPIC, payload=json.dumps(msg_dict))
                        publish_status(mqtt_client, MQTT_DIMMER_TOPIC, 100)
                        publish_status(mqtt_client, MQTT_BASE_COLOR_TOPIC, led_color_hex)
                        time.sleep(4)  # Zwift does not allow shorter request cycle
                except Exception as e:
                    online = False
                    logger.error(f'Error: {e}')

            mqtt_client.loop_stop()

        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f'Unhandled exception: {e}')
            time.sleep(MQTT_CONNECT_RETRY_INTERVAL)


if __name__ == "__main__":
    main()
