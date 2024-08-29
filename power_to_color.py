"""
*Input* cycling power in percentage of user ftp as input
*Return* RBG value accordant to ZWIFT power zone color definition
with threshold parameter to prevents oscillation near the thresholds
"""
class PowerToColor:
    def __init__(self, thresholds, deadband, overrun_limit):
        self.thresholds = thresholds
        self.deadband = deadband
        self.overrun_limit = overrun_limit

    def switch_output(self, value):
        if value > self.overrun_limit:
            return "FF6347"  # Overrun level (Tomato)

        for i, threshold in enumerate(self.thresholds):
            if value < threshold - self.deadband:
                return self.get_color(i)
            elif value >= self.thresholds[-1] + self.deadband:
                return self.get_color(len(self.thresholds))

        return self.get_color(len(self.thresholds) - 1)

    def get_color(self, level):
        colors = [
            "D3D3D3",  # Light Grey
            "0000FF",  # Blue
            "00FF00",  # Green
            "FFFF00",  # Yellow
            "FFA500",  # Orange
            "FF6347",  # Tomato
        ]
        return colors[min(level, len(colors) - 1)]
