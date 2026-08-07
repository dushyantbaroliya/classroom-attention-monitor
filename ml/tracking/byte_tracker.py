"""Self-contained ByteTrack-style multi-object tracker.

Implements the core ByteTrack idea (Zhang et al., 2022) without external
tracking dependencies:

1. Associate HIGH-confidence detections with existing tracks (IoU + Hungarian).
2. Associate remaining tracks with LOW-confidence detections, this is what
   keeps students tracked through partial occlusion, when the detector's
   confidence dips but the person is still there.
3. Unmatched high-confidence detections spawn new tracks; unmatched tracks
   are kept as "lost" for `max_lost_frames` so a student who ducks behind a
   classmate gets the SAME id back when they reappear.

Track ids are stable, monotonically increasing integers -> "Student N".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import numpy as np
from scipy.optimize import linear_sum_assignment

from ml.tracking.kalman import KalmanBoxFilter
from ml.types import BBox, Detection, Track


class TrackState(Enum):
    TENTATIVE = "tentative"  # newly created, not yet confirmed
    ACTIVE = "active"        # confirmed and updated recently
    LOST = "lost"            # missed recently; kept for re-identification


@dataclass
class _InternalTrack:
    track_id: int
    kf: KalmanBoxFilter
    confidence: float
    state: TrackState = TrackState.TENTATIVE
    hits: int = 1
    age: int = 1
    time_since_update: int = 0
    predicted_bbox: BBox = field(default=(0.0, 0.0, 0.0, 0.0))

    def to_public(self) -> Track:
        return Track(
            track_id=self.track_id,
            bbox=self.kf.bbox,
            confidence=self.confidence,
            hits=self.hits,
            age=self.age,
            time_since_update=self.time_since_update,
        )


def iou_matrix(boxes_a: list[BBox], boxes_b: list[BBox]) -> np.ndarray:
    """Pairwise IoU between two bbox lists, shape (len(a), len(b))."""
    if not boxes_a or not boxes_b:
        return np.zeros((len(boxes_a), len(boxes_b)))
    a = np.asarray(boxes_a, dtype=np.float64)
    b = np.asarray(boxes_b, dtype=np.float64)
    tl = np.maximum(a[:, None, :2], b[None, :, :2])
    br = np.minimum(a[:, None, 2:], b[None, :, 2:])
    wh = np.clip(br - tl, 0, None)
    inter = wh[..., 0] * wh[..., 1]
    area_a = (a[:, 2] - a[:, 0]) * (a[:, 3] - a[:, 1])
    area_b = (b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1])
    union = area_a[:, None] + area_b[None, :] - inter
    return np.where(union > 0, inter / union, 0.0)


def _match(
    tracks: list[_InternalTrack],
    detections: list[Detection],
    iou_thresh: float,
) -> tuple[list[tuple[int, int]], list[int], list[int]]:
    """Hungarian matching on IoU. Returns (matches, unmatched_t, unmatched_d)."""
    if not tracks or not detections:
        return [], list(range(len(tracks))), list(range(len(detections)))

    ious = iou_matrix([t.predicted_bbox for t in tracks], [d.bbox for d in detections])
    row_idx, col_idx = linear_sum_assignment(-ious)

    matches: list[tuple[int, int]] = []
    unmatched_t = set(range(len(tracks)))
    unmatched_d = set(range(len(detections)))
    for r, c in zip(row_idx, col_idx):
        if ious[r, c] >= iou_thresh:
            matches.append((r, c))
            unmatched_t.discard(r)
            unmatched_d.discard(c)
    return matches, sorted(unmatched_t), sorted(unmatched_d)


class ByteTracker:
    """Frame-by-frame tracker. Call `update()` once per processed frame."""

    def __init__(
        self,
        track_high_thresh: float = 0.50,
        track_low_thresh: float = 0.10,
        new_track_thresh: float = 0.60,
        match_iou_thresh: float = 0.20,
        max_lost_frames: int = 60,
        min_hits: int = 3,
    ) -> None:
        self.track_high_thresh = track_high_thresh
        self.track_low_thresh = track_low_thresh
        self.new_track_thresh = new_track_thresh
        self.match_iou_thresh = match_iou_thresh
        self.max_lost_frames = max_lost_frames
        self.min_hits = min_hits

        self._tracks: list[_InternalTrack] = []
        self._next_id = 1
        self.frame_count = 0

    # ------------------------------------------------------------------ api
    def update(self, detections: list[Detection]) -> list[Track]:
        """Advance one frame; returns confirmed (ACTIVE) tracks only."""
        self.frame_count += 1

        for t in self._tracks:
            t.predicted_bbox = t.kf.predict()
            t.age += 1
            t.time_since_update += 1

        high = [d for d in detections if d.confidence >= self.track_high_thresh]
        low = [
            d
            for d in detections
            if self.track_low_thresh <= d.confidence < self.track_high_thresh
        ]

        # Stage 1: high-confidence detections vs all alive tracks.
        alive = [t for t in self._tracks if t.state != TrackState.LOST]
        lost = [t for t in self._tracks if t.state == TrackState.LOST]
        matches, unmatched_t_idx, unmatched_high_idx = _match(
            alive, high, self.match_iou_thresh
        )
        for ti, di in matches:
            self._mark_matched(alive[ti], high[di])

        # Stage 1b: remaining high detections vs lost tracks (re-identification).
        remaining_high = [high[i] for i in unmatched_high_idx]
        matches_lost, _, unmatched_high_idx2 = _match(
            lost, remaining_high, self.match_iou_thresh
        )
        for ti, di in matches_lost:
            self._mark_matched(lost[ti], remaining_high[di])
        new_candidates = [remaining_high[i] for i in unmatched_high_idx2]

        # Stage 2 (the "byte" in ByteTrack): unmatched tracks vs LOW-confidence
        # detections, recovers occluded/blurred students.
        still_unmatched = [alive[i] for i in unmatched_t_idx]
        matches_low, unmatched_t_idx2, _ = _match(still_unmatched, low, self.match_iou_thresh)
        for ti, di in matches_low:
            self._mark_matched(still_unmatched[ti], low[di])

        # Tracks that matched nothing this frame become/stay LOST.
        for i in unmatched_t_idx2:
            still_unmatched[i].state = TrackState.LOST

        # Spawn new tracks from confident unmatched detections. Tracks are
        # ACTIVE immediately when min_hits <= 1 or during the very first
        # frames of a session (bootstrapping, as in the reference ByteTrack).
        for det in new_candidates:
            if det.confidence >= self.new_track_thresh:
                immediate = self.min_hits <= 1 or self.frame_count <= self.min_hits
                self._tracks.append(
                    _InternalTrack(
                        track_id=self._next_id,
                        kf=KalmanBoxFilter(det.bbox),
                        confidence=det.confidence,
                        state=TrackState.ACTIVE if immediate else TrackState.TENTATIVE,
                        predicted_bbox=det.bbox,
                    )
                )
                self._next_id += 1

        # Prune tracks lost for too long.
        self._tracks = [
            t for t in self._tracks if t.time_since_update <= self.max_lost_frames
        ]

        return [
            t.to_public()
            for t in self._tracks
            if t.state == TrackState.ACTIVE and t.time_since_update == 0
        ]

    # ------------------------------------------------------------- internals
    def _mark_matched(self, track: _InternalTrack, det: Detection) -> None:
        track.kf.update(det.bbox)
        track.confidence = det.confidence
        track.hits += 1
        track.time_since_update = 0
        if track.hits >= self.min_hits or self.frame_count <= self.min_hits:
            track.state = TrackState.ACTIVE
        elif track.state == TrackState.LOST:
            track.state = TrackState.ACTIVE

    @property
    def active_count(self) -> int:
        return sum(1 for t in self._tracks if t.state == TrackState.ACTIVE)
