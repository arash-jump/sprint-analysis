import contextlib
import io
import json
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import calculate


class CalculateInputTest(unittest.TestCase):
    def test_analysis_error_can_include_frame_diagnostics(self):
        output = io.StringIO()
        diagnostics = [{"frame_number": 1, "pose_detected": False}]

        with contextlib.redirect_stdout(output):
            status = calculate.emit_error(
                "The video did not contain enough detectable poses.",
                frame_count=1,
                detection_count=0,
                frame_diagnostics=diagnostics,
            )

        self.assertEqual(status, 1)
        self.assertEqual(json.loads(output.getvalue()), {
            "error": "The video did not contain enough detectable poses.",
            "frame_count": 1,
            "detection_count": 0,
            "frame_diagnostics": diagnostics,
        })

    def test_reference_run_distance_does_not_change_estimated_speed(self):
        hip_index = calculate.mp.solutions.pose.PoseLandmark.RIGHT_HIP.value
        results = []

        for run_distance in (5, 100):
            payload = {
                "movie_path": "/private/test.mp4",
                "ffprobe_binary": "ffprobe",
                "calibration_point": [
                    {"x": 0, "y": 0},
                    {"x": 100, "y": 0},
                ],
                "calibration_distance": 10,
                "run_distance": run_distance,
            }

            pose = SimpleNamespace(close=lambda: None)
            pose_results = []
            for x_position in (0.1, 0.4):
                landmarks = [
                    SimpleNamespace(x=0.0, y=0.0, visibility=0.0)
                    for _ in range(hip_index + 1)
                ]
                landmarks[hip_index] = SimpleNamespace(
                    x=x_position,
                    y=0.6,
                    visibility=0.9,
                )
                pose_results.append(SimpleNamespace(
                    pose_landmarks=SimpleNamespace(landmark=landmarks),
                ))
            pose.process = Mock(side_effect=[
                pose_results[0],
                SimpleNamespace(pose_landmarks=None),
                pose_results[1],
            ])

            class VideoCapture:
                def __init__(self):
                    self.frames = iter((object(), object(), object()))

                def isOpened(self):
                    return True

                def read(self):
                    try:
                        next(self.frames)
                    except StopIteration:
                        return False, None
                    return True, SimpleNamespace(shape=(100, 100, 3))

                def release(self):
                    pass

            output = io.StringIO()
            with (
                patch.object(sys, "argv", ["calculate.py", json.dumps(payload)]),
                patch.object(
                    calculate,
                    "read_frame_timestamps",
                    return_value=[0.0, 0.5, 1.0],
                ),
                patch.object(calculate.cv2, "VideoCapture", return_value=VideoCapture()),
                patch.object(calculate.cv2, "cvtColor", side_effect=lambda image, _code: image),
                patch.object(
                    calculate.mp.solutions.pose,
                    "Pose",
                    return_value=pose,
                ) as pose_factory,
                contextlib.redirect_stdout(output),
            ):
                self.assertEqual(calculate.main(), 0)
                pose_factory.assert_called_once_with()

            results.append(json.loads(output.getvalue()))

        self.assertAlmostEqual(results[0]["estimated_distance_m"], 3.0)
        self.assertAlmostEqual(results[0]["velocity_avg"], 3.0)
        self.assertEqual(results[0]["estimated_distance_m"], results[1]["estimated_distance_m"])
        self.assertEqual(results[0]["velocity_avg"], results[1]["velocity_avg"])
        self.assertEqual(len(results[0]["frame_diagnostics"]), 3)
        self.assertEqual(
            [frame["pose_detected"] for frame in results[0]["frame_diagnostics"]],
            [True, False, True],
        )
        self.assertEqual(
            results[0]["frame_diagnostics"][0]["landmark_x_px"],
            10.0,
        )
        self.assertEqual(
            results[0]["frame_diagnostics"][0]["landmark_y_px"],
            60.0,
        )
        self.assertEqual(
            results[0]["frame_diagnostics"][0]["landmark_visibility"],
            0.9,
        )
        self.assertIsNone(
            results[0]["frame_diagnostics"][1]["landmark_x_px"],
        )


if __name__ == "__main__":
    unittest.main()
