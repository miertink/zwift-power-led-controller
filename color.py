import matplotlib.colors as mcolors
import matplotlib.pyplot as plt

def get_hex_color(value, cmap_name='turbo'):
    """
    Returns a hex color code for a given value between 0 and 100 using a specified colormap.

    :param value: A number between 0 and 100.
    :param cmap_name: Name of the colormap to use (default is 'viridis').
    :return: Hex color code as a string.
    """
    # Ensure the value is within the range
    if value < 0 or value > 100:
        raise ValueError("Value must be between 0 and 100")

    # Normalize the value to the range [0, 1]
    norm_value = value / 100.0

    # Get the colormap
    cmap = plt.get_cmap(cmap_name)

    # Get the RGB value from the colormap
    rgb = cmap(norm_value)

    # Convert RGB to hex
    hex_color = mcolors.to_hex(rgb)

    return hex_color

# Example usage
value = 80
hex_color = get_hex_color(value)
print(f"The hex color for value {value} is {hex_color}")
