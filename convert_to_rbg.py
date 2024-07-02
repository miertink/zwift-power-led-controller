import numpy as np
def Convert_to_rgb(minimum, maximum, value):
    value = np.clip(value, minimum, maximum)
    minimum, maximum = float(minimum), float(maximum)
    ratio = 2 * (value-minimum) / (maximum - minimum)
    b = int(max(0, 255*(1 - ratio)))
    r = int(max(0, 255*(ratio - 1)))
    g = 255 - b - r
    return (r/255.0,g/255.0,b/255.0)