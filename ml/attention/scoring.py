"""Explainable, configurable attention scoring.

Every component is a named rule with a weight loaded from configuration
(`config.yaml -> scoring.weights`). The engine reports the exact
contribution of each rule so the dashboard can show *why* a student got
their score — no black boxes.

Normalization
-------------
raw score = sum of triggered weights.
The theoretical range without bonuses is [sum(negative weights), sum of
non-bonus positive weights]; that range is mapped linearly to 0..100.
"Bonus" rules (e.g. hand raised) can push the score above the nominal
maximum and are clamped at 100 — a student should not *need* a raised
hand to reach full attention.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

from ml.types import (
    EyeState,
    GazeEstimate,
    HandState,
    HeadPose,
    PhoneState,
    ScoreBreakdown,
)


@dataclass(frozen=True, slots=True)
class ScoreRule:
    name: str
    weight: float
    bonus: bool = False


@dataclass(slots=True)
class BehaviorSnapshot:
    """The per-frame behavioral inputs the scorer evaluates."""

    head: HeadPose
    eyes: EyeState
    gaze: GazeEstimate
    phone: PhoneState
    hand: HandState
    drowsy_after_seconds: float = 2.0


# Rule predicates: rule name -> does it trigger for this snapshot?
_PREDICATES: Mapping[str, Callable[[BehaviorSnapshot], bool]] = {
    "head_forward": lambda s: s.head.ok and s.head.label == "forward",
    "gaze_screen": lambda s: s.gaze.ok and s.gaze.label in ("screen", "notebook"),
    "eyes_open": lambda s: s.eyes.ok and not s.eyes.eyes_closed,
    "hand_raised": lambda s: s.hand.raised,
    "phone_detected": lambda s: s.phone.visible,
    "eyes_closed_long": lambda s: s.eyes.ok
    and s.eyes.eyes_closed
    and s.eyes.closed_duration >= s.drowsy_after_seconds,
}

DEFAULT_WEIGHTS: dict[str, dict] = {
    "head_forward": {"weight": 30},
    "gaze_screen": {"weight": 25},
    "eyes_open": {"weight": 15},
    "hand_raised": {"weight": 10, "bonus": True},
    "phone_detected": {"weight": -20},
    "eyes_closed_long": {"weight": -15},
}


class AttentionScorer:
    """Weighted-rule scorer with per-student exponential smoothing."""

    def __init__(
        self,
        weights: Mapping[str, Mapping] | None = None,
        smoothing_alpha: float = 0.35,
    ) -> None:
        raw = dict(weights) if weights else DEFAULT_WEIGHTS
        self.rules: list[ScoreRule] = []
        for name, spec in raw.items():
            if name not in _PREDICATES:
                raise ValueError(
                    f"Unknown scoring rule '{name}'. Known rules: {sorted(_PREDICATES)}"
                )
            self.rules.append(
                ScoreRule(
                    name=name,
                    weight=float(spec["weight"]),
                    bonus=bool(spec.get("bonus", False)),
                )
            )
        if not (0.0 < smoothing_alpha <= 1.0):
            raise ValueError("smoothing_alpha must be in (0, 1]")
        self.smoothing_alpha = smoothing_alpha

        self._max_raw = sum(r.weight for r in self.rules if r.weight > 0 and not r.bonus)
        self._min_raw = sum(r.weight for r in self.rules if r.weight < 0)
        if self._max_raw <= self._min_raw:
            raise ValueError("Scoring weights must allow a positive score range")
        # Previous smoothed value per student.
        self._smoothed: dict[int, float] = {}

    def score(self, track_id: int, snapshot: BehaviorSnapshot) -> ScoreBreakdown:
        components: dict[str, float] = {}
        raw = 0.0
        for rule in self.rules:
            if _PREDICATES[rule.name](snapshot):
                components[rule.name] = rule.weight
                raw += rule.weight

        span = self._max_raw - self._min_raw
        normalized = (raw - self._min_raw) / span * 100.0
        normalized = min(100.0, max(0.0, normalized))

        prev = self._smoothed.get(track_id)
        smoothed = (
            normalized
            if prev is None
            else self.smoothing_alpha * normalized + (1 - self.smoothing_alpha) * prev
        )
        self._smoothed[track_id] = smoothed

        return ScoreBreakdown(
            components=components,
            raw=raw,
            normalized=round(normalized, 2),
            smoothed=round(smoothed, 2),
        )

    def forget(self, track_id: int) -> None:
        """Drop smoothing state for a student who left the session."""
        self._smoothed.pop(track_id, None)
