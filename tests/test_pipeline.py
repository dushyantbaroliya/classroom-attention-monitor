"""End-to-end pipeline test with fake detector/analyzer (no heavy deps)."""
from __future__ import annotations

import numpy as np
import pytest

from backend.app.core.config import AppConfig
from ml.pipeline import AttentionPipeline
from tests.fakes import FakeAnalyzer, FakeDetector, FakeStudentScript

FRAME = np.zeros((720, 1280, 3), dtype=np.uint8)


def build_pipeline(scripts: list[FakeStudentScript]) -> AttentionPipeline:
    config = AppConfig()
    config.tracking.min_hits = 1
    return AttentionPipeline(
        config=config,
        detector=FakeDetector(scripts),
        analyzer=FakeAnalyzer(scripts),
    )


def run_frames(pipeline: AttentionPipeline, n: int, fps: float = 10.0):
    result = None
    for i in range(n):
        result = pipeline.process_frame(FRAME, i + 1, i / fps)
    return result


class TestPipelineEndToEnd:
    def test_two_students_detected_and_labeled(self):
        scripts = [
            FakeStudentScript(bbox=(100, 100, 300, 500)),
            FakeStudentScript(bbox=(600, 120, 800, 520)),
        ]
        result = run_frames(build_pipeline(scripts), 5)
        assert len(result.students) == 2
        assert {s.label for s in result.students} == {"Student 1", "Student 2"}

    def test_attentive_student_scores_high(self):
        scripts = [FakeStudentScript(bbox=(100, 100, 300, 500), attentive=True)]
        result = run_frames(build_pipeline(scripts), 10)
        student = result.students[0]
        assert student.head.ok
        assert not student.eyes.eyes_closed
        assert student.score.smoothed > 60

    def test_distracted_student_scores_lower(self):
        attentive = run_frames(
            build_pipeline([FakeStudentScript(bbox=(100, 100, 300, 500))]), 10
        ).students[0]
        distracted = run_frames(
            build_pipeline(
                [FakeStudentScript(bbox=(100, 100, 300, 500), attentive=False,
                                   has_phone=True)]
            ),
            10,
        ).students[0]
        assert distracted.score.smoothed < attentive.score.smoothed
        assert distracted.eyes.eyes_closed
        assert distracted.phone.visible

    def test_hand_raise_detected_and_counted(self):
        scripts = [FakeStudentScript(bbox=(100, 100, 300, 500), hand_raised=True)]
        pipeline = build_pipeline(scripts)
        result = run_frames(pipeline, 6)
        assert result.students[0].hand.raised
        assert result.hands_raised == 1

    def test_phone_detection_appears_in_frame_counters(self):
        scripts = [
            FakeStudentScript(bbox=(100, 100, 300, 500), has_phone=True),
            FakeStudentScript(bbox=(600, 120, 800, 520)),
        ]
        result = run_frames(build_pipeline(scripts), 5)
        assert result.phones_visible == 1
        by_label = {s.label: s for s in result.students}
        assert by_label["Student 1"].phone.visible
        assert not by_label["Student 2"].phone.visible

    def test_class_average_is_mean_of_students(self):
        scripts = [
            FakeStudentScript(bbox=(100, 100, 300, 500)),
            FakeStudentScript(bbox=(600, 120, 800, 520), attentive=False),
        ]
        result = run_frames(build_pipeline(scripts), 8)
        scores = [s.score.smoothed for s in result.students]
        assert result.class_average == pytest.approx(sum(scores) / 2, abs=0.01)

    def test_empty_classroom_produces_empty_result(self):
        result = run_frames(build_pipeline([]), 3)
        assert result.students == []
        assert result.class_average == 0.0

    def test_processing_time_reported(self):
        result = run_frames(build_pipeline([FakeStudentScript(bbox=(100, 100, 300, 500))]), 2)
        assert result.processing_ms >= 0
