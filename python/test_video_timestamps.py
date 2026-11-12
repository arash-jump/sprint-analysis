import json
import subprocess
import unittest
from unittest.mock import patch

from video_timestamps import (
    VideoTimestampError,
    parse_frame_timestamps,
    read_frame_timestamps,
)


class VideoTimestampTest(unittest.TestCase):
    def test_parses_variable_frame_rate_presentation_timestamps(self):
        timestamps = parse_frame_timestamps(json.dumps({
            "frames": [
                {"best_effort_timestamp_time": "0.000000"},
                {"best_effort_timestamp_time": "0.033367"},
                {"best_effort_timestamp_time": "0.100100"},
            ],
        }))

        self.assertEqual(timestamps, [0.0, 0.033367, 0.1001])

    def test_rejects_missing_invalid_and_non_increasing_timestamps(self):
        for probe_output in (
            '{"frames":[]}',
            '{"frames":[{}]}',
            '{"frames":[{"best_effort_timestamp_time":"N/A"}]}',
            '{"frames":[{"best_effort_timestamp_time":"NaN"}]}',
            '{"frames":[{"best_effort_timestamp_time":"0"},{"best_effort_timestamp_time":"0"}]}',
            '{"frames":[{"best_effort_timestamp_time":"1"},{"best_effort_timestamp_time":"0"}]}',
        ):
            with self.subTest(probe_output=probe_output):
                with self.assertRaises(VideoTimestampError):
                    parse_frame_timestamps(probe_output)

    @patch("video_timestamps.subprocess.run")
    def test_invokes_ffprobe_with_argument_list_and_returns_timestamps(self, run):
        run.return_value.stdout = '{"frames":[{"best_effort_timestamp_time":"0.0"}]}'

        timestamps = read_frame_timestamps("/private/video with spaces.mp4", "/usr/bin/ffprobe")

        self.assertEqual(timestamps, [0.0])
        self.assertEqual(run.call_args.args[0], [
            "/usr/bin/ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "frame=best_effort_timestamp_time",
            "-of",
            "json",
            "/private/video with spaces.mp4",
        ])
        self.assertTrue(run.call_args.kwargs["check"])
        self.assertEqual(run.call_args.kwargs["timeout"], 600)

    @patch("video_timestamps.subprocess.run", side_effect=FileNotFoundError)
    def test_reports_missing_ffprobe_without_falling_back_to_an_assumed_fps(self, _run):
        with self.assertRaisesRegex(VideoTimestampError, "Install FFmpeg/FFprobe"):
            read_frame_timestamps("/private/video.mp4", "missing-ffprobe")

    @patch(
        "video_timestamps.subprocess.run",
        side_effect=subprocess.TimeoutExpired("ffprobe", 600),
    )
    def test_reports_ffprobe_timeout(self, _run):
        with self.assertRaisesRegex(VideoTimestampError, "timed out"):
            read_frame_timestamps("/private/video.mp4", "ffprobe")


if __name__ == "__main__":
    unittest.main()
