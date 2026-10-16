"""Unit tests for trajectory predictor (M2)."""

import pytest

from zoneshield.pipeline import Predictor


def test_predictor_constant_velocity():
    predictor = Predictor(dt=0.1)
    tracks = [{
        "id": 1,
        "centroid": [100.0, 100.0],
        "velocity": [10.0, 20.0],
        "class": "foreign",
        "class_probs": {},
        "confidence": 0.9,
    }]
    preds = predictor.predict(tracks, horizons_ms=[100, 250, 500], target_line_y_px=300)

    assert len(preds) == 1
    p = preds[0]
    assert p["track_id"] == 1
    assert p["tti_ms"] is not None
    # TTI = (300 - 100) / 20 * 1000 = 10000ms
    assert abs(p["tti_ms"] - 10000.0) < 1.0

    # Position at 100ms: (100 + 10*0.1, 100 + 20*0.1) = (101, 102)
    assert abs(p["positions_px"][0][0] - 101.0) < 0.1
    assert abs(p["positions_px"][0][1] - 102.0) < 0.1

    # At jet position x
    assert p["at_jet_position_px"] is not None
    assert abs(p["at_jet_position_px"][1] - 300.0) < 0.1


def test_predictor_moving_away_no_tti():
    predictor = Predictor(dt=0.1)
    tracks = [{
        "id": 1,
        "centroid": [100.0, 400.0],
        "velocity": [0.0, -10.0],  # moving up, away from line at y=300
        "class": "foreign",
        "class_probs": {},
        "confidence": 0.9,
    }]
    preds = predictor.predict(tracks, horizons_ms=[100], target_line_y_px=300)
    assert preds[0]["tti_ms"] is None


def test_predictor_crosses_zone():
    predictor = Predictor(dt=0.1)
    tracks = [{
        "id": 1,
        "centroid": [100.0, 100.0],
        "velocity": [0.0, 50.0],  # moving fast toward line at y=300
        "class": "foreign",
        "class_probs": {},
        "confidence": 0.9,
    }]
    preds = predictor.predict(tracks, horizons_ms=[100], target_line_y_px=300)
    # TTI = (300-100)/50 * 1000 = 4000ms, within 2000ms? No, 4000 > 2000
    assert preds[0]["crosses_zone"] is False


def test_predictor_crosses_zone_fast():
    predictor = Predictor(dt=0.1)
    tracks = [{
        "id": 1,
        "centroid": [100.0, 250.0],
        "velocity": [0.0, 100.0],  # very fast
        "class": "foreign",
        "class_probs": {},
        "confidence": 0.9,
    }]
    preds = predictor.predict(tracks, horizons_ms=[100], target_line_y_px=300)
    # TTI = (300-250)/100 * 1000 = 500ms, within 2000ms
    assert preds[0]["crosses_zone"] is True