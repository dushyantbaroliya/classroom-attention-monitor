"""Unit tests for the ByteTrack-style tracker."""
from __future__ import annotations

from ml.tracking.byte_tracker import ByteTracker, iou_matrix
from ml.types import BBox, Detection


def det(bbox: BBox, conf: float = 0.9) -> Detection:
    return Detection(bbox=bbox, confidence=conf, class_id=0)


def shifted(bbox: BBox, dx: float = 0.0, dy: float = 0.0) -> BBox:
    x1, y1, x2, y2 = bbox
    return (x1 + dx, y1 + dy, x2 + dx, y2 + dy)


def make_tracker(**kwargs) -> ByteTracker:
    kwargs.setdefault("min_hits", 1)
    return ByteTracker(**kwargs)


BOX_A: BBox = (100, 100, 200, 300)
BOX_B: BBox = (400, 100, 500, 300)


class TestIoU:
    def test_identical_boxes(self):
        m = iou_matrix([BOX_A], [BOX_A])
        assert m[0, 0] == 1.0

    def test_disjoint_boxes(self):
        m = iou_matrix([BOX_A], [BOX_B])
        assert m[0, 0] == 0.0

    def test_empty_inputs(self):
        assert iou_matrix([], [BOX_A]).shape == (0, 1)


class TestTracking:
    def test_ids_are_stable_across_frames(self):
        tracker = make_tracker()
        first = tracker.update([det(BOX_A), det(BOX_B)])
        ids_frame1 = {t.track_id for t in first}
        for i in range(1, 10):
            tracks = tracker.update(
                [det(shifted(BOX_A, dx=3 * i)), det(shifted(BOX_B, dx=-3 * i))]
            )
        assert {t.track_id for t in tracks} == ids_frame1
        assert len(ids_frame1) == 2

    def test_new_student_gets_new_id(self):
        tracker = make_tracker()
        tracker.update([det(BOX_A)])
        tracks = tracker.update([det(BOX_A), det(BOX_B)])
        assert len(tracks) == 2
        assert len({t.track_id for t in tracks}) == 2

    def test_reidentification_after_occlusion(self):
        """A student who disappears briefly must get the SAME id back."""
        tracker = make_tracker(max_lost_frames=30)
        [original] = tracker.update([det(BOX_A)])
        for _ in range(5):  # occluded: no detections at all
            tracker.update([])
        [recovered] = tracker.update([det(shifted(BOX_A, dx=5))])
        assert recovered.track_id == original.track_id

    def test_track_dropped_after_max_lost(self):
        tracker = make_tracker(max_lost_frames=3)
        [original] = tracker.update([det(BOX_A)])
        for _ in range(10):
            tracker.update([])
        [reappeared] = tracker.update([det(BOX_A)])
        assert reappeared.track_id != original.track_id

    def test_low_confidence_keeps_existing_track_alive(self):
        """The ByteTrack second stage: low-score detections update tracks."""
        tracker = make_tracker(track_high_thresh=0.5, track_low_thresh=0.1)
        [t0] = tracker.update([det(BOX_A, conf=0.9)])
        [t1] = tracker.update([det(shifted(BOX_A, dx=4), conf=0.3)])
        assert t1.track_id == t0.track_id

    def test_low_confidence_does_not_spawn_new_track(self):
        tracker = make_tracker(new_track_thresh=0.6)
        tracks = tracker.update([det(BOX_A, conf=0.3)])
        assert tracks == []

    def test_min_hits_confirmation(self):
        """After warmup, a new detection needs min_hits frames to be confirmed."""
        tracker = ByteTracker(min_hits=3)
        for i in range(20):  # warmup with one stable student
            tracker.update([det(BOX_A)])
        tracks = tracker.update([det(BOX_A), det(BOX_B)])
        assert len(tracks) == 1  # newcomer still tentative
        tracker.update([det(BOX_A), det(BOX_B)])
        tracks = tracker.update([det(BOX_A), det(BOX_B)])
        assert len(tracks) == 2  # confirmed after 3 hits

    def test_crossing_students_keep_identities(self):
        tracker = make_tracker()
        a, b = (100, 100, 160, 260), (400, 100, 460, 260)
        first = tracker.update([det(a), det(b)])
        id_by_x = {round(t.bbox[0]): t.track_id for t in first}
        # Move toward each other over many small steps.
        for i in range(1, 30):
            tracks = tracker.update(
                [det(shifted(a, dx=8 * i)), det(shifted(b, dx=-8 * i))]
            )
        final = sorted(tracks, key=lambda t: t.bbox[0])
        # After crossing, the track that started left (at x=100) is now right.
        assert final[-1].track_id == id_by_x[100]
