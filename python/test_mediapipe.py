import argparse
from pathlib import Path

import cv2
import mediapipe as mp


def main() -> int:
    parser = argparse.ArgumentParser(description="Check pose detection on a video.")
    parser.add_argument("video_path", type=Path, help="Path to the video file")
    args = parser.parse_args()

    if not args.video_path.is_file():
        parser.error(f"video file does not exist: {args.video_path}")

    cap = cv2.VideoCapture(str(args.video_path))
    if not cap.isOpened():
        print(f"Unable to open video: {args.video_path}")
        cap.release()
        return 1

    pose = mp.solutions.pose.Pose()
    try:
        frame_count = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_count += 1
            image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = pose.process(image_rgb)

            if results.pose_landmarks:
                print(f"Frame {frame_count}: detected pose!")
                hip = results.pose_landmarks.landmark[24]
                print("hip(x, y):", hip.x, hip.y)
    finally:
        cap.release()
        pose.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
