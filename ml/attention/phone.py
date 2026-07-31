"""Phone detection post-processing: associate phone boxes with students.

YOLO gives us phone detections for the whole frame; this module decides
which student each phone belongs to and whether that student is likely
looking at it (phone visible + head pitched down toward it).
"""
from __future__ import annotations

from ml.types import BBox, Detection, PhoneState, Track


def _expand(bbox: BBox, fraction: float) -> BBox:
    x1, y1, x2, y2 = bbox
    w, h = x2 - x1, y2 - y1
    return (x1 - w * fraction, y1 - h * fraction, x2 + w * fraction, y2 + h * fraction)


def _contains(bbox: BBox, point: tuple[float, float]) -> bool:
    x1, y1, x2, y2 = bbox
    return x1 <= point[0] <= x2 and y1 <= point[1] <= y2


def associate_phones(
    tracks: list[Track],
    phone_detections: list[Detection],
    *,
    assoc_expand: float = 0.15,
) -> dict[int, Detection]:
    """Map track_id -> the phone detection assigned to that student.

    A phone belongs to the student whose (slightly expanded) box contains the
    phone centre; ties go to the smallest containing box, i.e. the nearest
    person rather than someone large in the foreground.
    """
    assigned: dict[int, Detection] = {}
    for phone in phone_detections:
        center = phone.center
        best_track: Track | None = None
        best_area = float("inf")
        for track in tracks:
            expanded = _expand(track.bbox, assoc_expand)
            if _contains(expanded, center):
                x1, y1, x2, y2 = track.bbox
                area = (x2 - x1) * (y2 - y1)
                if area < best_area:
                    best_area = area
                    best_track = track
        if best_track is not None and best_track.track_id not in assigned:
            assigned[best_track.track_id] = phone
    return assigned


def phone_state_for(
    track_id: int,
    assignments: dict[int, Detection],
    head_pitch_deg: float,
    *,
    looking_pitch_deg: float = -10.0,
) -> PhoneState:
    """Build the PhoneState for one student from the association result."""
    phone = assignments.get(track_id)
    if phone is None:
        return PhoneState(visible=False)
    return PhoneState(
        visible=True,
        looking_at_phone=head_pitch_deg <= looking_pitch_deg,
        bbox=phone.bbox,
    )
