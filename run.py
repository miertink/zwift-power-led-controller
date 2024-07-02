#!/bin/python

# imports
from zwift import Client
from ringbuffer import RingBuffer
from paho.mqtt import client as mqtt
from settings import *
import numpy as np
import time
import json

if __name__ == "__main__":

    #mqtt setup
    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    mqtt_client.username_pw_set(mqtt_login, mqtt_pw)
    mqtt_client.will_set(mqtt_topic_will, payload="Offline", retain=True)
    mqtt_client.connect(mqtt_host_name)
    mqtt_client.publish(mqtt_topic_will, payload="Online", retain=True)
    mqtt_client.publish(mqtt_topic, "Starting")

    #set ringbuffer size (weight factor)
    x = RingBuffer(3)

    #get if user is online on zwift
    client = Client(username, password)
    world = client.get_world(1)
    print('trying to find ' + str(player_id))

    #get first name and ftp from user account
    profile = client.get_profile()
    user_profile = profile.profile
    ftp_user_profile = (user_profile["ftp"])
    firstName = (user_profile["firstName"])

    #set led power (0-100) corresponding interval from user ftp*150%
    led_interval = [0, 100]
    user_interval = [0, ftp_user_profile*1.5]

# main loop
while True:
    error = 0
    online = False
    mqtt_client.loop_start()
    while not online:
        try:
            status = world.player_status(player_id)
            error = 0
            online = True
            print(str(player_id) + ', ' + str(firstName) + ', appears to be online, check if cycling or running, ftp: ' + str(ftp_user_profile))
            mqtt_client.publish("cmnd/Zwift/led_enableAll", 1, retain=False)
            time.sleep(2)
        except:
            error += 1
            online = False
            print(str(player_id) + ' appears to be offline or error while retrieving player status - trying..' + str(
                error))
            time.sleep(5)
            mqtt_client.publish("cmnd/Zwift/led_enableAll", 0, retain=False)
    while online:
        try:
            status = world.player_status(player_id)
            if status.sport == 0:
                msg_dict = {'is_online': 1, 'sport': 'cycling', 'hr': status.heartrate, 'power': status.power,
                            'speed': float("{:.2f}".format(float(status.speed) / 1000000.0))}
            mqtt_client.publish(mqtt_topic, payload=json.dumps(msg_dict), retain=False)
            power_equivalent = round(np.interp(status.power, user_interval, led_interval))
            mqtt_client.publish("cmnd/Zwift/led_dimmer", power_equivalent, retain=False)
            x.add(power_equivalent)
            print(msg_dict)
            print('mqtt led dim output = {:0.0f}   |  '.format(np.mean(x.get())), x.get())
            time.sleep(4)
        except:
            online = False
    mqtt_client.loop_stop()
