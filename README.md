# ZwiftLight

## Introduction:

There are already several code repositories available on GitHub that retrieve ZWIFT real-time user data and control devices like fans and lights. I’ve reused and enhanced some of these to create a version tailored specifically to my needs.

I recommend this project for individuals with some experience in Python, firmware flashing, networking, electronic and working with devices like ESP8266. Several configurations across different aspects are required, so a basic understanding in these areas will be helpful.

The color profile I’ve chosen closely matches the one ZWIFT uses in their power zone graphs.

## Requirements:

   - ZWIFT subscription
   - Smart Trainer
   - Computer to run this Python script (I suggest using a Raspberry Pi, which will likely be the same system hosting your MQTT broker)
   - MQTT broker with some basic configuration
   - RGB Light Strip and RGB LED Controller with MQTT support (I recommend flashing the RGB controller with TASMOTA or similar firmware)

I personally use a MAGICHOME controller, available on Aliexpress or similar shops, running TASMOTA firmware.
Initially, these MAGICHOME controllers had the ESP8266 chip, but recently, they have switched to the BL602 chip, more information can be found on the following link: https://github.com/esphome/feature-requests/issues/1049

My current setup uses the BL602-based controller, and below is an illustration showing the minimal configuration required to connect the controller to MQTT, as well as the configuration of the RGB module for the LED strip.

![tasmota_setup.gif](/icons/tasmota_setup.gif)

## How to Install:

   - Clone this Python repository to your computer.
   - Install the required libraries by running: 

    pip install -r requirements.txt

   - Update the settings.py file with your ZWIFT credentials, MQTT broker configuration, and the MQTT topics matching your LED controller device setup.
   - After configuring everything, just start *run.py* and you're ready to ride!

> [!TIP]
> I have added the following code to /etc/rc.local on my Raspberry Pi to automatically start ZwiftLight upon boot:

```
# ZwiftLight
/home/admin/python-projects/ZwiftLight/.venv/bin/python3 /home/admin/python-projects/ZwiftLight/run.py
```

## How it works (very short):
    
   - The python code first connects to your MQTT broker.
   - It then connects to ZWIFT using 'zwift-client' API, retrieves your FTP (Functional Threshold Power) from your profile, and calculates your power zones.
   - Once you start riding in Watopia, the API requests your real-time data every 4 deconds and begins publishing MQTT data to the RGB controller. The led light switches on and changes colors according to your current riding power output.

Unfortunately, there will always be a small delay between your riding power and the corresponding RGB color change. This is due to ZWIFT’s API limitations, which restrict the request rate (4-5 sec).

## Ride On !!



Big thanks to @jsmits who wrote the zwift-client IPA.

https://github.com/jsmits/zwift-client
