"""Unit tests for simulated actuator (M2)."""

import time
import pytest

from zoneshield.actuator import SimulatedActuator, HardwareActuator, ActuationEvent


def test_actuator_is_simulated():
    act = SimulatedActuator()
    assert act.is_simulated is True


def test_actuator_arm_and_fire():
    act = SimulatedActuator(delay_ms=50, cooldown_ms=100)
    act.arm()
    assert act.state()["state"] in ("armed", "cooldown")

    event = act.fire(t_fire_ms=1000.0, target_px=(300, 250))
    assert isinstance(event, ActuationEvent)
    assert event.applied is True or event.blocked_by_guardrail is not None


def test_actuator_kill_switch():
    act = SimulatedActuator(delay_ms=50, cooldown_ms=100)
    act.kill_switch(True)
    act.arm()
    event = act.fire(t_fire_ms=1000.0, target_px=(300, 250))
    assert event.applied is False
    assert event.blocked_by_guardrail == "kill_switch"


def test_actuator_cooldown():
    act = SimulatedActuator(delay_ms=50, cooldown_ms=1000)
    act.arm()
    act.fire(t_fire_ms=1000.0, target_px=(300, 250))
    # Immediately try again - should be in cooldown
    event2 = act.fire(t_fire_ms=1001.0, target_px=(300, 250))
    assert event2.applied is False
    assert "cooldown" in (event2.blocked_by_guardrail or "")


def test_hardware_actuator_is_stub():
    act = HardwareActuator()
    assert act.is_simulated is False
    state = act.state()
    assert state["tested"] is False
    assert state["simulated"] is False
    with pytest.raises(NotImplementedError):
        act.fire(t_fire_ms=1000.0, target_px=(300, 250))