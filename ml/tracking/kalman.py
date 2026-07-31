"""Constant-velocity Kalman filter for bounding boxes (ByteTrack-style).

State: [cx, cy, aspect_ratio, height, vcx, vcy, va, vh]
Measurement: [cx, cy, aspect_ratio, height]
"""
from __future__ import annotations

import numpy as np

from ml.types import BBox

_NDIM = 4
_DT = 1.0

# Motion / observation uncertainty weights, per ByteTrack reference impl.
_STD_WEIGHT_POSITION = 1.0 / 20
_STD_WEIGHT_VELOCITY = 1.0 / 160


def bbox_to_measurement(bbox: BBox) -> np.ndarray:
    """(x1, y1, x2, y2) -> (cx, cy, aspect, height)."""
    x1, y1, x2, y2 = bbox
    w = max(x2 - x1, 1e-6)
    h = max(y2 - y1, 1e-6)
    return np.array([x1 + w / 2, y1 + h / 2, w / h, h], dtype=np.float64)


def measurement_to_bbox(z: np.ndarray) -> BBox:
    """(cx, cy, aspect, height) -> (x1, y1, x2, y2)."""
    cx, cy, a, h = z[:4]
    w = a * h
    return (float(cx - w / 2), float(cy - h / 2), float(cx + w / 2), float(cy + h / 2))


class KalmanBoxFilter:
    """One Kalman filter per track."""

    def __init__(self, initial_bbox: BBox) -> None:
        self._F = np.eye(2 * _NDIM)
        for i in range(_NDIM):
            self._F[i, _NDIM + i] = _DT
        self._H = np.eye(_NDIM, 2 * _NDIM)

        z = bbox_to_measurement(initial_bbox)
        self.x = np.zeros(2 * _NDIM)
        self.x[:_NDIM] = z

        h = z[3]
        std = [
            2 * _STD_WEIGHT_POSITION * h,
            2 * _STD_WEIGHT_POSITION * h,
            1e-2,
            2 * _STD_WEIGHT_POSITION * h,
            10 * _STD_WEIGHT_VELOCITY * h,
            10 * _STD_WEIGHT_VELOCITY * h,
            1e-5,
            10 * _STD_WEIGHT_VELOCITY * h,
        ]
        self.P = np.diag(np.square(std))

    def predict(self) -> BBox:
        h = self.x[3]
        std_pos = [
            _STD_WEIGHT_POSITION * h,
            _STD_WEIGHT_POSITION * h,
            1e-2,
            _STD_WEIGHT_POSITION * h,
        ]
        std_vel = [
            _STD_WEIGHT_VELOCITY * h,
            _STD_WEIGHT_VELOCITY * h,
            1e-5,
            _STD_WEIGHT_VELOCITY * h,
        ]
        Q = np.diag(np.square(np.concatenate([std_pos, std_vel])))

        self.x = self._F @ self.x
        self.P = self._F @ self.P @ self._F.T + Q
        return measurement_to_bbox(self.x)

    def update(self, bbox: BBox) -> None:
        z = bbox_to_measurement(bbox)
        h = self.x[3]
        std = [
            _STD_WEIGHT_POSITION * h,
            _STD_WEIGHT_POSITION * h,
            1e-1,
            _STD_WEIGHT_POSITION * h,
        ]
        R = np.diag(np.square(std))

        S = self._H @ self.P @ self._H.T + R
        K = self.P @ self._H.T @ np.linalg.inv(S)
        innovation = z - self._H @ self.x
        self.x = self.x + K @ innovation
        self.P = (np.eye(2 * _NDIM) - K @ self._H) @ self.P

    @property
    def bbox(self) -> BBox:
        return measurement_to_bbox(self.x)
