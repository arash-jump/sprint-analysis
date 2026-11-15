import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np

import diagnose_pose
from diagnose_pose import (
    MAX_DIAGNOSTIC_IMAGES,
    diagnose_video,
    select_diagnostic_frames,
    validate_output_directory,
)


class SelectDiagnosticFramesTest(unittest.TestCase):
    def test_image_selection_is_bounded_and_includes_detected_neighbors_and_misses(self):
        diagnostics = []
        for index in range(120):
            detected = index % 8 == 3
            diagnostics.append({
                "frame_number": index + 1,
                "timestamp_seconds": index / 30,
                "pose_detected": detected,
                "calculation_accepted": detected,
            })

        selected = select_diagnostic_frames(diagnostics)
        categories = {
            label
            for labels in selected.values()
            for label in labels
        }

        self.assertLessEqual(len(selected), MAX_DIAGNOSTIC_IMAGES)
        self.assertIn("detected_representative", categories)
        self.assertIn("before_detected_representative", categories)
        self.assertIn("after_detected_representative", categories)
        self.assertIn("undetected_representative", categories)

    def test_unavailable_pose_results_still_produce_undetected_representatives(self):
        diagnostics = [
            {
                "frame_number": index + 1,
                "timestamp_seconds": index / 30,
                "pose_detected": False,
                "calculation_accepted": False,
            }
            for index in range(30)
        ]

        selected = select_diagnostic_frames(diagnostics)

        self.assertTrue(selected)
        self.assertTrue(all(
            "undetected_representative" in labels
            for labels in selected.values()
        ))

    def test_video_diagnostic_writes_json_and_selected_images_for_requested_window(self):
        accepted_pose = {
            "pose_detected": True,
            "right_hip": {
                "x_px": 10.0,
                "y_px": 20.0,
                "x_normalized": 0.5,
                "y_normalized": 0.5,
                "visibility": 0.9,
            },
            "landmarks": [],
        }
        no_pose = {
            "pose_detected": False,
            "right_hip": None,
            "landmarks": [],
        }
        pose_frames = [
            accepted_pose,
            accepted_pose,
            accepted_pose,
            accepted_pose,
            no_pose,
        ]
        video_bytes = b"unchanged video"

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            video_path = root / "input.mp4"
            video_path.write_bytes(video_bytes)
            output_dir = root / "diagnostics"

            class VideoCapture:
                def __init__(self, _path):
                    self.frames = iter(range(5))

                def isOpened(self):
                    return True

                def read(self):
                    try:
                        next(self.frames)
                    except StopIteration:
                        return False, None
                    return True, np.zeros((40, 60, 3), dtype=np.uint8)

                def release(self):
                    pass

            pose_instances = [Mock(), Mock()]

            def write_image(path, _frame):
                Path(path).write_bytes(b"diagnostic image")
                return True

            with (
                patch.object(
                    diagnose_pose,
                    "read_frame_timestamps",
                    return_value=[0.0, 0.1, 0.2, 0.3, 0.4],
                ),
                patch.object(diagnose_pose.cv2, "VideoCapture", VideoCapture),
                patch.object(diagnose_pose, "create_pose", side_effect=pose_instances),
                patch.object(
                    diagnose_pose,
                    "analyze_pose_frame",
                    side_effect=pose_frames + pose_frames,
                ) as analyze_frame,
                patch.object(
                    diagnose_pose,
                    "_draw_label",
                    side_effect=lambda frame, *_args: frame,
                ),
                patch.object(diagnose_pose.cv2, "imwrite", side_effect=write_image),
            ):
                report = diagnose_video(
                    video_path,
                    output_dir,
                    start_seconds=0.1,
                    end_seconds=0.3,
                    roi=(5, 6, 20, 25),
                )

            diagnostics = json.loads(
                (output_dir / "diagnostics.json").read_text(encoding="utf-8")
            )
            self.assertEqual(report["frame_count"], 3)
            self.assertEqual(report["total_video_frame_count"], 5)
            self.assertEqual(
                report["roi"],
                {"x": 5, "y": 6, "width": 20, "height": 25},
            )
            self.assertEqual(diagnostics["selected_time_window_seconds"], {
                "start": 0.1,
                "end": 0.3,
            })
            self.assertLessEqual(
                len(report["diagnostic_images"]),
                MAX_DIAGNOSTIC_IMAGES,
            )
            self.assertTrue(all(
                (output_dir / image["file"]).is_file()
                for image in report["diagnostic_images"]
            ))
            self.assertTrue(all(
                call.args[2] == (5, 6, 20, 25)
                for call in analyze_frame.call_args_list
            ))
            self.assertEqual(video_path.read_bytes(), video_bytes)

    def test_output_inside_repository_must_be_in_private_ignored_directory(self):
        private_dir = (
            diagnose_pose.PROJECT_ROOT
            / "storage"
            / "app"
            / "private"
            / "pose-diagnostics"
            / "sample"
        )
        self.assertEqual(
            validate_output_directory(private_dir),
            private_dir.resolve(),
        )
        with self.assertRaisesRegex(ValueError, "only under"):
            validate_output_directory(diagnose_pose.PROJECT_ROOT / "python" / "images")
        with self.assertRaisesRegex(ValueError, "public directory"):
            validate_output_directory(diagnose_pose.PROJECT_ROOT / "public" / "images")


if __name__ == "__main__":
    unittest.main()
