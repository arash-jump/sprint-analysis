import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

from pose_detection import (
    POSE_MODEL_SETTINGS,
    RIGHT_HIP_INDEX,
    analyze_pose_frame,
    create_pose,
    draw_pose_overlay,
    validate_roi,
)


class PoseDetectionRoiTest(unittest.TestCase):
    def test_pose_creation_uses_the_shared_model_settings(self):
        with patch("pose_detection.mp.solutions.pose.Pose") as pose_factory:
            create_pose()

        pose_factory.assert_called_once_with(**POSE_MODEL_SETTINGS)

    def test_roi_landmark_coordinates_are_restored_to_the_original_frame(self):
        landmarks = [
            SimpleNamespace(x=0.1, y=0.2, visibility=0.9)
            for _ in range(33)
        ]
        landmarks[RIGHT_HIP_INDEX] = SimpleNamespace(
            x=0.25,
            y=0.5,
            visibility=0.95,
        )
        pose = SimpleNamespace(
            process=Mock(return_value=SimpleNamespace(
                pose_landmarks=SimpleNamespace(landmark=landmarks),
            )),
        )
        frame = np.zeros((100, 200, 3), dtype=np.uint8)

        with patch("pose_detection.cv2.cvtColor", side_effect=lambda image, _code: image):
            result = analyze_pose_frame(pose, frame, roi=(50, 20, 100, 50))

        processed_image = pose.process.call_args.args[0]
        self.assertEqual(processed_image.shape, (50, 100, 3))
        self.assertEqual(result["right_hip"]["x_px"], 75.0)
        self.assertEqual(result["right_hip"]["y_px"], 45.0)
        self.assertEqual(result["right_hip"]["x_normalized"], 0.375)
        self.assertEqual(result["right_hip"]["y_normalized"], 0.45)

        with (
            patch("pose_detection.cv2.line") as draw_line,
            patch("pose_detection.cv2.circle") as draw_circle,
        ):
            draw_pose_overlay(frame, result["landmarks"])

        draw_line.assert_called()
        draw_circle.assert_any_call(frame, (75, 45), 4, (0, 0, 255), -1)

    def test_roi_omitted_uses_the_original_full_frame(self):
        frame = np.zeros((80, 120, 3), dtype=np.uint8)
        pose = SimpleNamespace(process=Mock(return_value=SimpleNamespace(
            pose_landmarks=None,
        )))

        with patch("pose_detection.cv2.cvtColor", side_effect=lambda image, _code: image):
            result = analyze_pose_frame(pose, frame)

        self.assertIs(pose.process.call_args.args[0], frame)
        self.assertFalse(result["pose_detected"])

    def test_invalid_or_out_of_bounds_roi_is_rejected(self):
        invalid_rois = [
            (0, 0, 0, 10),
            (-1, 0, 10, 10),
            (0, 0, 201, 10),
            (0, 0, 10),
            (True, 0, 10, 10),
        ]

        for roi in invalid_rois:
            with self.subTest(roi=roi):
                with self.assertRaises(ValueError):
                    validate_roi(roi, 200, 100)

    def test_non_finite_visibility_is_kept_for_rejection_reason_but_not_json_output(self):
        landmarks = [
            SimpleNamespace(x=0.1, y=0.2, visibility=0.9)
            for _ in range(RIGHT_HIP_INDEX + 1)
        ]
        landmarks[RIGHT_HIP_INDEX] = SimpleNamespace(
            x=0.5,
            y=0.5,
            visibility=float("nan"),
        )
        pose = SimpleNamespace(process=Mock(return_value=SimpleNamespace(
            pose_landmarks=SimpleNamespace(landmark=landmarks),
        )))
        frame = np.zeros((100, 100, 3), dtype=np.uint8)

        with patch("pose_detection.cv2.cvtColor", side_effect=lambda image, _code: image):
            result = analyze_pose_frame(pose, frame)

        self.assertTrue(result["pose_detected"])
        self.assertTrue(np.isnan(result["right_hip"]["visibility"]))


if __name__ == "__main__":
    unittest.main()
