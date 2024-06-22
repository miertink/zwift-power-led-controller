#!/bin/python

from zwift import Client
from paho.mqtt import client as mqtt

import time
import json

# I know... this is not elegant!
from settings import *

#OFFLINE_MSG = json.dumps({'is_online': 0, 'hr': 0, 'power': 0, 'speed': 0.0})

if __name__ == "__main__":
    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    mqtt_client.username_pw_set(mqtt_login, mqtt_pw)
    mqtt_client.will_set(mqtt_topic_will, payload="Offline", retain=True)
    mqtt_client.connect(mqtt_host_name)
    mqtt_client.publish(mqtt_topic_will, payload="Online", retain=True)
    mqtt_client.publish(mqtt_topic, "Starting")

    client = Client(username, password)
    world = client.get_world(1)
    print('trying to find ' + str(player_id))

while True:
    error = 0
    online = False
    mqtt_client.loop_start()
    while not online:
        try:
            status = world.player_status(player_id)
            error = 0
            online = True
            print(str(player_id) + ' appears to be online, check if cycling or running')
            time.sleep(2)
        except:
            error += 1
            online = False
            print(str(player_id) + ' appears to be offline or error while retrieving player status - trying..' + str(
                error))
            time.sleep(5)
    while online:
        try:
            status = world.player_status(player_id)
            if status.sport == 0:
                msg_dict = {'is_online': 1, 'sport': 'cycling', 'hr': status.heartrate, 'power': status.power,
                            'speed': float("{:.2f}".format(float(status.speed) / 1000000.0))}
            elif status.sport == 1:
                msg_dict = {'is_online': 1, 'sport': 'running', 'hr': status.heartrate,
                            'speed': float("{:.2f}".format(float(status.speed) / 1000000.0))}
            mqtt_client.publish(mqtt_topic, payload=json.dumps(msg_dict), retain=False)
            mqtt_client.publish("/cmnd/miertink_e20fc4/power", status.power, retain=False)
            print(msg_dict)
            time.sleep(4)
        except:
            online = False
    mqtt_client.loop_stop()
