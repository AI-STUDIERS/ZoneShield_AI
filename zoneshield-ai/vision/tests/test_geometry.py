"""Unit tests for geometry module (M1 acceptance gate: geometry tests green)."""

import math
import numpy as np
import pytest

from zoneshield.geometry import (
    Point,
    Line,
    Polygon,
    line_intersection,
    point_in_polygon,
    point_to_line_distance,
    segment_intersects_circle,
    kalman_predict,
    kalman_update,
    tti_ms,
    lateral_position_at_time,
    homography_from_points,
)


def test_line_intersection_basic():
    l1 = Line(Point(0, 0), Point(10, 10))
    l2 = Line(Point(0, 10), Point(10, 0))
    pt = line_intersection(l1, l2)
    assert pt is not None
    assert abs(pt.x - 5.0) < 1e-6
    assert abs(pt.y - 5.0) < 1e-6


def test_line_intersection_parallel():
    l1 = Line(Point(0, 0), Point(10, 0))
    l2 = Line(Point(0, 5), Point(10, 5))
    assert line_intersection(l1, l2) is None


def test_point_in_polygon_inside():
    poly = Polygon((Point(0, 0), Point(10, 0), Point(10, 10), Point(0, 10)))
    assert point_in_polygon(Point(5, 5), poly) is True


def test_point_in_polygon_outside():
    poly = Polygon((Point(0, 0), Point(10, 0), Point(10, 10), Point(0, 10)))
    assert point_in_polygon(Point(15, 5), poly) is False


def test_point_in_polygon_on_edge():
    poly = Polygon((Point(0, 0), Point(10, 0), Point(10, 10), Point(0, 10)))
    # Edge points are not strictly inside
    assert point_in_polygon(Point(0, 5), poly) is False


def test_point_to_line_distance():
    line = Line(Point(0, 0), Point(10, 0))
    assert abs(point_to_line_distance(Point(5, 3), line) - 3.0) < 1e-6
    assert abs(point_to_line_distance(Point(5, -3), line) - 3.0) < 1e-6


def test_segment_intersects_circle_true():
    p1 = Point(0, 0)
    p2 = Point(10, 0)
    center = Point(5, 1)
    assert segment_intersects_circle(p1, p2, center, 2.0) is True


def test_segment_intersects_circle_false():
    p1 = Point(0, 0)
    p2 = Point(10, 0)
    center = Point(5, 5)
    assert segment_intersects_circle(p1, p2, center, 2.0) is False


def test_kalman_predict_update_roundtrip():
    state = np.array([0.0, 0.0, 1.0, 0.0])
    cov = np.eye(4) * 0.1
    Q = np.eye(4) * 0.01
    dt = 0.1

    state_pred, cov_pred = kalman_predict(state, cov, Q, dt)
    assert state_pred.shape == (4, 1) or state_pred.shape == (4,)
    assert cov_pred.shape == (4, 4)

    measurement = np.array([0.1, 0.0])
    R = np.eye(2) * 0.05
    state_upd, cov_upd, K, y = kalman_update(state_pred, cov_pred, measurement, R)
    assert state_upd.shape == (4,) or state_upd.shape == (4, 1)
    assert cov_upd.shape == (4, 4)


def test_tti_ms():
    # Object moving toward line at y=100, currently at y=50, vy=10 px/s
    t = tti_ms((0, 50), (0, 10), 100)
    assert t is not None
    assert abs(t - 5000.0) < 1.0  # 50px / 10px/s = 5s = 5000ms

    # Object moving away
    t = tti_ms((0, 150), (0, -10), 100)
    assert t is None

    # Object already past line
    t = tti_ms((0, 120), (0, 10), 100)
    assert t == 0.0


def test_lateral_position_at_time():
    x = lateral_position_at_time((0, 0), (5, 0), 1000.0)
    assert abs(x - 5.0) < 1e-6  # 5 px/s * 1s = 5px


def test_homography_from_points_insufficient():
    H = homography_from_points([(0, 0), (1, 1)], [(0, 0), (1, 1)])
    assert H is None


def test_homography_from_points_identity():
    pts = [(0, 0), (10, 0), (10, 10), (0, 10)]
    H = homography_from_points(pts, pts)
    assert H is not None
    assert H.shape == (3, 3)