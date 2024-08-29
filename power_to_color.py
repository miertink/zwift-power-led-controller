class PowerToColor:
    def __init__(self, thresholds, deadband, overrun_limit):
        """
        Initialize the LevelController with thresholds, deadband, and overrun_limit.

        :param thresholds: List of threshold values for the levels (ascending order).
        :param deadband: Deadband value to prevent oscillation between levels.
        :param overrun_limit: Value beyond which the system should handle overrun.
        """
        self.thresholds = thresholds
        self.deadband = deadband
        self.overrun_limit = overrun_limit
        self.current_level = 0

    def get_level(self, value):
        """
        Determine the level based on the input value, considering deadband and overrun.

        :param value: The input value to be evaluated.
        :return: The current level.
        """
        if value > self.overrun_limit:
            # Handle overrun condition
            print("Overrun detected! Input exceeds limit.")
            self.current_level = len(self.thresholds) + 1  # Assign an overrun level (e.g., 6)
        else:
            # Normal operation considering deadband
            for i, threshold in enumerate(self.thresholds):
                if value < threshold - self.deadband:
                    self.current_level = i
                    break
                elif value >= threshold + self.deadband:
                    self.current_level = i + 1

        return self.current_level

    def switch_output(self, value):
        """
        Switch output based on the determined level.

        :param value: The input value to be evaluated.
        """
        level = self.get_level(value)
        print(f"Value: {value} | Current Level: {level}")

        if level == 0:
            self.output_level_1()
        elif level == 1:
            self.output_level_2()
        elif level == 2:
            self.output_level_3()
        elif level == 3:
            self.output_level_4()
        elif level == 4:
            self.output_level_5()
        elif level == 5:
            self.output_level_6()
        else:
            print("Invalid level!")

    def output_level_1(self):
        print("D3D3D3")

    def output_level_2(self):
        print("0000FF")

    def output_level_3(self):
        print("00FF00")

    def output_level_4(self):
        print("FFFF00")

    def output_level_5(self):
        print("FFA07A")

    def output_level_6(self):
        print("FF6347")