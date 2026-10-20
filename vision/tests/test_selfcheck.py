"""Unit tests for OpenCV 5 and COOL runtime selfcheck (M5 acceptance gate)."""

import json
from pathlib import Path

from zoneshield.selfcheck import (
    check_cool_acceleration,
    check_hardware_platform,
    check_opencv_version,
    run_selfcheck,
)


def test_check_opencv_version():
    res = check_opencv_version()
    assert "version" in res
    assert "major" in res
    assert "is_opencv_5" in res
    assert "status" in res


def test_check_hardware_platform():
    res = check_hardware_platform()
    assert "architecture" in res
    assert "system" in res
    assert "is_arm64" in res


def test_check_cool_acceleration():
    res = check_cool_acceleration()
    assert "cool_active" in res
    assert "num_threads" in res
    assert "quick_threshold_ms" in res
    assert res["quick_threshold_ms"] >= 0


def test_run_selfcheck(tmp_path):
    out_file = tmp_path / "cool_proof.json"
    res = run_selfcheck(export_path=out_file)
    assert res["product"] == "ZoneShield AI"
    assert out_file.exists()
    
    with open(out_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["product"] == "ZoneShield AI"
    assert "opencv" in data
    assert "cool" in data
