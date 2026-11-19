from __future__ import annotations

import json
import math
import sys

import cv2

from analysis_quality import assess_detection_quality, assess_right_hip
from analysis_metrics import calculate_velocity_metrics
from measurement_interval import MeasurementFrameRange
from pose_detection import analyze_pose_frame, create_pose
from video_timestamps import VideoTimestampError, read_frame_timestamps


def emit_error(
    message: str,
    analysis_status: str = "processing_error",
    **details,
) -> int:
    print(json.dumps({
        "analysis_status": analysis_status,
        "error": message,
        **details,
    }, allow_nan=False))
    return 1


def parse_roi(value) -> tuple[int, int, int, int] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        if set(value) != {"x", "y", "width", "height"}:
            raise ValueError("ROI must contain integer x, y, width, and height values.")
        value = (value["x"], value["y"], value["width"], value["height"])
    if (
        not isinstance(value, (list, tuple))
        or len(value) != 4
        or any(type(coordinate) is not int for coordinate in value)
    ):
        raise ValueError("ROI must contain integer x, y, width, and height values.")
    return tuple(value)


def parse_measurement_range(
    payload: dict,
    total_video_frames: int,
) -> MeasurementFrameRange:
    start_frame = payload.get("measurement_start_frame")
    end_frame = payload.get("measurement_end_frame")
    return MeasurementFrameRange(
        start_frame=1 if start_frame is None else start_frame,
        end_frame=total_video_frames if end_frame is None else end_frame,
        total_video_frames=total_video_frames,
    )


def analyze_video(
    movie_path: str,
    frame_timestamps: list[float],
    frame_range: MeasurementFrameRange,
    roi: tuple[int, int, int, int] | None,
) -> tuple[list[dict], list[dict], list[tuple[float, float]]]:
    cap = cv2.VideoCapture(movie_path)
    if not cap.isOpened():
        cap.release()
        raise ValueError("The video could not be opened.")

    pose = create_pose()
    frame_diagnostics = []
    measurement_diagnostics = []
    detected_positions = []
    frames_processed = 0

    try:
        while frames_processed < frame_range.end_frame:
            ret, frame = cap.read()
            if not ret:
                raise ValueError(
                    "The video ended before the selected measurement range."
                )
            if frames_processed >= len(frame_timestamps):
                raise ValueError(
                    "Decoded video frames do not match the available frame timestamps."
                )

            frame_number = frames_processed + 1
            timestamp = frame_timestamps[frames_processed]
            pose_frame = analyze_pose_frame(pose, frame, roi)
            right_hip = pose_frame["right_hip"]
            accepted, rejection_reason = assess_right_hip(right_hip)
            if not pose_frame["pose_detected"]:
                rejection_reason = "pose_not_detected"

            in_measurement_interval = frame_range.includes(frame_number)
            diagnostic = {
                "frame_number": frame_number,
                "timestamp_seconds": timestamp,
                "pose_detected": pose_frame["pose_detected"],
                "landmark_x_px": right_hip["x_px"] if right_hip else None,
                "landmark_y_px": right_hip["y_px"] if right_hip else None,
                "landmark_visibility": (
                    right_hip["visibility"]
                    if right_hip
                    and isinstance(right_hip["visibility"], (int, float))
                    and math.isfinite(right_hip["visibility"])
                    else None
                ),
                "within_measurement_interval": in_measurement_interval,
                "calculation_accepted": in_measurement_interval and accepted,
                "rejection_reason": (
                    rejection_reason
                    if in_measurement_interval or not accepted
                    else "outside_measurement_interval"
                ),
            }
            frame_diagnostics.append(diagnostic)
            frames_processed += 1

            if in_measurement_interval:
                measurement_diagnostics.append(diagnostic)
                if accepted:
                    detected_positions.append((timestamp, right_hip["x_px"]))
    finally:
        cap.release()
        pose.close()

    return frame_diagnostics, measurement_diagnostics, detected_positions


