import json
import math
import sys

import cv2
import mediapipe as mp

from analysis_metrics import calculate_velocity_metrics


def emit_error(message: str) -> int:
    print(json.dumps({"error": message}))
    return 1


def main() -> int:
    if len(sys.argv) < 2:
        return emit_error("No analysis input was provided.")

    try:
        payload = json.loads(sys.argv[1])
        if not isinstance(payload, dict):
            return emit_error("Analysis input must be a JSON object.")

        movie_path = payload["movie_path"]
        fps = float(payload["fps"])
        run_distance = float(payload["run_distance"])
        calibration_distance = float(payload["calibration_distance"])
        calibration_points = payload["calibration_point"]

        if not isinstance(movie_path, str) or not movie_path:
            return emit_error("A video path is required.")
        if (
            not all(math.isfinite(value) for value in (fps, calibration_distance, run_distance))
            or fps <= 0
            or calibration_distance <= 0
            or run_distance <= 0
        ):
            return emit_error("FPS and distances must be greater than zero.")
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

    cap = cv2.VideoCapture(movie_path)
    if not cap.isOpened():
        cap.release()
        return emit_error("The video could not be opened.")

    pose = mp.solutions.pose.Pose()
    detected_positions: list[tuple[int, float]] = []
    frames_processed = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frames_processed += 1
            height, width = frame.shape[:2]
            image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = pose.process(image_rgb)

            if results.pose_landmarks:
                right_hip = results.pose_landmarks.landmark[
                    mp.solutions.pose.PoseLandmark.RIGHT_HIP.value
                ]
                x_position = right_hip.x * width
                if math.isfinite(x_position):
                    detected_positions.append((frames_processed, x_position))
    finally:
        cap.release()
        pose.close()

    if len(detected_positions) < 2:
        return emit_error("The video did not contain enough detectable poses.")

    metrics = calculate_velocity_metrics(
        detected_positions,
        fps=fps,
        scale_m_per_px=scale_m_per_px,
    )

    result = {
        "fps": fps,
        "run_distance": run_distance,
        "calibration_distance": calibration_distance,
        "pixel_distance": pixel_distance,
        "scale_m_per_px": scale_m_per_px,
        "frame_count": frames_processed,
        "detection_count": len(detected_positions),
        **metrics,
    }

    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
