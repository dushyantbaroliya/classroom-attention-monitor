"""The end-to-end attention pipeline for one video stream.

    frame -> detection -> tracking -> (per student)
          head pose | eyes/EAR | gaze | pose/hands | phone assoc -> score
          -> FrameResult

The pipeline is deliberately I/O-free: it takes a decoded frame and returns
a FrameResult. Persistence, streaming and pacing live in the backend's
PipelineRunner. Detector and analyzer are injected (Protocols), so the
pipeline itself is unit-testable with fakes, no GPU or model downloads.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from backend.app.core.config import AppConfig
from backend.app.core.logging import get_logger, log_event
from ml.attention.eye_aspect_ratio import BlinkTracker, average_ear
from ml.attention.gaze import GazeEstimator
from ml.attention.hand_raise import HandRaiseTracker, is_hand_raised
from ml.attention.head_pose import HeadPoseEstimator
from ml.attention.phone import associate_phones, phone_state_for
from ml.attention.scoring import AttentionScorer, BehaviorSnapshot
from ml.models.detector import Detector, DetectorOutput
from ml.models.face_analyzer import FaceAnalyzer, match_face_to_bbox
from ml.tracking.byte_tracker import ByteTracker
from ml.types import (
    EyeState,
    FrameResult,
    GazeEstimate,
    HandState,
    HeadPose,
    StudentFrameResult,
)

log = get_logger("pipeline")

STATE_TTL_FRAMES = 300  # drop per-student state after this many unseen frames


@dataclass
class _StudentState:
    blink: BlinkTracker
    hand: HandRaiseTracker
    last_seen_frame: int = 0


@dataclass
class AttentionPipeline:
    config: AppConfig
    detector: Detector
    analyzer: FaceAnalyzer
    tracker: ByteTracker = field(init=False)
    scorer: AttentionScorer = field(init=False)

    def __post_init__(self) -> None:
        t = self.config.tracking
        self.tracker = ByteTracker(
            track_high_thresh=t.track_high_thresh,
            track_low_thresh=t.track_low_thresh,
            new_track_thresh=t.new_track_thresh,
            match_iou_thresh=t.match_iou_thresh,
            max_lost_frames=t.max_lost_frames,
            min_hits=t.min_hits,
        )
        s = self.config.scoring
        self.scorer = AttentionScorer(
            weights=s.weights or None, smoothing_alpha=s.smoothing_alpha
        )
        hp = self.config.head_pose
        self.head_pose = HeadPoseEstimator(
            yaw_left_deg=hp.yaw_left_deg,
            yaw_right_deg=hp.yaw_right_deg,
            pitch_up_deg=hp.pitch_up_deg,
            pitch_down_deg=hp.pitch_down_deg,
        )
        g = self.config.gaze
        self.gaze = GazeEstimator(
            h_left_ratio=g.h_left_ratio,
            h_right_ratio=g.h_right_ratio,
            v_down_ratio=g.v_down_ratio,
            notebook_pitch_deg=g.notebook_pitch_deg,
        )
        self._states: dict[int, _StudentState] = {}

    # ------------------------------------------------------------------ main
    def process_frame(
        self, frame_bgr: np.ndarray, frame_index: int, timestamp: float
    ) -> FrameResult:
        started = time.perf_counter()
        h, w = frame_bgr.shape[:2]

        detections: DetectorOutput = self.detector.detect(frame_bgr)
        tracks = self.tracker.update(detections.persons)
        # Analyze faces within each tracked person's box: crops small, distant
        # classroom faces up to a detectable size (full-frame face detection
        # misses them). See MediaPipeAnalyzer.detect_faces.
        faces = (
            self.analyzer.detect_faces(frame_bgr, regions=[t.bbox for t in tracks])
            if tracks
            else []
        )
        phone_assignments = associate_phones(
            tracks, detections.phones, assoc_expand=self.config.phone.assoc_expand
        )

        students: list[StudentFrameResult] = []
        for track in tracks:
            state = self._state_for(track.track_id, frame_index)
            face = match_face_to_bbox(faces, track.bbox)

            head = (
                self.head_pose.estimate(face, (w, h)) if face else HeadPose(ok=False)
            )
            eyes: EyeState = state.blink.update(
                average_ear(face) if face else None, timestamp
            )
            gaze: GazeEstimate = (
                self.gaze.estimate(face, head.pitch) if face else GazeEstimate(ok=False)
            )

            pose_landmarks = self.analyzer.detect_pose(frame_bgr, track.bbox)
            bbox_height = track.bbox[3] - track.bbox[1]
            raw_raised = (
                is_hand_raised(
                    pose_landmarks, bbox_height, self.config.hands.raise_margin
                )
                if pose_landmarks
                else False
            )
            hand: HandState = state.hand.update(raw_raised, timestamp)
            if hand.changed:
                log_event(
                    log,
                    "hand_raise_changed",
                    track_id=track.track_id,
                    raised=hand.raised,
                    timestamp=round(timestamp, 2),
                )

            phone = phone_state_for(
                track.track_id,
                phone_assignments,
                head.pitch,
                looking_pitch_deg=self.config.phone.looking_pitch_deg,
            )

            score = self.scorer.score(
                track.track_id,
                BehaviorSnapshot(
                    head=head,
                    eyes=eyes,
                    gaze=gaze,
                    phone=phone,
                    hand=hand,
                    drowsy_after_seconds=self.config.eyes.drowsy_after_seconds,
                ),
            )

            students.append(
                StudentFrameResult(
                    track_id=track.track_id,
                    label=f"Student {track.track_id}",
                    bbox=track.bbox,
                    head=head,
                    eyes=eyes,
                    gaze=gaze,
                    phone=phone,
                    hand=hand,
                    score=score,
                )
            )

        self._prune_states(frame_index)
        scores = [s.score.smoothed for s in students]
        return FrameResult(
            frame_index=frame_index,
            timestamp=timestamp,
            students=students,
            class_average=round(sum(scores) / len(scores), 2) if scores else 0.0,
            phones_visible=sum(s.phone.visible for s in students),
            hands_raised=sum(s.hand.raised for s in students),
            processing_ms=round((time.perf_counter() - started) * 1000, 1),
        )

    # ------------------------------------------------------------- internals
    def _state_for(self, track_id: int, frame_index: int) -> _StudentState:
        state = self._states.get(track_id)
        if state is None:
            e = self.config.eyes
            state = _StudentState(
                blink=BlinkTracker(
                    ear_closed_threshold=e.ear_closed_threshold,
                    blink_min_frames=e.blink_min_frames,
                    drowsy_after_seconds=e.drowsy_after_seconds,
                ),
                hand=HandRaiseTracker(),
            )
            self._states[track_id] = state
            log_event(log, "student_detected", track_id=track_id, frame=frame_index)
        state.last_seen_frame = frame_index
        return state

    def _prune_states(self, frame_index: int) -> None:
        stale = [
            tid
            for tid, s in self._states.items()
            if frame_index - s.last_seen_frame > STATE_TTL_FRAMES
        ]
        for tid in stale:
            del self._states[tid]
            self.scorer.forget(tid)


def build_default_pipeline(config: AppConfig) -> AttentionPipeline:
    """Wire the pipeline with real models, per `config.detection.backend`.

    - "mediapipe" (default): torch-free EfficientDet person/phone detector.
    - "yolo": Ultralytics YOLO (needs torch), GPU-capable.
    Both feed the same MediaPipe Tasks face/pose analyzer.
    """
    d = config.detection
    if d.backend == "yolo":
        from ml.models.detector import YoloDetector

        detector = YoloDetector(
            model_path=d.model_path,
            device=d.device,
            confidence=d.confidence,
            iou=d.iou,
            person_class_id=d.person_class_id,
            phone_class_id=d.phone_class_id,
            max_detections=d.max_detections,
            face_model_path=d.face_model_path,
        )
    else:
        from ml.models.detector import MediaPipeObjectDetector

        detector = MediaPipeObjectDetector(
            model_path=d.mediapipe_model_path,
            confidence=d.confidence,
            max_detections=d.max_detections,
        )

    from ml.models.face_analyzer import MediaPipeAnalyzer
    m = config.mediapipe
    analyzer = MediaPipeAnalyzer(
        face_landmarker_path=m.face_landmarker_path,
        pose_landmarker_path=m.pose_landmarker_path,
        max_faces=m.max_faces,
        crop_margin=m.crop_margin,
        min_face_confidence=m.min_face_confidence,
        min_pose_confidence=m.min_pose_confidence,
        enable_pose=m.enable_pose,
    )
    return AttentionPipeline(config=config, detector=detector, analyzer=analyzer)
