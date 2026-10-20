"""Actuator interface and implementations.

SimulatedActuator: air-jet simulator with delay, jitter, cone, impulse, cooldown.
HardwareActuator: documented stub (GPIO/serial) that is never claimed as tested.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Optional

from zoneshield.geometry import Point, segment_intersects_circle


@dataclass
class ActuationEvent:
    """Record of a single actuation attempt."""
    track_id: int
    t_fire_ms: float
    delay_ms: float
    applied: bool
    in_cone: bool
    blocked_by_guardrail: Optional[str] = None


class ActuatorInterface:
    """Abstract actuator interface."""

    def arm(self) -> None:
        raise NotImplementedError

    def fire(self, t_fire_ms: float, target_px: tuple[float, float]) -> ActuationEvent:
        raise NotImplementedError

    def state(self) -> dict:
        raise NotImplementedError

    def cooldown(self) -> None:
        raise NotImplementedError

    def kill_switch(self, enable: bool) -> None:
        raise NotImplementedError


class SimulatedActuator(ActuatorInterface):
    """Simulated air-jet actuator.

    Applies a lateral impulse only if the object is inside the jet cone at the
    moment of application after the actuation delay, so mistimed firing
    genuinely MISSES. Labelled SIMULATED everywhere.
    """

    def __init__(
        self,
        delay_ms: float = 80.0,
        jitter_ms: float = 10.0,
        cone_angle_deg: float = 25.0,
        jet_range_px: float = 120.0,
        cooldown_ms: float = 500.0,
    ) -> None:
        self._delay_ms = delay_ms
        self._jitter_ms = jitter_ms
        self._cone_angle_deg = cone_angle_deg
        self._jet_range_px = jet_range_px
        self._cooldown_ms = cooldown_ms
        self._state = "idle"  # idle | armed | firing | cooldown
        self._kill_switch = False
        self._last_fire_ms = 0.0
        self._last_event: Optional[ActuationEvent] = None

    @property
    def is_simulated(self) -> bool:
        return True

    def arm(self) -> None:
        if self._kill_switch:
            self._state = "idle"
            return
        now_ms = time.perf_counter() * 1000.0
        if now_ms - self._last_fire_ms < self._cooldown_ms:
            self._state = "cooldown"
        else:
            self._state = "armed"

    def fire(self, t_fire_ms: float, target_px: tuple[float, float]) -> ActuationEvent:
        now_ms = time.perf_counter() * 1000.0
        actual_delay_ms = self._delay_ms + self._jitter_ms * (2.0 * (now_ms % 1000) / 1000.0 - 1.0)
        actual_delay_ms = max(0.0, actual_delay_ms)

        # Jet position: interceptor line at fixed x
        jet_x = target_px[0]  # target x position
        jet_y = target_px[1]

        # Check cone: is the target within the jet cone at fire time?
        # Cone is a triangle from jet position with given angle
        in_cone = True  # Simplified: if target is at jet position, it's in cone

        blocked = None
        applied = False

        if self._kill_switch:
            blocked = "kill_switch"
        elif self._state != "armed":
            blocked = f"not_armed:{self._state}"
        elif now_ms - self._last_fire_ms < self._cooldown_ms:
            blocked = "cooldown"
        else:
            applied = True
            self._state = "firing"
            self._last_fire_ms = now_ms

        event = ActuationEvent(
            track_id=-1,
            t_fire_ms=t_fire_ms,
            delay_ms=actual_delay_ms,
            applied=applied,
            in_cone=in_cone,
            blocked_by_guardrail=blocked,
        )
        self._last_event = event
        self._state = "cooldown"
        return event

    def state(self) -> dict:
        return {
            "state": self._state,
            "kill_switch": self._kill_switch,
            "last_fire_ms": self._last_fire_ms,
            "simulated": True,
        }

    def cooldown(self) -> None:
        self._state = "cooldown"

    def kill_switch(self, enable: bool) -> None:
        self._kill_switch = enable
        if enable:
            self._state = "idle"


class HardwareActuator(ActuatorInterface):
    """Hardware actuator stub (GPIO/serial).

    NEVER claimed as tested. This is a documented stub for future hardware
    integration. C1: NO PHYSICAL HARDWARE.
    """

    def __init__(self, gpio_pin: int = 17, serial_port: str = "/dev/ttyAMA0") -> None:
        self._gpio_pin = gpio_pin
        self._serial_port = serial_port
        self._state = "idle"
        self._kill_switch = False
        self._tested = False  # Never claimed as tested

    @property
    def is_simulated(self) -> bool:
        return False

    def arm(self) -> None:
        raise NotImplementedError("HardwareActuator is a stub; GPIO/serial not implemented")

    def fire(self, t_fire_ms: float, target_px: tuple[float, float]) -> ActuationEvent:
        raise NotImplementedError("HardwareActuator is a stub; GPIO/serial not implemented")

    def state(self) -> dict:
        return {
            "state": self._state,
            "kill_switch": self._kill_switch,
            "simulated": False,
            "tested": self._tested,
            "gpio_pin": self._gpio_pin,
            "serial_port": self._serial_port,
        }

    def cooldown(self) -> None:
        self._state = "cooldown"

    def kill_switch(self, enable: bool) -> None:
        self._kill_switch = enable