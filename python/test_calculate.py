import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import calculate
from analysis_metrics import calculate_velocity_metrics
from analysis_quality import assess_detection_quality
from measurement_interval import MeasurementFrameRange
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


class FakeCapture:
    def __init__(self, frames):
        self.frames = iter(frames)
        self.read_count = 0
        self.released = False

    def isOpened(self):
        return True

    def read(self):
        self.read_count += 1
        try:
            return True, next(self.frames)
        except StopIteration:
            return False, None

    def release(self):
        self.released = True


class CalculateInputTest(unittest.TestCase):
    def test_measurement_range_parser_defaults_and_rejects_invalid_values(self):
        self.assertEqual(
            calculate.parse_measurement_range({}, 5),
            MeasurementFrameRange(1, 5, 5),
        )
        for payload in (
            {"measurement_start_frame": 0},
            {"measurement_start_frame": 4, "measurement_end_frame": 3},
            {"measurement_end_frame": 6},
            {"measurement_start_frame": True},
            {"measurement_end_frame": float("nan")},
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    calculate.parse_measurement_range(payload, 5)

    def test_roi_parser_requires_four_integer_pixel_coordinates(self):
        self.assertEqual(calculate.parse_roi([20, 10, 300, 180]), (20, 10, 300, 180))
        self.assertEqual(
            calculate.parse_roi({"x": 20, "y": 10, "width": 300, "height": 180}),
            (20, 10, 300, 180),
        )
        self.assertIsNone(calculate.parse_roi(None))
        for roi in (
            [1, 2, 3],
            [0, 0, 10, 10.5],
            [False, 0, 10, 10],
            {"x": 0, "y": 0, "width": 10},
            {"x": 0, "y": 0, "width": 10, "height": 10.5},
        ):
            with self.subTest(roi=roi):
                with self.assertRaises(ValueError):
                    calculate.parse_roi(roi)

    def test_warmup_uses_one_model_and_only_interval_points_reach_velocity(self):
        frames = [object() for _ in range(6)]
        capture = FakeCapture(frames)
        pose = Mock()
        per_frame_x = [10000, 9000, 300, 200, 100, -5000]
        pose_frames = [
            {
                "pose_detected": True,
                "right_hip": {
                    "x_px": x,
                    "y_px": 20,
                    "visibility": 0.9,
                },
            }
            for x in per_frame_x
        ]
        analyze_calls = []

        def analyze(passed_pose, frame, roi):
            analyze_calls.append((passed_pose, frame, roi))
            return pose_frames[len(analyze_calls) - 1]

        with (
            patch.object(calculate.cv2, "VideoCapture", return_value=capture),
            patch.object(calculate, "create_pose", return_value=pose) as create_pose,
            patch.object(calculate, "analyze_pose_frame", side_effect=analyze),
            patch.object(
                calculate,
                "assess_right_hip",
                side_effect=lambda landmark: (landmark is not None, None),
            ),
        ):
            all_diagnostics, interval_diagnostics, positions = calculate.analyze_video(
                "/private/video.mp4",
                [0.0, 0.04, 0.12, 0.4, 0.95, 1.0],
                MeasurementFrameRange(3, 5, 6),
                (10, 20, 300, 100),
            )

        create_pose.assert_called_once_with()
        self.assertTrue(capture.released)
        pose.close.assert_called_once_with()
        self.assertEqual([call[0] for call in analyze_calls], [pose] * 5)
        self.assertEqual([call[1] for call in analyze_calls], frames[:5])
        self.assertEqual([call[2] for call in analyze_calls], [(10, 20, 300, 100)] * 5)
        self.assertEqual(len(all_diagnostics), 5)
        self.assertEqual(len(interval_diagnostics), 3)
        self.assertEqual(
            [diagnostic["within_measurement_interval"] for diagnostic in all_diagnostics],
            [False, False, True, True, True],
        )
        self.assertEqual(
            [diagnostic["rejection_reason"] for diagnostic in all_diagnostics[:2]],
            ["outside_measurement_interval", "outside_measurement_interval"],
        )
        self.assertEqual(positions, [(0.12, 300), (0.4, 200), (0.95, 100)])
        self.assertEqual(
            calculate_velocity_metrics(positions, scale_m_per_px=1)["estimated_distance_m"],
            200,
        )
        self.assertEqual(
            assess_detection_quality(interval_diagnostics)["frame_count"],
            3,
        )

    def test_model_stops_at_inclusive_end_and_range_uses_variable_timestamps(self):
        frames = [object() for _ in range(5)]
        capture = FakeCapture(frames)
        pose = Mock()
        calls = []

        def analyze(_pose, frame, _roi):
            calls.append(frame)
            return {"pose_detected": False, "right_hip": None}

        with (
            patch.object(calculate.cv2, "VideoCapture", return_value=capture),
            patch.object(calculate, "create_pose", return_value=pose),
            patch.object(calculate, "analyze_pose_frame", side_effect=analyze),
        ):
            diagnostics, interval_diagnostics, positions = calculate.analyze_video(
                "/private/video.mp4",
                [0.0, 0.1, 0.3, 0.7, 0.8],
                MeasurementFrameRange(2, 3, 5),
                None,
            )

        self.assertEqual(len(calls), 3)
        self.assertEqual(len(diagnostics), 3)
        self.assertEqual([item["frame_number"] for item in interval_diagnostics], [2, 3])
        self.assertEqual(positions, [])

    def test_pose_records_reuse_inference_landmarks_and_clear_undetected_frames(self):
        frames = [object(), object()]
        capture = FakeCapture(frames)
        landmarks = [
            {"x_px": float(index), "y_px": float(index + 10)}
            for index in range(33)
        ]
        pose_frames = [
            {
                "pose_detected": True,
                "right_hip": {
                    "x_px": landmarks[24]["x_px"],
                    "y_px": landmarks[24]["y_px"],
                    "visibility": 0.9,
                },
                "landmarks": landmarks,
            },
            {"pose_detected": False, "right_hip": None, "landmarks": []},
        ]
        pose = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            records_path = f"{temp_dir}/poses.jsonl"
            with (
                patch.object(calculate.cv2, "VideoCapture", return_value=capture),
                patch.object(calculate, "create_pose", return_value=pose),
                patch.object(calculate, "analyze_pose_frame", side_effect=pose_frames),
                patch.object(
                    calculate,
                    "assess_right_hip",
                    side_effect=lambda landmark: (landmark is not None, None),
                ),
            ):
                diagnostics, _interval, _positions = calculate.analyze_video(
                    "/private/video.mp4",
                    [0.0, 0.1],
                    MeasurementFrameRange(2, 2, 2),
                    (50, 20, 100, 50),
                    records_path,
                )

            records = [
                json.loads(line)
                for line in Path(records_path)
                .read_text(encoding="utf-8")
                .splitlines()
            ]

        self.assertEqual(len(diagnostics), 2)
        self.assertEqual(records[0]["landmarks"][24], [24.0, 34.0])
        self.assertEqual(records[0]["roi"], {
            "x": 50,
            "y": 20,
            "width": 100,
            "height": 50,
        })
        self.assertFalse(records[0]["within_measurement_interval"])
        self.assertFalse(records[0]["calculation_accepted"])
        self.assertFalse(records[1]["pose_detected"])
        self.assertEqual(records[1]["landmarks"], [])

    def test_short_selected_interval_fails_quality_without_speed_metrics(self):
        pose = Mock()
        pose.close = Mock()
        pose.process = Mock(side_effect=[
            pose_result(0.1),
            pose_result(0.2),
            pose_result(0.3),
            pose_result(0.4),
        ])
        capture = FakeCapture([
            SimpleNamespace(shape=(100, 100, 3))
            for _ in range(6)
        ])
        payload = analysis_payload()
        payload.update({
            "measurement_start_frame": 2,
            "measurement_end_frame": 4,
        })
        output = io.StringIO()
        with (
            patch.object(sys, "argv", ["calculate.py", json.dumps(payload)]),
            patch.object(calculate, "read_frame_timestamps", return_value=[
                0.0, 0.1, 0.3, 0.7, 0.8, 1.0,
            ]),
            patch.object(calculate.cv2, "VideoCapture", return_value=capture),
            patch.object(calculate.cv2, "cvtColor", side_effect=lambda image, _code: image),
            patch.object(calculate, "create_pose", return_value=pose),
            contextlib.redirect_stdout(output),
        ):
            self.assertEqual(calculate.main(), 1)

        result = json.loads(output.getvalue())
        self.assertEqual(result["analysis_status"], "detection_quality_insufficient")
        self.assertEqual(result["frame_count"], 3)
        self.assertEqual(result["accepted_point_count"], 3)
        self.assertEqual(result["model_input_frame_count"], 4)
        self.assertEqual(result["measurement_interval"]["start_frame"], 2)
        self.assertEqual(result["measurement_interval"]["end_frame"], 4)
        self.assertAlmostEqual(
            result["measurement_interval"]["start_timestamp_seconds"],
            0.1,
        )
        self.assertAlmostEqual(
            result["measurement_interval"]["end_timestamp_seconds"],
            0.7,
        )
        self.assertTrue(result["measurement_interval"]["boundaries_inclusive"])
        self.assertEqual(len(result["frame_diagnostics"]), 4)
        self.assertFalse(result["frame_diagnostics"][0]["calculation_accepted"])
        self.assertNotIn("velocity_max", result)

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
