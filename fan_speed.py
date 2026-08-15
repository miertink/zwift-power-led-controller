"""
Turns live ride telemetry into a fan duty cycle (0-100), published to the
AC dimmer firmware over MQTT. The mapping is pluggable: FAN_SOURCE in
settings.py selects which FanSpeedStrategy drives the fan, so a new
telemetry source (heart rate, virtual speed, ...) can be added later by
implementing FanSpeedStrategy and registering it in get_fan_speed_strategy().
"""
import math
import time
from abc import ABC, abstractmethod

from settings import (
    FAN_SOURCE,
    FAN_BASE_SPEED,
    FAN_MIN_POWER_WATTS,
    FAN_MAX_POWER_WATTS,
    FAN_MAX_SPEED,
    FAN_SMOOTHING_SECONDS,
)


class FanSpeedStrategy(ABC):
    @abstractmethod
    def compute(self, status, ftp) -> int:
        """Return the fan duty cycle (0-100) for the given Zwift player status."""


class PowerBasedFanSpeed(FanSpeedStrategy):
    """Continuous (non-stepped) linear mapping from power (W) to fan duty cycle.

    The output ramps toward the target speed via an exponential moving average with
    time constant smoothing_seconds, instead of jumping straight to it - this gives a
    gradual ramp over time rather than stepping whenever a new sample arrives.
    """

    def __init__(self, base_speed, min_power_watts, max_power_watts, max_speed, smoothing_seconds):
        self.base_speed = base_speed
        self.min_power_watts = min_power_watts
        self.max_power_watts = max_power_watts
        self.max_speed = max_speed
        self.smoothing_seconds = smoothing_seconds
        self._smoothed_speed = None
        self._last_update = None

    def _target_speed(self, power) -> float:
        if power <= self.min_power_watts:
            return self.base_speed
        if power >= self.max_power_watts:
            return self.max_speed
        ratio = (power - self.min_power_watts) / (self.max_power_watts - self.min_power_watts)
        return self.base_speed + ratio * (self.max_speed - self.base_speed)

    def compute(self, status, ftp) -> int:
        target = self._target_speed(status.power)
        now = time.monotonic()

        if self._smoothed_speed is None:
            # First reading - jump straight there, nothing to ramp from yet.
            self._smoothed_speed = target
        else:
            dt = now - self._last_update
            alpha = 1.0 if self.smoothing_seconds <= 0 else 1.0 - math.exp(-dt / self.smoothing_seconds)
            self._smoothed_speed += alpha * (target - self._smoothed_speed)
        self._last_update = now

        return round(self._smoothed_speed)


def get_fan_speed_strategy() -> FanSpeedStrategy:
    if FAN_SOURCE == "power":
        return PowerBasedFanSpeed(
            FAN_BASE_SPEED, FAN_MIN_POWER_WATTS, FAN_MAX_POWER_WATTS, FAN_MAX_SPEED, FAN_SMOOTHING_SECONDS
        )
    raise ValueError(f"Unsupported FAN_SOURCE: {FAN_SOURCE!r}")
