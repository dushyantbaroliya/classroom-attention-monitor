"""Unit tests for head pose helper functions."""
from __future__ import annotations

import math

import numpy as np
import pytest

from ml.attention.head_pose import classify_head_pose, rotation_matrix_to_euler


def rot_z(deg: float) -> np.ndarray:
    r = math.radians(deg)
    return np.array(
        [[math.cos(r), -math.sin(r), 0], [math.sin(r), math.cos(r), 0], [0, 0, 1]]
    )


def rot_y(deg: float) -> np.ndarray:
    r = math.radians(deg)
    return np.array(
        [[math.cos(r), 0, math.sin(r)], [0, 1, 0], [-math.sin(r), 0, math.cos(r)]]
    )


class TestEulerDecomposition:
    def test_identity_is_zero_angles(self):
        yaw, pitch, roll = rotation_matrix_to_euler(np.eye(3))
        assert yaw == pytest.approx(0.0, abs=1e-9)
        assert pitch == pytest.approx(0.0, abs=1e-9)
        assert roll == pytest.approx(0.0, abs=1e-9)

    def test_pure_yaw_recovered(self):
        yaw, pitch, roll = rotation_matrix_to_euler(rot_z(25.0))
        assert yaw == pytest.approx(25.0, abs=1e-6)
        assert pitch == pytest.approx(0.0, abs=1e-6)

    def test_pure_pitch_recovered(self):
        # Right-hand-rule convention: rotation about Y by θ decomposes to pitch=θ.
        yaw, pitch, roll = rotation_matrix_to_euler(rot_y(-15.0))
        assert pitch == pytest.approx(-15.0, abs=1e-6)

    def test_gimbal_lock_does_not_crash(self):
        yaw, pitch, roll = rotation_matrix_to_euler(rot_y(90.0))
        assert pitch == pytest.approx(90.0, abs=1e-4)


class TestClassification:
    @pytest.mark.parametrize(
        ("yaw", "pitch", "expected"),
        [
            (0, 0, "forward"),
            (5, -5, "forward"),
            (-25, 0, "left"),
            (25, 0, "right"),
            (0, 20, "up"),
            (0, -20, "down"),
        ],
    )
    def test_categories(self, yaw, pitch, expected):
        assert classify_head_pose(yaw, pitch) == expected

    def test_yaw_takes_priority_over_pitch(self):
        # Turned to a neighbor while also glancing down: report the turn.
        assert classify_head_pose(-30, -30) == "left"

    def test_thresholds_are_configurable(self):
        assert classify_head_pose(15, 0, yaw_right_deg=10.0) == "right"
        assert classify_head_pose(15, 0, yaw_right_deg=20.0) == "forward"

    def test_boundary_is_inclusive(self):
        assert classify_head_pose(20.0, 0) == "right"
        assert classify_head_pose(-20.0, 0) == "left"