def main() -> int:
    if len(sys.argv) < 2:
        return emit_error("No analysis input was provided.")

    try:
        payload = json.loads(sys.argv[1])
        if not isinstance(payload, dict):
            return emit_error("Analysis input must be a JSON object.")

        movie_path = payload["movie_path"]
        ffprobe_binary = payload["ffprobe_binary"]
        calibration_distance = float(payload["calibration_distance"])
        calibration_points = payload["calibration_point"]
        roi = parse_roi(payload.get("roi"))

        if not isinstance(movie_path, str) or not movie_path:
            return emit_error("A video path is required.")
        if not isinstance(ffprobe_binary, str) or not ffprobe_binary:
            return emit_error("An FFprobe executable is required.")
        if (
            not math.isfinite(calibration_distance)
            or calibration_distance <= 0
        ):
            return emit_error("Calibration distance must be greater than zero.")
        if not isinstance(calibration_points, list) or len(calibration_points) < 2:
            return emit_error("At least two calibration points are required.")

        x1, y1 = float(calibration_points[0]["x"]), float(calibration_points[0]["y"])
        x2, y2 = float(calibration_points[1]["x"]), float(calibration_points[1]["y"])
        if not all(math.isfinite(value) for value in (x1, y1, x2, y2)):
            return emit_error("Calibration points must be finite coordinates.")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return emit_error("Analysis input is invalid.")

    pixel_distance = math.hypot(x2 - x1, y2 - y1)
    if not math.isfinite(pixel_distance) or pixel_distance <= 0:
        return emit_error("Calibration points must be distinct valid coordinates.")

    scale_m_per_px = calibration_distance / pixel_distance
    if not math.isfinite(scale_m_per_px):
        return emit_error("The calibration scale is invalid.")

    try:
        frame_timestamps = read_frame_timestamps(movie_path, ffprobe_binary)
    except VideoTimestampError as exception:
        return emit_error(str(exception))
    first_timestamp = frame_timestamps[0]
    frame_timestamps = [
        timestamp - first_timestamp for timestamp in frame_timestamps
    ]

    try:
        frame_range = parse_measurement_range(payload, len(frame_timestamps))
        frame_diagnostics, measurement_diagnostics, detected_positions = analyze_video(
            movie_path,
            frame_timestamps,
            frame_range,
            roi,
        )
    except ValueError as exception:
        return emit_error(str(exception))

    quality = assess_detection_quality(measurement_diagnostics)
    measurement_interval = {
        "start_frame": frame_range.start_frame,
        "end_frame": frame_range.end_frame,
        "frame_count": frame_range.frame_count,
        "start_timestamp_seconds": frame_timestamps[frame_range.start_frame - 1],
        "end_timestamp_seconds": frame_timestamps[frame_range.end_frame - 1],
        "boundaries_inclusive": True,
    }
    roi_result = (
        {"x": roi[0], "y": roi[1], "width": roi[2], "height": roi[3]}
        if roi is not None
        else None
    )
    if quality["analysis_status"] != "quality_check_passed":
        return emit_error(
            "Pose detection quality is insufficient for a sprint measurement.",
            **quality,
            detection_count=quality["accepted_point_count"],
            landmark_used="right_hip",
            model_input_frame_count=frame_range.end_frame,
            measurement_interval=measurement_interval,
            roi=roi_result,
            frame_diagnostics=frame_diagnostics,
        )

    try:
        metrics = calculate_velocity_metrics(
            detected_positions,
            scale_m_per_px=scale_m_per_px,
        )
    except ValueError as exception:
        return emit_error(str(exception))

    result = {
        **quality,
        "time_basis": "converted_video_presentation_timestamps",
        "calibration_distance": calibration_distance,
        "pixel_distance": pixel_distance,
        "scale_m_per_px": scale_m_per_px,
        "detection_count": quality["accepted_point_count"],
        "landmark_used": "right_hip",
        "model_input_frame_count": frame_range.end_frame,
        "measurement_interval": measurement_interval,
        "roi": roi_result,
        "analysis_start_seconds": detected_positions[0][0],
        "analysis_end_seconds": detected_positions[-1][0],
        "frame_diagnostics": frame_diagnostics,
        **metrics,
    }

    print(json.dumps(result, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
