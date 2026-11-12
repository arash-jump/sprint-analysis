import json
import math
import sys

import cv2
import mediapipe as mp

from analysis_metrics import calculate_velocity_metrics
from video_timestamps import VideoTimestampError, read_frame_timestamps


def emit_error(message: str, **details) -> int:
    print(json.dumps({"error": message, **details}))
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

    pose = mp.solutions.pose.Pose()
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
            height, width = frame.shape[:2]
            image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = pose.process(image_rgb)
            frame_diagnostic = {
                "frame_number": frames_processed,
                "timestamp_seconds": timestamp,
                "pose_detected": bool(results.pose_landmarks),
                "landmark_x_px": None,
                "landmark_y_px": None,
                "landmark_visibility": None,
            }

            if results.pose_landmarks:
                right_hip = results.pose_landmarks.landmark[
                    mp.solutions.pose.PoseLandmark.RIGHT_HIP.value
                ]
                x_position = right_hip.x * width
                y_position = right_hip.y * height
                visibility = getattr(right_hip, "visibility", None)
                frame_diagnostic["landmark_x_px"] = (
                    x_position if math.isfinite(x_position) else None
                )
                frame_diagnostic["landmark_y_px"] = (
                    y_position if math.isfinite(y_position) else None
                )
                frame_diagnostic["landmark_visibility"] = (
                    visibility
                    if visibility is not None and math.isfinite(visibility)
                    else None
                )
                if math.isfinite(x_position):
                    detected_positions.append((timestamp, x_position))
            frame_diagnostics.append(frame_diagnostic)
    finally:
        cap.release()
        pose.close()

    if frames_processed != len(frame_timestamps):
        return emit_error(
            "Decoded video frames do not match the available frame timestamps."
        )

    if len(detected_positions) < 2:
        return emit_error(
            "The video did not contain enough detectable poses.",
            frame_count=frames_processed,
            detection_count=len(detected_positions),
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
        "time_basis": "converted_video_presentation_timestamps",
        "calibration_distance": calibration_distance,
        "pixel_distance": pixel_distance,
        "scale_m_per_px": scale_m_per_px,
        "frame_count": frames_processed,
        "detection_count": len(detected_positions),
        "landmark_used": "right_hip",
        "analysis_start_seconds": detected_positions[0][0],
        "analysis_end_seconds": detected_positions[-1][0],
        "frame_diagnostics": frame_diagnostics,
        **metrics,
    }

    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
