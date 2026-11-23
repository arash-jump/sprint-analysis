import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np

from pose_overlay_video import (
    build_setpts_expression,
    _draw_frame,
    _draw_status,
    render_pose_overlay_video,
)


class PoseOverlayVideoTest(unittest.TestCase):
    def test_missing_ffmpeg_reports_safe_specific_failure(self):
        capture = Mock()
        capture.isOpened.return_value = True
        capture.read.return_value = (True, np.zeros((8, 8, 3), dtype=np.uint8))
        with tempfile.TemporaryDirectory() as directory:
            records = Path(directory) / 'records.jsonl'
            records.write_text(json.dumps({'frame_number': 1, 'timestamp_seconds': 0.0}) + '\n')
            with (
                patch('pose_overlay_video.read_frame_timestamps', return_value=[0.0]),
                patch('pose_overlay_video.cv2.VideoCapture', return_value=capture),
                patch('pose_overlay_video.subprocess.Popen', side_effect=FileNotFoundError('private path')),
                self.assertRaisesRegex(RuntimeError, 'FFmpeg executable could not be found'),
            ):
                render_pose_overlay_video(Path('source'), records, 'ffprobe', 'ffmpeg', Path(directory) / 'out.mp4')
        capture.release.assert_called_once_with()

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg is required')
    def test_real_encoder_preserves_frame_timestamps(self):
        from video_timestamps import read_frame_timestamps

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'source.mp4'
            output = Path(directory) / 'output.mp4'
            records = Path(directory) / 'records.jsonl'
            subprocess.run([
                'ffmpeg', '-loglevel', 'error', '-f', 'lavfi', '-i',
                'color=size=160x120:rate=30:duration=0.2', '-c:v', 'libx264',
                '-pix_fmt', 'yuv420p', str(source),
            ], check=True)
            timestamps = read_frame_timestamps(str(source), 'ffprobe')
            records.write_text(''.join(json.dumps({
                'frame_number': i + 1,
                'timestamp_seconds': timestamp - timestamps[0],
                'pose_detected': False,
                'within_measurement_interval': True,
                'calculation_accepted': False,
                'landmarks': [],
            }) + '\n' for i, timestamp in enumerate(timestamps)))
            render_pose_overlay_video(source, records, 'ffprobe', 'ffmpeg', output)
            actual = read_frame_timestamps(str(output), 'ffprobe')
            self.assertEqual(len(actual), len(timestamps))
            for expected, observed in zip(timestamps, actual):
                self.assertAlmostEqual(expected - timestamps[0], observed - actual[0], places=6)

    def test_setpts_expression_preserves_variable_frame_timestamps(self):
        self.assertEqual(
            build_setpts_expression([0.0, 0.033, 0.1]),
            "if(lt(N\\,1)\\,0\\,if(lt(N\\,2)\\,33000\\,100000))",
        )

    def test_setpts_rejects_timestamps_that_cannot_be_represented(self):
        with self.assertRaises(ValueError):
            build_setpts_expression([0.0, 0.0000004, 0.1])

    def test_renderer_uses_records_in_order_and_ffprobe_pts_without_inference(self):
        records = [
            {
                "frame_number": index + 1,
                "timestamp_seconds": timestamp,
                "pose_detected": True,
                "within_measurement_interval": index == 1,
                "calculation_accepted": index == 1,
                "rejection_reason": None if index == 1 else "outside_measurement_interval",
                "roi": {"x": 1, "y": 1, "width": 4, "height": 3},
                "landmarks": [[float(point), float(point + 1)] for point in range(33)],
            }
            for index, timestamp in enumerate([0.0, 0.033, 0.1])
        ]
        source_frames = [
            np.full((8, 8, 3), index, dtype=np.uint8)
            for index in range(3)
        ]
        capture = Mock()
        capture.isOpened.return_value = True
        capture.read.side_effect = [(True, frame.copy()) for frame in source_frames]
        capture.release = Mock()
        process = Mock()
        written_frames = bytearray()
        process.stdin.write.side_effect = written_frames.extend
        process.wait.return_value = 0
        raw_input = {}

        def fake_popen(command, **kwargs):
            raw_input["filter_graph"] = Path(command[command.index("-/filter_complex") + 1]).read_text()
            raw_input["process"] = process
            return process

        with tempfile.TemporaryDirectory() as temp_dir:
            records_path = Path(temp_dir) / "poses.jsonl"
            records_path.write_text(
                "".join(json.dumps(record) + "\n" for record in records),
                encoding="utf-8",
            )
            with (
                patch("pose_overlay_video.read_frame_timestamps", return_value=[10.0, 10.033, 10.1]),
                patch("pose_overlay_video.cv2.VideoCapture", return_value=capture),
                patch("pose_overlay_video.subprocess.Popen", side_effect=fake_popen),
                patch("pose_overlay_video._draw_frame") as draw_frame,
            ):
                rendered_count = render_pose_overlay_video(
                    Path("source.mp4"),
                    records_path,
                    "ffprobe",
                    "ffmpeg",
                    Path(temp_dir) / "output.mp4",
                )

        self.assertEqual(rendered_count, 3)
        self.assertEqual(
            [call.args[1]["frame_number"] for call in draw_frame.call_args_list],
            [1, 2, 3],
        )
        self.assertIn("33000", raw_input["filter_graph"])
        self.assertIn("100000", raw_input["filter_graph"])
        self.assertEqual(len(written_frames), 3 * 8 * 8 * 3)
        capture.release.assert_called_once_with()
        process.wait.assert_called_once_with()

    def test_landmark_coordinates_are_drawn_in_the_original_video_space(self):
        record = {
            "frame_number": 1,
            "timestamp_seconds": 0.0,
            "pose_detected": True,
            "within_measurement_interval": True,
            "calculation_accepted": True,
            "landmarks": [[float(point + 350), float(point + 300)] for point in range(33)],
        }
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        with patch("pose_overlay_video.draw_pose_overlay") as draw_pose_overlay:
            _draw_frame(frame, record, {"x": 350, "y": 300, "width": 1300, "height": 300})

        landmarks = draw_pose_overlay.call_args.args[1]
        self.assertEqual(landmarks[0], {"x_px": 350.0, "y_px": 300.0})
        self.assertEqual(landmarks[32], {"x_px": 382.0, "y_px": 332.0})

    def test_status_distinguishes_interval_detection_and_hip_acceptance(self):
        cases = [
            (
                {
                    "frame_number": 1,
                    "timestamp_seconds": 0.0,
                    "within_measurement_interval": False,
                    "pose_detected": False,
                    "calculation_accepted": False,
                },
                ["OUTSIDE INTERVAL - NOT MEASURED", "POSE NOT DETECTED", "RIGHT HIP NOT USED"],
            ),
            (
                {
                    "frame_number": 2,
                    "timestamp_seconds": 0.1,
                    "within_measurement_interval": True,
                    "pose_detected": True,
                    "calculation_accepted": False,
                    "rejection_reason": "low_visibility",
                },
                ["MEASUREMENT INTERVAL", "POSE DETECTED", "RIGHT HIP NOT ACCEPTED (low_visibility)"],
            ),
            (
                {
                    "frame_number": 3,
                    "timestamp_seconds": 0.2,
                    "within_measurement_interval": True,
                    "pose_detected": True,
                    "calculation_accepted": True,
                },
                ["MEASUREMENT INTERVAL", "POSE DETECTED", "RIGHT HIP ACCEPTED"],
            ),
        ]
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        for record, expected_labels in cases:
            labels = []
            with (
                patch("pose_overlay_video.cv2.putText", side_effect=lambda _, text, *args: labels.append(text)),
                patch("pose_overlay_video.cv2.rectangle"),
            ):
                _draw_status(frame.copy(), record, None)
            for label in expected_labels:
                self.assertTrue(any(label in text for text in labels), (label, labels))

    def test_missing_pose_does_not_draw_previous_landmarks(self):
        frame = np.zeros((8, 8, 3), dtype=np.uint8)
        record = {
            "frame_number": 2,
            "timestamp_seconds": 0.1,
            "within_measurement_interval": True,
            "pose_detected": False,
            "calculation_accepted": False,
            "landmarks": [],
        }
        with (
            patch("pose_overlay_video.draw_pose_overlay") as draw_pose_overlay,
            patch("pose_overlay_video.cv2.putText"),
            patch("pose_overlay_video.cv2.rectangle"),
        ):
            _draw_frame(frame, record, None)

        draw_pose_overlay.assert_not_called()

    def test_renderer_preserves_ffmpeg_error_when_input_pipe_closes(self):
        record = {
            "frame_number": 1,
            "timestamp_seconds": 0.0,
            "pose_detected": False,
            "within_measurement_interval": False,
            "calculation_accepted": False,
        }
        capture = Mock()
        capture.isOpened.return_value = True
        capture.read.return_value = (True, np.zeros((8, 8, 3), dtype=np.uint8))
        process = Mock()
        process.stdin.write.side_effect = BrokenPipeError()
        process.poll.return_value = 1
        process.wait.return_value = 1

        def fake_popen(command, **kwargs):
            kwargs["stderr"].write(b"invalid filter graph")
            return process

        with tempfile.TemporaryDirectory() as temp_dir:
            records_path = Path(temp_dir) / "poses.jsonl"
            records_path.write_text(json.dumps(record) + "\n", encoding="utf-8")
            with (
                patch("pose_overlay_video.read_frame_timestamps", return_value=[10.0]),
                patch("pose_overlay_video.cv2.VideoCapture", return_value=capture),
                patch("pose_overlay_video.subprocess.Popen", side_effect=fake_popen),
                patch("pose_overlay_video._draw_frame"),
                self.assertRaisesRegex(RuntimeError, "invalid filter graph"),
            ):
                render_pose_overlay_video(
                    Path("source.mp4"),
                    records_path,
                    "ffprobe",
                    "ffmpeg",
                    Path(temp_dir) / "output.mp4",
                )

        process.wait.assert_called_once_with()
        capture.release.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
