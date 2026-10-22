"""Unit tests for simulator (M1 acceptance gate: seeded scenario is reproducible)."""

import numpy as np
import pytest

from zoneshield.framesource import SimulatorLive


def test_simulator_seeded_reproducible():
    """Same seed produces identical frames bit-for-bit."""
    s1 = SimulatorLive(width=320, height=240, fps=15, seed=12345)
    s2 = SimulatorLive(width=320, height=240, fps=15, seed=12345)

    frames1 = []
    frames2 = []
    for _ in range(20):
        f1 = s1.read()
        f2 = s2.read()
        assert f1 is not None and f2 is not None
        frames1.append(f1.image.copy())
        frames2.append(f2.image.copy())

    s1.close()
    s2.close()

    for i, (a, b) in enumerate(zip(frames1, frames2)):
        assert np.array_equal(a, b), f"Frame {i} differs between identical seeds"


def test_simulator_different_seed_different():
    """Different seeds produce different output."""
    s1 = SimulatorLive(width=320, height=240, fps=15, seed=1)
    s2 = SimulatorLive(width=320, height=240, fps=15, seed=2)

    f1 = s1.read()
    f2 = s2.read()
    s1.close()
    s2.close()

    assert f1 is not None and f2 is not None
    assert not np.array_equal(f1.image, f2.image)


def test_simulator_restart_resets():
    """Restart returns to initial state."""
    s = SimulatorLive(width=320, height=240, fps=15, seed=99)
    f1 = s.read()
    f2 = s.read()
    s.restart()
    f3 = s.read()
    f4 = s.read()
    s.close()

    assert f1 is not None and f2 is not None and f3 is not None and f4 is not None
    # After restart, frames should match the original sequence
    assert np.array_equal(f1.image, f3.image)
    assert np.array_equal(f2.image, f4.image)


def test_simulator_ground_truth():
    """Ground truth records are produced with expected fields."""
    s = SimulatorLive(width=320, height=240, fps=15, seed=7)
    for _ in range(10):
        s.read()
    gt = s.ground_truth()
    s.close()

    assert len(gt) == 10
    for frame_gt in gt:
        assert "frame" in frame_gt
        assert "objects" in frame_gt
        for obj in frame_gt["objects"]:
            assert "class" in obj
            assert obj["class"] in ("foreign", "legit")
            assert "position_px" in obj
            assert "radius_px" in obj
            assert "intervention_required" in obj
            assert isinstance(obj["intervention_required"], bool)