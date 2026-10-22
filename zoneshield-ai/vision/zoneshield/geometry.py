"""Geometry utilities: line intersection, point-in-polygon, Kalman helpers.

Pure functions with exhaustive unit tests (see vision/tests/test_geometry.py).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np


@dataclass(frozen=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True)
class Line:
    p1: Point
    p2: Point


@dataclass(frozen=True)
class Polygon:
    vertices: Tuple[Point, ...]


def line_intersection(l1: Line, l2: Line) -> Optional[Point]:
    """Return intersection point of two lines, or None if parallel."""
    x1, y1 = l1.p1.x, l1.p1.y
    x2, y2 = l1.p2.x, l1.p2.y
    x3, y3 = l2.p1.x, l2.p1.y
    x4, y4 = l2.p2.x, l2.p2.y

    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(den) < 1e-9:
        return None

    px = ((x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)) / den
    py = ((x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)) / den
    return Point(px, py)


def point_in_polygon(point: Point, poly: Polygon) -> bool:
    """Ray-casting point-in-polygon test. Returns True if strictly inside.
    Points exactly on the boundary are considered outside."""
    x, y = point.x, point.y
    # First check if point is exactly on any edge (boundary = outside)
    verts = poly.vertices
    n = len(verts)
    for i in range(n):
        j = (i + 1) % n
        xi, yi = verts[i].x, verts[i].y
        xj, yj = verts[j].x, verts[j].y
        # Check if point is on the segment
        if abs((x - xi) * (yj - yi) - (y - yi) * (xj - xi)) < 1e-9:
            if min(xi, xj) - 1e-9 <= x <= max(xi, xj) + 1e-9 and min(yi, yj) - 1e-9 <= y <= max(yi, yj) + 1e-9:
                return False
    # Ray casting for interior
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = verts[i].x, verts[i].y
        xj, yj = verts[j].x, verts[j].y
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def point_to_line_distance(point: Point, line: Line) -> float:
    """Perpendicular distance from point to infinite line."""
    x0, y0 = point.x, point.y
    x1, y1 = line.p1.x, line.p1.y
    x2, y2 = line.p2.x, line.p2.y
    num = abs((y2 - y1) * x0 - (x2 - x1) * y0 + x2 * y1 - y2 * x1)
    den = math.hypot(y2 - y1, x2 - x1)
    if den < 1e-9:
        return math.hypot(x0 - x1, y0 - y1)
    return num / den


def segment_intersects_circle(p1: Point, p2: Point, center: Point, radius: float) -> bool:
    """True if line segment p1-p2 intersects circle centered at center with radius."""
    # Vector from p1 to p2
    dx = p2.x - p1.x
    dy = p2.y - p1.y
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        return math.hypot(center.x - p1.x, center.y - p1.y) <= radius

    # Project center onto line segment, clamped to [0, 1]
    t = ((center.x - p1.x) * dx + (center.y - p1.y) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    closest = Point(p1.x + t * dx, p1.y + t * dy)
    return math.hypot(center.x - closest.x, center.y - closest.y) <= radius


def kalman_predict(
    state: np.ndarray,
    covariance: np.ndarray,
    process_noise: np.ndarray,
    dt: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """Kalman predict step for constant-velocity model [x, y, vx, vy]."""
    state = np.asarray(state, dtype=float).reshape(4, 1)
    covariance = np.asarray(covariance, dtype=float)
    process_noise = np.asarray(process_noise, dtype=float)
    F = np.array([
        [1, 0, dt, 0],
        [0, 1, 0, dt],
        [0, 0, 1, 0],
        [0, 0, 0, 1],
    ])
    state_pred = F @ state
    cov_pred = F @ covariance @ F.T + process_noise
    return state_pred, cov_pred


def kalman_update(
    state_pred: np.ndarray,
    cov_pred: np.ndarray,
    measurement: np.ndarray,
    measurement_noise: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Kalman update step. Measurement is [x, y]."""
    state_pred = np.asarray(state_pred, dtype=float).reshape(4, 1)
    cov_pred = np.asarray(cov_pred, dtype=float)
    measurement = np.asarray(measurement, dtype=float).reshape(2, 1)
    measurement_noise = np.asarray(measurement_noise, dtype=float)
    H = np.array([
        [1, 0, 0, 0],
        [0, 1, 0, 0],
    ])
    y = measurement - H @ state_pred
    S = H @ cov_pred @ H.T + measurement_noise
    K = cov_pred @ H.T @ np.linalg.inv(S)
    state_upd = state_pred + K @ y
    I = np.eye(4)
    cov_upd = (I - K @ H) @ cov_pred
    return state_upd, cov_upd, K, y


def tti_ms(
    position_px: Tuple[float, float],
    velocity_px_s: Tuple[float, float],
    target_line_y_px: float,
) -> Optional[float]:
    """Time-to-intercept (ms) until object reaches target line, or None if moving away."""
    _, y = position_px
    _, vy = velocity_px_s
    if vy <= 0:
        return None
    distance_px = target_line_y_px - y
    if distance_px < 0:
        return 0.0
    return (distance_px / vy) * 1000.0


def lateral_position_at_time(
    position_px: Tuple[float, float],
    velocity_px_s: Tuple[float, float],
    t_ms: float,
) -> float:
    """X position at time t_ms in the future."""
    x, _ = position_px
    vx, _ = velocity_px_s
    return x + vx * (t_ms / 1000.0)


def homography_from_points(
    image_points: list[Tuple[float, float]],
    world_points: list[Tuple[float, float]],
) -> Optional[np.ndarray]:
    """Compute homography from 4+ image<->world point pairs."""
    if len(image_points) < 4 or len(world_points) < 4:
        return None
    src = np.array(image_points, dtype=np.float32)
    dst = np.array(world_points, dtype=np.float32)
    H, _ = cv2.findHomography(src, dst)
    return H