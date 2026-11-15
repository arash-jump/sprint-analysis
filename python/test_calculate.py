import contextlib
import io
import json
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import calculate
from pose_detection import RIGHT_HIP_INDEX


def pose_result(x_position=0.1, visibility=0.9):
    landmarks = [
        SimpleNamespace(x=0.1, y=0.6, visibility=0.9)
        for _ in range(RIGHT_HIP_INDEX + 1)
    ]
    landmarks[RIGHT_HIP_INDEX] = SimpleNamespace(
        x=x_position,
        y=0.6,
        visibility=visibility,
    )
    return SimpleNamespace(
        pose_landmarks=SimpleNamespace(landmark=landmarks),
    )


def analysis_payload(run_distance=10):
    return {
        "movie_path": "/private/test.mp4",
        "ffprobe_binary": "ffprobe",
        "calibration_point": [
            {"x": 0, "y": 0},
            {"x": 100, "y": 0},
        ],
        "calibration_distance": 10,
        "run_distance": run_distance,
    }


class CalculateInputTest(unittest.TestCase):
    def test_timestamp_failure_is_reported_as_processing_error(self):
        output = io.StringIO()
        with (
            patch.object(
                sys,
                "argv",
                ["calculate.py", json.dumps(analysis_payload())],
            ),
            patch.object(
                calculate,
                "read_frame_timestamps",
                side_effect=calculate.VideoTimestampError("Invalid timestamps."),
            ),
            contextlib.redirect_stdout(output),
        ):
            self.assertEqual(calculate.main(), 1)

        result = json.loads(output.getvalue())
        self.assertEqual(result["analysis_status"], "processing_error")
        self.assertEqual(result["error"], "Invalid timestamps.")

    def test_analysis_error_can_include_frame_diagnostics(self):
        output = io.StringIO()
        diagnostics = [{"frame_number": 1, "pose_detected": False}]

        with contextlib.redirect_stdout(output):
            status = calculate.emit_error(
                "Pose detection quality is insufficient.",
                analysis_status="detection_quality_insufficient",
                frame_count=1,
                accepted_point_count=0,
                frame_diagnostics=diagnostics,
            )

        self.assertEqual(status, 1)
        self.assertEqual(json.loads(output.getvalue()), {
            "analysis_status": "detection_quality_insufficient",
            "error": "Pose detection quality is insufficient.",
            "frame_count": 1,
            "accepted_point_count": 0,
            "frame_diagnostics": diagnostics,
        })

    def test_zero_one_or_two_accepted_frames_do_not_return_velocity_metrics(self):
        for accepted_count in range(3):
            pose = Mock()
            pose.close = Mock()
            pose.process = Mock(side_effect=[
                pose_result(0.1 + index * 0.1)
                if index < accepted_count
                else SimpleNamespace(pose_landmarks=None)
                for index in range(6)
            ])

            class VideoCapture:
                def __init__(self):
                    self.frames = iter(range(6))

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
                patch.object(
                    sys,
                    "argv",
                    ["calculate.py", json.dumps(analysis_payload())],
                ),
                patch.object(
                    calculate,
                    "read_frame_timestamps",
                    return_value=[index * 0.1 for index in range(6)],
                ),
                patch.object(calculate.cv2, "VideoCapture", return_value=VideoCapture()),
                patch.object(calculate.cv2, "cvtColor", side_effect=lambda image, _code: image),
                patch.object(calculate, "create_pose", return_value=pose),
                contextlib.redirect_stdout(output),
            ):
                with self.subTest(accepted_count=accepted_count):
                    self.assertEqual(calculate.main(), 1)

            result = json.loads(output.getvalue())
            self.assertEqual(
                result["analysis_status"],
                "detection_quality_insufficient",
            )
            self.assertEqual(result["accepted_point_count"], accepted_count)
            self.assertEqual(len(result["frame_diagnostics"]), 6)
            self.assertNotIn("velocity_max", result)
            self.assertNotIn("velocity_avg", result)
            self.assertNotIn("estimated_distance_m", result)
            self.assertNotIn("segment_speeds", result)

    def test_reference_run_distance_does_not_change_accepted_quality_or_speed(self):
        results = []

        for run_distance in (5, 100):
            pose = Mock()
            pose.close = Mock()
            pose.process = Mock(side_effect=[
                pose_result(0.1),
                pose_result(0.2),
                SimpleNamespace(pose_landmarks=None),
                pose_result(0.3),
                pose_result(0.4),
            ])

            class VideoCapture:
                def __init__(self):
                    self.frames = iter(range(5))

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
                patch.object(
                    sys,
                    "argv",
                    ["calculate.py", json.dumps(analysis_payload(run_distance))],
                ),
                patch.object(
                    calculate,
                    "read_frame_timestamps",
                    return_value=[0.0, 0.25, 0.5, 0.75, 1.0],
                ),
                patch.object(calculate.cv2, "VideoCapture", return_value=VideoCapture()),
                patch.object(calculate.cv2, "cvtColor", side_effect=lambda image, _code: image),
                patch.object(calculate, "create_pose", return_value=pose),
                contextlib.redirect_stdout(output),
            ):
                self.assertEqual(calculate.main(), 0)

            results.append(json.loads(output.getvalue()))

        self.assertAlmostEqual(results[0]["estimated_distance_m"], 3.0)
        self.assertAlmostEqual(results[0]["velocity_avg"], 3.0)
        self.assertEqual(results[0]["analysis_status"], "quality_check_passed")
        self.assertEqual(results[0]["pose_detection_count"], 4)
        self.assertEqual(results[0]["accepted_point_count"], 4)
        self.assertEqual(results[0]["estimated_distance_m"], results[1]["estimated_distance_m"])
        self.assertEqual(results[0]["velocity_avg"], results[1]["velocity_avg"])
        self.assertEqual(len(results[0]["frame_diagnostics"]), 5)
        self.assertEqual(
            [frame["pose_detected"] for frame in results[0]["frame_diagnostics"]],
            [True, True, False, True, True],
        )
        self.assertEqual(
            [frame["calculation_accepted"] for frame in results[0]["frame_diagnostics"]],
            [True, True, False, True, True],
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

    def test_detected_but_invalid_landmarks_are_not_adopted_or_serialized_as_nan(self):
        invalid_results = [
            pose_result(float("nan"), 0.9),
            pose_result(1.1, 0.9),
            pose_result(0.5, 0.49),
            pose_result(0.5, float("nan")),
        ]
        pose = Mock()
        pose.close = Mock()
        pose.process = Mock(side_effect=invalid_results)

        class VideoCapture:
            def __init__(self):
                self.frames = iter(range(4))

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
            patch.object(
                sys,
                "argv",
                ["calculate.py", json.dumps(analysis_payload())],
            ),
            patch.object(
                calculate,
                "read_frame_timestamps",
                return_value=[0.0, 0.1, 0.2, 0.3],
            ),
            patch.object(calculate.cv2, "VideoCapture", return_value=VideoCapture()),
            patch.object(calculate.cv2, "cvtColor", side_effect=lambda image, _code: image),
            patch.object(calculate, "create_pose", return_value=pose),
            contextlib.redirect_stdout(output),
        ):
            self.assertEqual(calculate.main(), 1)

        result = json.loads(output.getvalue())
        self.assertEqual(result["pose_detection_count"], 4)
        self.assertEqual(result["accepted_point_count"], 0)
        self.assertEqual(
            [frame["rejection_reason"] for frame in result["frame_diagnostics"]],
            [
                "non_finite_coordinate",
                "coordinate_out_of_frame",
                "low_visibility",
                "invalid_visibility",
            ],
        )
        self.assertIsNone(result["frame_diagnostics"][0]["landmark_x_px"])
        self.assertIsNone(result["frame_diagnostics"][3]["landmark_visibility"])


if __name__ == "__main__":
    unittest.main()
