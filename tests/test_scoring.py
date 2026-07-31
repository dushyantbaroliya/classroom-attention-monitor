"""Unit tests for the configurable attention scoring engine."""
from __future__ import annotations

import pytest

from ml.attention.scoring import AttentionScorer, BehaviorSnapshot
from ml.types import EyeState, GazeEstimate, HandState, HeadPose, PhoneState


def snapshot(
    *,
    head_label: str = "forward",
    gaze_label: str = "screen",
    eyes_closed: bool = False,
    closed_duration: float = 0.0,
    phone: bool = False,
    hand: bool = False,
) -> BehaviorSnapshot:
    return BehaviorSnapshot(
        head=HeadPose(label=head_label, ok=True),
        eyes=EyeState(eyes_closed=eyes_closed, closed_duration=closed_duration, ok=True),
        gaze=GazeEstimate(label=gaze_label, ok=True),
        phone=PhoneState(visible=phone),
        hand=HandState(raised=hand),
    )


def make_scorer(**kwargs) -> AttentionScorer:
    kwargs.setdefault("smoothing_alpha", 1.0)  # disable smoothing for exactness
    return AttentionScorer(**kwargs)


class TestNormalization:
    def test_fully_attentive_student_scores_100(self):
        result = make_scorer().score(1, snapshot())
        assert result.normalized == 100.0

    def test_fully_disengaged_student_scores_0(self):
        s = snapshot(
            head_label="left",
            gaze_label="right",
            eyes_closed=True,
            closed_duration=5.0,
            phone=True,
        )
        result = make_scorer().score(1, s)
        assert result.normalized == 0.0

    def test_score_always_within_bounds(self):
        scorer = make_scorer()
        cases = [
            snapshot(hand=True),
            snapshot(phone=True),
            snapshot(head_label="down", gaze_label="down"),
            snapshot(eyes_closed=True, closed_duration=3.0, hand=True),
        ]
        for i, s in enumerate(cases):
            r = scorer.score(i, s)
            assert 0.0 <= r.normalized <= 100.0

    def test_bonus_rule_not_required_for_max(self):
        """Hand raised is a bonus: 100 must be reachable without it."""
        r = make_scorer().score(1, snapshot(hand=False))
        assert r.normalized == 100.0

    def test_bonus_is_clamped_at_100(self):
        r = make_scorer().score(1, snapshot(hand=True))
        assert r.normalized == 100.0
        assert r.components["hand_raised"] == 10


class TestExplainability:
    def test_components_report_triggered_rules_only(self):
        r = make_scorer().score(1, snapshot(phone=True))
        assert r.components["phone_detected"] == -20
        assert "eyes_closed_long" not in r.components
        assert r.components["head_forward"] == 30

    def test_phone_penalty_lowers_score(self):
        scorer = make_scorer()
        clean = scorer.score(1, snapshot()).normalized
        with_phone = scorer.score(2, snapshot(phone=True)).normalized
        assert with_phone < clean

    def test_short_closure_is_not_drowsiness(self):
        r = make_scorer().score(1, snapshot(eyes_closed=True, closed_duration=0.3))
        assert "eyes_closed_long" not in r.components
        assert "eyes_open" not in r.components  # eyes are closed though

    def test_long_closure_triggers_drowsiness_penalty(self):
        r = make_scorer().score(1, snapshot(eyes_closed=True, closed_duration=2.5))
        assert r.components["eyes_closed_long"] == -15


class TestConfigurability:
    def test_custom_weights_change_result(self):
        heavy_phone = {
            "head_forward": {"weight": 30},
            "phone_detected": {"weight": -60},
        }
        scorer = make_scorer(weights=heavy_phone)
        r = scorer.score(1, snapshot(phone=True))
        # raw = 30 - 60 = -30; range [-60, 30] -> (−30+60)/90*100
        assert r.normalized == pytest.approx(33.33, abs=0.01)

    def test_unknown_rule_rejected(self):
        with pytest.raises(ValueError, match="Unknown scoring rule"):
            AttentionScorer(weights={"vibes": {"weight": 10}})

    def test_invalid_alpha_rejected(self):
        with pytest.raises(ValueError):
            AttentionScorer(smoothing_alpha=0.0)


class TestSmoothing:
    def test_smoothing_converges_toward_new_value(self):
        scorer = AttentionScorer(smoothing_alpha=0.5)
        scorer.score(7, snapshot())  # 100 -> smoothed = 100
        r2 = scorer.score(7, snapshot(phone=True, head_label="down", gaze_label="down"))
        assert r2.smoothed > r2.normalized  # pulled up by history
        assert r2.smoothed < 100.0

    def test_students_smoothed_independently(self):
        scorer = AttentionScorer(smoothing_alpha=0.5)
        scorer.score(1, snapshot(phone=True))
        r_other = scorer.score(2, snapshot())
        assert r_other.smoothed == 100.0

    def test_forget_resets_history(self):
        scorer = AttentionScorer(smoothing_alpha=0.5)
        scorer.score(1, snapshot(phone=True))
        scorer.forget(1)
        r = scorer.score(1, snapshot())
        assert r.smoothed == 100.0
