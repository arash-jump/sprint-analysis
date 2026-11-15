import math

import cv2
import mediapipe as mp


POSE_MODEL_SETTINGS = {
    "static_image_mode": False,
    "model_complexity": 1,
    "smooth_landmarks": True,
    "enable_segmentation": False,
    "min_detection_confidence": 0.5,
    "min_tracking_confidence": 0.5,
}

RIGHT_HIP_INDEX = mp.solutions.pose.PoseLandmark.RIGHT_HIP.value


def create_pose():
    return mp.solutions.pose.Pose(**POSE_MODEL_SETTINGS)


def validate_roi(roi: tuple[int, int, int, int], frame_width: int, frame_height: int):
    if (
        not isinstance(roi, (tuple, list))
        or len(roi) != 4
        or any(not isinstance(value, int) or isinstance(value, bool) for value in roi)
    ):
        raise ValueError("ROI must contain integer x, y, width, and height values.")

    x, y, width, height = roi
    if (
        x < 0
        or y < 0
        or width <= 0
        or height <= 0
        or x + width > frame_width
        or y + height > frame_height
    ):
        raise ValueError("ROI must be a non-empty rectangle inside the video frame.")

    return x, y, width, height


def analyze_pose_frame(pose, frame_bgr, roi=None):
    frame_height, frame_width = frame_bgr.shape[:2]
    if roi is None:
        roi_x, roi_y, roi_width, roi_height = 0, 0, frame_width, frame_height
        image = frame_bgr
    else:
        roi_x, roi_y, roi_width, roi_height = validate_roi(
            roi, frame_width, frame_height
        )
        image = frame_bgr[roi_y:roi_y + roi_height, roi_x:roi_x + roi_width]

    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    results = pose.process(image_rgb)
    pose_landmarks = results.pose_landmarks
    if not pose_landmarks:
        return {
            "pose_detected": False,
            "right_hip": None,
            "landmarks": [],
        }

    landmarks = []
    for landmark in pose_landmarks.landmark:
        x_px = roi_x + landmark.x * roi_width
        y_px = roi_y + landmark.y * roi_height
        visibility = getattr(landmark, "visibility", None)
        landmarks.append({
            "x_px": x_px if math.isfinite(x_px) else None,
            "y_px": y_px if math.isfinite(y_px) else None,
            "x_normalized": x_px / frame_width,
            "y_normalized": y_px / frame_height,
            "visibility": visibility,
        })

    return {
        "pose_detected": True,
        "right_hip": (
            landmarks[RIGHT_HIP_INDEX]
            if RIGHT_HIP_INDEX < len(landmarks)
            else None
        ),
        "landmarks": landmarks,
    }


def draw_pose_overlay(frame_bgr, landmarks):
    for start_index, end_index in mp.solutions.pose.POSE_CONNECTIONS:
        start = landmarks[start_index]
        end = landmarks[end_index]
        if (
            start["x_px"] is not None
            and start["y_px"] is not None
            and end["x_px"] is not None
            and end["y_px"] is not None
        ):
            cv2.line(
                frame_bgr,
                (round(start["x_px"]), round(start["y_px"])),
                (round(end["x_px"]), round(end["y_px"])),
                (40, 220, 40),
                2,
            )

    for index, landmark in enumerate(landmarks):
        if landmark["x_px"] is None or landmark["y_px"] is None:
            continue
        color = (0, 0, 255) if index == RIGHT_HIP_INDEX else (255, 180, 0)
        cv2.circle(
            frame_bgr,
            (round(landmark["x_px"]), round(landmark["y_px"])),
            4 if index == RIGHT_HIP_INDEX else 2,
            color,
            -1,
        )

    return frame_bgr
