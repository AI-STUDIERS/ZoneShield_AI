"""Unit tests for Kalman filter tracker (M2)."""

import numpy as np
import pytest

from zoneshield.pipeline import Tracker


def test_tracker_new_detection_creates_track():
    tracker = Tracker(dt=0.1)
    detections = [{"centroid": [100.0, 100.0]}]
    class_probs = {0: {"foreign": 0.9, "legit": 0.1, "ambiguous": 0.0}}
    tracks = tracker.update(detections, class_probs)
    assert len(tracks) == 1
    assert tracks[0]["id"] == 0
    assert tracks[0]["centroid"] == [100.0, 100.0]


def test_tracker_persistence_across_frames():
    tracker = Tracker(dt=0.1)
    # Frame 1: create track at (100, 100)
    t1 = tracker.update([{"centroid": [100.0, 100.0]}], {0: {"foreign": 0.9, "legit": 0.1, "ambiguous": 0.0}})
    assert len(t1) == 1
    track_id = t1[0]["id"]

    # Frame 2: same track moved to (110, 105)
    t2 = tracker.update([{"centroid": [110.0, 105.0]}], {track_id: {"foreign": 0.8, "legit": 0.2, "ambiguous": 0.0}})
    assert len(t2) == 1
    assert t2[0]["id"] == track_id
    assert t2[0]["age"] == 2
    assert t2[0]["hits"] == 2


def test_tracker_missed_detection_keeps_track():
    tracker = Tracker(dt=0.1)
    t1 = tracker.update([{"centroid": [100.0, 100.0]}], {0: {"foreign": 0.9, "legit": 0.1, "ambiguous": 0.0}})
    track_id = t1[0]["id"]

    # Frame 2: no detections - track should be predicted, not removed immediately
    t2 = tracker.update([], {})
    assert len(t2) == 1
    assert t2[0]["id"] == track_id
    assert t2[0]["misses"] >= 0  # track still alive


def test_tracker_multiple_objects():
    tracker = Tracker(dt=0.1)
    detections = [
        {"centroid": [50.0, 50.0]},
        {"centroid": [200.0, 200.0]},
        {"centroid": [350.0, 100.0]},
    ]
    class_probs = {
        0: {"foreign": 0.9, "legit": 0.1, "ambiguous": 0.0},
        1: {"foreign": 0.1, "legit": 0.9, "ambiguous": 0.0},
        2: {"foreign": 0.8, "legit": 0.2, "ambiguous": 0.0},
    }
    tracks = tracker.update(detections, class_probs)
    assert len(tracks) == 3
    ids = sorted([t["id"] for t in tracks])
    assert ids == [0, 1, 2]


def test_tracker_class_props_assigned():
    tracker = Tracker(dt=0.1)
    class_probs = {0: {"foreign": 0.95, "legit": 0.05, "ambiguous": 0.0}}
    tracks = tracker.update([{"centroid": [100.0, 100.0]}], class_probs)
    assert tracks[0]["class"] == "foreign"
    assert tracks[0]["confidence"] == 0.95