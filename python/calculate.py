import json
import math
import sys

import cv2

from analysis_quality import assess_detection_quality, assess_right_hip
from analysis_metrics import calculate_velocity_metrics
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

    cap = cv2.VideoCapture(movie_path)
    if not cap.isOpened():
        cap.release()
        return emit_error("The video could not be opened.")

    pose = create_pose()
    detected_positions: list[tuple[float, float]] = []
    frame_diagnostics = []
    frames_processed = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frames_processed >= len(frame_timestamps):
                return emit_error(
                    "Decoded video frames do not match the available frame timestamps."
                )

            timestamp = frame_timestamps[frames_processed] - frame_timestamps[0]
            frames_processed += 1
            pose_frame = analyze_pose_frame(pose, frame)
            right_hip = pose_frame["right_hip"]
            accepted, rejection_reason = assess_right_hip(right_hip)
            if not pose_frame["pose_detected"]:
                rejection_reason = "pose_not_detected"
            frame_diagnostic = {
                "frame_number": frames_processed,
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
                "calculation_accepted": accepted,
                "rejection_reason": rejection_reason,
            }
            if accepted:
                detected_positions.append((timestamp, right_hip["x_px"]))
            frame_diagnostics.append(frame_diagnostic)
    finally:
        cap.release()
        pose.close()

    if frames_processed != len(frame_timestamps):
        return emit_error(
            "Decoded video frames do not match the available frame timestamps."
        )

    quality = assess_detection_quality(frame_diagnostics)
    if quality["analysis_status"] != "quality_check_passed":
        return emit_error(
            "Pose detection quality is insufficient for a sprint measurement.",
            **quality,
            detection_count=quality["accepted_point_count"],
            landmark_used="right_hip",
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
        "analysis_start_seconds": detected_positions[0][0],
        "analysis_end_seconds": detected_positions[-1][0],
        "frame_diagnostics": frame_diagnostics,
        **metrics,
    }

    print(json.dumps(result, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
