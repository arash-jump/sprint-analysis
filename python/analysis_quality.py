from __future__ import annotations

from collections import Counter
from math import isfinite
from statistics import median


# Initial operational thresholds; these are not scientifically validated.
QUALITY_THRESHOLDS = {
    "minimum_accepted_points": 4,
    "minimum_pose_detection_rate": 0.70,
    "minimum_accepted_point_rate": 0.70,
    "minimum_right_hip_visibility": 0.50,
    "maximum_missing_interval_seconds": 0.50,
}


def assess_right_hip(landmark: dict | None) -> tuple[bool, str | None]:
    if landmark is None:
        return False, "right_hip_missing"

    x = landmark.get("x_normalized")
    y = landmark.get("y_normalized")
    visibility = landmark.get("visibility")
    if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
        return False, "coordinate_missing"
    if not isfinite(x) or not isfinite(y):
        return False, "non_finite_coordinate"
    if not 0 <= x <= 1 or not 0 <= y <= 1:
        return False, "coordinate_out_of_frame"
    if not isinstance(visibility, (int, float)):
        return False, "visibility_missing"
    if not isfinite(visibility) or not 0 <= visibility <= 1:
        return False, "invalid_visibility"
    if visibility < QUALITY_THRESHOLDS["minimum_right_hip_visibility"]:
        return False, "low_visibility"

    return True, None


def _missing_intervals(frame_diagnostics: list[dict]) -> list[dict]:
    if not frame_diagnostics:
        return []

    timestamps = [frame["timestamp_seconds"] for frame in frame_diagnostics]
    intervals = [
        current - previous
        for previous, current in zip(timestamps, timestamps[1:])
        if current > previous
    ]
    frame_duration = median(intervals) if intervals else 0.0
    gaps = []
    index = 0

    while index < len(frame_diagnostics):
        if frame_diagnostics[index]["calculation_accepted"]:
            index += 1
            continue

        start_index = index
        while (
            index + 1 < len(frame_diagnostics)
            and not frame_diagnostics[index + 1]["calculation_accepted"]
        ):
            index += 1
        end_index = index

        start = timestamps[start_index]
        end = (
            timestamps[end_index + 1]
            if end_index + 1 < len(timestamps)
            else timestamps[end_index] + frame_duration
        )
        rejection_reasons = Counter(
            frame_diagnostics[frame_index].get("rejection_reason") or "unknown"
            for frame_index in range(start_index, end_index + 1)
        )
        gaps.append({
            "start_seconds": start,
            "end_seconds": end,
            "duration_seconds": max(0.0, end - start),
            "duration_estimated": end_index + 1 == len(timestamps),
            "rejection_reasons": dict(rejection_reasons),
            "first_frame_number": frame_diagnostics[start_index]["frame_number"],
            "last_frame_number": frame_diagnostics[end_index]["frame_number"],
            "frame_count": end_index - start_index + 1,
        })
        index += 1

    return gaps


def assess_detection_quality(frame_diagnostics: list[dict]) -> dict:
    frame_count = len(frame_diagnostics)
    pose_detection_count = sum(
        bool(frame["pose_detected"]) for frame in frame_diagnostics
    )
    accepted_frames = [
        frame
        for frame in frame_diagnostics
        if frame["calculation_accepted"]
    ]
    accepted_count = len(accepted_frames)
    pose_detection_rate = pose_detection_count / frame_count if frame_count else 0.0
    accepted_point_rate = accepted_count / frame_count if frame_count else 0.0
    accepted_timestamps = [
        frame["timestamp_seconds"] for frame in accepted_frames
    ]
    accepted_gaps = [
        current - previous
        for previous, current in zip(accepted_timestamps, accepted_timestamps[1:])
    ]
    maximum_accepted_gap = max(accepted_gaps) if accepted_gaps else None
    missing_intervals = _missing_intervals(frame_diagnostics)
    maximum_missing_interval = max(
        (gap["duration_seconds"] for gap in missing_intervals),
        default=0.0,
    )

    checks = {
        "minimum_accepted_points": {
            "passed": accepted_count >= QUALITY_THRESHOLDS["minimum_accepted_points"],
            "actual": accepted_count,
            "threshold": QUALITY_THRESHOLDS["minimum_accepted_points"],
        },
        "minimum_pose_detection_rate": {
            "passed": pose_detection_rate
            >= QUALITY_THRESHOLDS["minimum_pose_detection_rate"],
            "actual": pose_detection_rate,
            "threshold": QUALITY_THRESHOLDS["minimum_pose_detection_rate"],
        },
        "minimum_accepted_point_rate": {
            "passed": accepted_point_rate
            >= QUALITY_THRESHOLDS["minimum_accepted_point_rate"],
            "actual": accepted_point_rate,
            "threshold": QUALITY_THRESHOLDS["minimum_accepted_point_rate"],
        },
        "maximum_accepted_gap_seconds": {
            "passed": maximum_accepted_gap is not None
            and maximum_accepted_gap
            <= QUALITY_THRESHOLDS["maximum_missing_interval_seconds"],
            "actual": maximum_accepted_gap,
            "threshold": QUALITY_THRESHOLDS["maximum_missing_interval_seconds"],
        },
        "maximum_missing_interval_seconds": {
            "passed": maximum_missing_interval
            <= QUALITY_THRESHOLDS["maximum_missing_interval_seconds"],
            "actual": maximum_missing_interval,
            "threshold": QUALITY_THRESHOLDS["maximum_missing_interval_seconds"],
        },
    }
    quality_passed = all(check["passed"] for check in checks.values())

    return {
        "analysis_status": (
            "quality_check_passed"
            if quality_passed
            else "detection_quality_insufficient"
        ),
        "frame_count": frame_count,
        "pose_detection_count": pose_detection_count,
        "pose_detection_rate": pose_detection_rate,
        "accepted_point_count": accepted_count,
        "accepted_point_rate": accepted_point_rate,
        "first_accepted_timestamp_seconds": (
            accepted_timestamps[0] if accepted_timestamps else None
        ),
        "last_accepted_timestamp_seconds": (
            accepted_timestamps[-1] if accepted_timestamps else None
        ),
        "maximum_gap_between_accepted_points_seconds": maximum_accepted_gap,
        "maximum_missing_interval_seconds": maximum_missing_interval,
        "missing_intervals": missing_intervals,
        "quality_thresholds": QUALITY_THRESHOLDS,
        "quality_checks": checks,
    }
