#!/bin/python

# Imports
from zwift import Client
from ringbuffer import RingBuffer
from convert_to_rbg import Convert_to_rgb
from paho.mqtt import client as mqtt
from settings import *
import numpy as np
import time
import json


def setup_mqtt():
    """Setup and configure the MQTT client."""
    client = mqtt.Client()
    client.username_pw_set(mqtt_login, mqtt_pw)
    client.will_set(mqtt_topic_will, payload="Offline", retain=True)
    client.connect(mqtt_host_name)
    client.publish(mqtt_topic_will, payload="Online", retain=True)
    client.publish(mqtt_topic, "Starting")
    return client


def get_user_profile(client):
    """Retrieve user profile information from Zwift."""
    profile = client.get_profile()
    user_profile = profile.profile
    return user_profile["ftp"], user_profile["firstName"]


def get_led_color(power, user_zone7):
    """Convert power to RGB color."""
    led_color = Convert_to_rgb(1, user_zone7, power)
    led_color = [format(int(x * 254), '02x') for x in led_color]
    return "".join(led_color)


def main():
    # MQTT setup
    mqtt_client = setup_mqtt()

    # Set ringbuffer size (weight factor)
    buffer_size = 3
    x = RingBuffer(buffer_size)

    # Zwift client setup
    client = Client(username, password)
    world = client.get_world(1)
    print(f'Trying to find player {player_id}')

    # Get first name and FTP from user account
    ftp_user_profile, first_name = get_user_profile(client)

    # Set LED power (0-100) corresponding interval from user FTP*150%
    user_zone7 = int(ftp_user_profile * 1.5)

    # Main loop
    while True:
        error = 0
        online = False
        mqtt_client.loop_start()
        while not online:
            try:
                status = world.player_status(player_id)
                online = True
                print(
                    f'{player_id}, {first_name}, appears to be online, check if cycling or running, FTP: {ftp_user_profile}')
                mqtt_client.publish("cmnd/Zwift/led_enableAll", 1, retain=False)
                time.sleep(2)
            except Exception as e:
                error += 1
                online = False
                print(f'{player_id} appears to be offline or error while retrieving player status - trying.. {error}')
                print(f'Error: {e}')
                time.sleep(5)
                mqtt_client.publish("cmnd/Zwift/led_enableAll", 0, retain=False)

        while online:
            try:
                status = world.player_status(player_id)
                if status.sport == 0:
                    msg_dict = {
                        'is_online': 1,
                        'sport': 'cycling',
                        'hr': status.heartrate,
                        'power': status.power,
                        'speed': float(f"{status.speed / 1000000.0:.2f}")
                    }
                    x.add(status.power)
                    led_color = get_led_color(status.power, user_zone7)
                    print(f'{msg_dict}, rbg: {led_color}')
                    mqtt_client.publish("cmnd/Zwift/led_dimmer", 100, retain=False)
                    mqtt_client.publish("cmnd/Zwift/led_basecolor_rgb", led_color, retain=False)
                    time.sleep(4)
            except Exception as e:
                online = False
                print(f'Error: {e}')
        mqtt_client.loop_stop()


if __name__ == "__main__":
    main()
