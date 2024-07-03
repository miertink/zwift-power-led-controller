import time
import threading
import colorsys

# Function to convert hex color to RGB tuple
def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

# Function to convert RGB tuple to hex color
def rgb_to_hex(rgb_color):
    return '#{:02x}{:02x}{:02x}'.format(*rgb_color)

# Function to interpolate between two RGB colors
def interpolate_color(start_rgb, end_rgb, steps):
    return [
        (
            int(start_rgb[0] + (end_rgb[0] - start_rgb[0]) * t / steps),
            int(start_rgb[1] + (end_rgb[1] - start_rgb[1]) * t / steps),
            int(start_rgb[2] + (end_rgb[2] - start_rgb[2]) * t / steps)
        )
        for t in range(steps + 1)
    ]

# Function to handle the smooth transition of led_color_hex
def smooth_transition(start_color, end_color, duration, steps=100):
    start_rgb = hex_to_rgb(start_color)
    end_rgb = hex_to_rgb(end_color)
    interpolated_colors = interpolate_color(start_rgb, end_rgb, steps)

    for color in interpolated_colors:
        led_color_hex = rgb_to_hex(color)
        publish_status(mqtt_client, MQTT_BASE_COLOR_TOPIC, led_color_hex)
        time.sleep(duration / steps)

# Thread target function
def led_transition_thread():
    while online:
        try:
            status = world.player_status(PLAYER_ID)
            if status.sport == 0:
                ring_buffer.add(status.power)
                power_avg = int(np.mean(ring_buffer.get()))
                led_color = convert_to_rgb(0, user_power_zone7, power_avg)
                led_color_hex = ''.join(f'{c:02x}' for c in led_color)
                msg_dict = {'is_online': 1,
                            'sport': 'cycling',
                            'hr': status.heartrate,
                            'power': status.power,
                            'power average': power_avg,
                            'speed': float("{:.2f}".format(float(status.speed) / 1000000.0))}
                logger.info(msg_dict)
                publish_status(mqtt_client, MQTT_BASE_COLOR_TOPIC, led_color_hex)
                publish_status(mqtt_client, MQTT_INFO_TOPIC, payload=json.dumps(msg_dict))

                # Start a new thread for the smooth transition
                threading.Thread(target=smooth_transition, args=(current_color, led_color_hex, 1)).start()
                current_color = led_color_hex

        except:
            online = False
            logger.info(f'{PLAYER_ID} appears to have gone offline')
        time.sleep(MQTT_ZWIFT_REQUEST_INTERNAL)

# Initialize current color
current_color = '#000000'

# Start the LED transition thread
threading.Thread(target=led_transition_thread).start()
#..
