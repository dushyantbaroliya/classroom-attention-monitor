"""Head pose estimation from MediaPipe Face Mesh landmarks via solvePnP.

The math helpers (`rotation_matrix_to_euler`, `classify_head_pose`) are pure
functions so they can be unit-tested without OpenCV or MediaPipe.
"""
from __future__ import annotations

import math
from typing import Mapping, Sequence

import numpy as np

from ml.types import HeadPose, HeadPoseLabel

# MediaPipe Face Mesh landmark indices used as PnP correspondences.
PNP_LANDMARK_INDICES: tuple[int, ...] = (1, 152, 263, 33, 287, 57)

# Generic 3D face model points (millimetres, arbitrary but consistent scale)
# in the same order as PNP_LANDMARK_INDICES:
# nose tip, chin, left eye outer corner, right eye outer corner,
# left mouth corner, right mouth corner.
MODEL_POINTS_3D: np.ndarray = np.array(
    [
        (0.0, 0.0, 0.0),
        (0.0, -63.6, -12.5),
        (-43.3, 32.7, -26.0),
        (43.3, 32.7, -26.0),
        (-28.9, -28.9, -24.1),
        (28.9, -28.9, -24.1),
    ],
    dtype=np.float64,
)


def rotation_matrix_to_euler(rmat: np.ndarray) -> tuple[float, float, float]:
    """Decompose a 3x3 rotation matrix into (yaw, pitch, roll) in degrees.

    Convention: yaw is rotation around the vertical axis (left/right),
    pitch around the horizontal axis (up/down), roll is head tilt.
    """
    sy = math.sqrt(rmat[0, 0] ** 2 + rmat[1, 0] ** 2)
    singular = sy < 1e-6
    if not singular:
        pitch = math.atan2(-rmat[2, 0], sy)
        yaw = math.atan2(rmat[1, 0], rmat[0, 0])
        roll = math.atan2(rmat[2, 1], rmat[2, 2])
    else:  # gimbal lock
        pitch = math.atan2(-rmat[2, 0], sy)
        yaw = 0.0
        roll = math.atan2(-rmat[1, 2], rmat[1, 1])
    return math.degrees(yaw), math.degrees(pitch), math.degrees(roll)


def classify_head_pose(
    yaw: float,
    pitch: float,
    *,
    yaw_left_deg: float = -20.0,
    yaw_right_deg: float = 20.0,
    pitch_up_deg: float = 15.0,
    pitch_down_deg: float = -12.0,
) -> HeadPoseLabel:
    """Map (yaw, pitch) angles to a coarse head-pose category.

    Yaw wins over pitch when both exceed their thresholds because horizontal
    turning is the stronger disengagement signal in a classroom.
    """
    if yaw <= yaw_left_deg:
        return "left"
    if yaw >= yaw_right_deg:
        return "right"
    if pitch >= pitch_up_deg:
        return "up"
    if pitch <= pitch_down_deg:
        return "down"
    return "forward"


class HeadPoseEstimator:
    """Estimates head pose for one face from 2D landmark pixel coordinates."""

    def __init__(
        self,
        yaw_left_deg: float = -20.0,
        yaw_right_deg: float = 20.0,
        pitch_up_deg: float = 15.0,
        pitch_down_deg: float = -12.0,
    ) -> None:
        self.yaw_left_deg = yaw_left_deg
        self.yaw_right_deg = yaw_right_deg
        self.pitch_up_deg = pitch_up_deg
        self.pitch_down_deg = pitch_down_deg

    def estimate(
        self,
        landmarks_px: Mapping[int, Sequence[float]],
        frame_size: tuple[int, int],
    ) -> HeadPose:
        """Estimate pose from a {landmark_index: (x_px, y_px)} mapping.

        `frame_size` is (width, height) of the image the landmarks live in,
        used to build an approximate pinhole camera matrix.
        """
        try:
            image_points = np.array(
                [landmarks_px[i][:2] for i in PNP_LANDMARK_INDICES], dtype=np.float64
            )
        except KeyError:
            return HeadPose(ok=False)

        import cv2  # local import: keeps module importable without OpenCV

        width, height = frame_size
        focal = float(width)  # standard approximation: focal length ~ image width
        camera_matrix = np.array(
            [[focal, 0, width / 2.0], [0, focal, height / 2.0], [0, 0, 1]],
            dtype=np.float64,
        )
        dist_coeffs = np.zeros((4, 1))

        ok, rvec, _tvec = cv2.solvePnP(
            MODEL_POINTS_3D,
            image_points,
            camera_matrix,
            dist_coeffs,
            flags=cv2.SOLVEPNP_ITERATIVE,
        )
        if not ok:
            return HeadPose(ok=False)

        rmat, _ = cv2.Rodrigues(rvec)
        yaw, pitch, roll = rotation_matrix_to_euler(rmat)
        # solvePnP with this model yields pitch sign flipped vs. our
        # "positive = up" convention; normalize it here.
        pitch = -pitch
        label = classify_head_pose(
            yaw,
            pitch,
            yaw_left_deg=self.yaw_left_deg,
            yaw_right_deg=self.yaw_right_deg,
            pitch_up_deg=self.pitch_up_deg,
            pitch_down_deg=self.pitch_down_deg,
        )
        return HeadPose(yaw=yaw, pitch=pitch, roll=roll, label=label, ok=True)
