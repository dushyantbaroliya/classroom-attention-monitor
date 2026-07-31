"""Unit tests for gaze classification, hand-raise detection and phone association."""
from __future__ import annotations

from ml.attention.gaze import classify_gaze
from ml.attention.hand_raise import (
    LEFT_SHOULDER,
    LEFT_WRIST,
    RIGHT_SHOULDER,
    RIGHT_WRIST,
    HandRaiseTracker,
    is_hand_raised,
)
from ml.attention.phone import associate_phones, phone_state_for
from ml.types import Detection, Track


class TestGazeClassification:
    def test_centered_gaze_is_screen(self):
        assert classify_gaze(0.5, 0.4, head_pitch_deg=0.0) == "screen"

    def test_iris_left(self):
        assert classify_gaze(0.30, 0.4, head_pitch_deg=0.0) == "left"

    def test_iris_right(self):
        assert classify_gaze(0.75, 0.4, head_pitch_deg=0.0) == "right"

    def test_head_down_centered_gaze_is_notebook(self):
        assert classify_gaze(0.5, 0.5, head_pitch_deg=-30.0) == "notebook"

    def test_iris_down_centered_is_notebook(self):
        assert classify_gaze(0.5, 0.8, head_pitch_deg=0.0) == "notebook"

    def test_down_and_sideways_is_down(self):
        assert classify_gaze(0.2, 0.8, head_pitch_deg=0.0) == "down"

    def test_thresholds_configurable(self):
        assert classify_gaze(0.30, 0.4, 0.0, h_left_ratio=0.25) == "screen"


def pose(wrist_y: float, shoulder_y: float = 100.0, visibility: float = 1.0) -> dict:
    return {
        LEFT_SHOULDER: (50.0, shoulder_y, visibility),
        RIGHT_SHOULDER: (150.0, shoulder_y, visibility),
        LEFT_WRIST: (40.0, wrist_y, visibility),
        RIGHT_WRIST: (160.0, 300.0, visibility),  # right hand always down
    }


class TestHandRaise:
    def test_wrist_above_shoulder_is_raised(self):
        assert is_hand_raised(pose(wrist_y=40.0), bbox_height=200.0)

    def test_wrist_below_shoulder_is_not_raised(self):
        assert not is_hand_raised(pose(wrist_y=180.0), bbox_height=200.0)

    def test_margin_filters_near_shoulder_hands(self):
        # Wrist 5px above shoulder, margin = 0.05*200 = 10px -> not raised.
        assert not is_hand_raised(pose(wrist_y=95.0), bbox_height=200.0)

    def test_low_visibility_landmarks_ignored(self):
        assert not is_hand_raised(pose(wrist_y=40.0, visibility=0.2), bbox_height=200.0)

    def test_missing_landmarks_handled(self):
        assert not is_hand_raised({}, bbox_height=200.0)


class TestHandRaiseTracker:
    def test_debounce_suppresses_single_frame_glitch(self):
        tracker = HandRaiseTracker(debounce_frames=3)
        tracker.update(True, 0.0)
        state = tracker.update(False, 0.1)
        assert not state.raised

    def test_sustained_raise_flips_state_and_logs_event(self):
        tracker = HandRaiseTracker(debounce_frames=3)
        for i in range(3):
            state = tracker.update(True, i * 0.1)
        assert state.raised and state.changed
        assert tracker.raise_count == 1
        assert tracker.events[0].timestamp == 0.2

    def test_full_raise_lower_cycle(self):
        tracker = HandRaiseTracker(debounce_frames=2)
        for i in range(2):
            tracker.update(True, i * 0.1)
        for i in range(2, 4):
            tracker.update(False, i * 0.1)
        assert not tracker.raised
        assert len(tracker.events) == 2
        assert tracker.raise_count == 1


def track(tid: int, bbox) -> Track:
    return Track(track_id=tid, bbox=bbox, confidence=0.9)


def phone_det(cx: float, cy: float, size: float = 20.0) -> Detection:
    half = size / 2
    return Detection(
        bbox=(cx - half, cy - half, cx + half, cy + half), confidence=0.8, class_id=67
    )


class TestPhoneAssociation:
    def test_phone_inside_person_is_assigned(self):
        tracks = [track(1, (0, 0, 100, 200)), track(2, (200, 0, 300, 200))]
        assignments = associate_phones(tracks, [phone_det(50, 150)])
        assert set(assignments) == {1}

    def test_phone_far_from_everyone_is_unassigned(self):
        tracks = [track(1, (0, 0, 100, 200))]
        assignments = associate_phones(tracks, [phone_det(500, 500)])
        assert assignments == {}

    def test_overlapping_people_smallest_box_wins(self):
        big = track(1, (0, 0, 300, 400))
        small = track(2, (40, 60, 160, 260))
        assignments = associate_phones([big, small], [phone_det(100, 150)])
        assert set(assignments) == {2}

    def test_looking_at_phone_requires_pitch_down(self):
        tracks = [track(1, (0, 0, 100, 200))]
        assignments = associate_phones(tracks, [phone_det(50, 150)])
        looking = phone_state_for(1, assignments, head_pitch_deg=-25.0)
        not_looking = phone_state_for(1, assignments, head_pitch_deg=5.0)
        assert looking.visible and looking.looking_at_phone
        assert not_looking.visible and not not_looking.looking_at_phone

    def test_no_phone_state(self):
        state = phone_state_for(1, {}, head_pitch_deg=-25.0)
        assert not state.visible and not state.looking_at_phone
