import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import cv2
import numpy as np

import diagnose_camera_motion as diagnostic
from diagnose_camera_motion import (
    THRESHOLDS, background_mask, compose_to_reference, estimate_link, pose_box, project,
)
from pose_detection import analyze_pose_frame


class CameraMotionDiagnosticTest(unittest.TestCase):
    def setUp(self):
        grid = np.array([(x, y) for y in range(40, 441, 80)
                         for x in range(50, 591, 90)], np.float32)
        self.previous = grid
        self.forward = np.array([[1.0, 0.015, 24.0], [-0.01, 1.0, 8.0],
                                 [0.00003, -0.00002, 1.0]])
        self.current = project(self.forward, grid)

    def test_known_homography_and_reference_direction(self):
        matrix, info, inliers, held = estimate_link(self.previous, self.current, 640, 480)
        self.assertTrue(info['valid'], info)
        self.assertGreater(info['inliers'], 12)
        self.assertGreater(info['holdout_count'], 4)
        self.assertEqual(info['training_count'] + info['holdout_count'], len(self.previous))
        self.assertAlmostEqual(info['inlier_ratio'], info['inliers'] / info['training_count'])
        self.assertFalse(np.any(inliers & held))
        self.assertLess(info['holdout_median_error_px'], 0.01)
        to_reference, overlap, reason = compose_to_reference(np.eye(3), matrix, 640, 480, 1)
        self.assertEqual(reason, 'ok')
        self.assertGreater(overlap, .8)
        np.testing.assert_allclose(project(to_reference, self.current), self.previous, atol=.01)
        second = np.array([[1, 0, 12], [0, 1, -4], [0, 0, 1]], dtype=float)
        later, _, reason = compose_to_reference(to_reference, second, 640, 480, 2)
        self.assertEqual(reason, 'ok')
        np.testing.assert_allclose(project(later, project(second, self.current)), self.previous, atol=.01)

    def test_insufficient_and_clustered_points_fail_without_identity(self):
        matrix, info, _, _ = estimate_link(self.previous[:4], self.current[:4], 640, 480)
        self.assertIsNone(matrix)
        self.assertEqual(info['reason'], 'insufficient_correspondences')
        points = np.array([(100 + i % 5, 100 + i // 5) for i in range(30)], np.float32)
        matrix, info, _, _ = estimate_link(points, points + 1, 640, 480)
        self.assertIsNone(matrix)
        self.assertEqual(info['reason'], 'points_poorly_distributed')

    def test_nonfinite_singular_loss_of_overlap_and_chain_limit_fail(self):
        points = self.current.copy(); points[0, 0] = np.nan
        self.assertEqual(estimate_link(self.previous, points, 640, 480)[1]['reason'], 'non_finite_points')
        self.assertEqual(compose_to_reference(np.eye(3), np.zeros((3,3)), 640, 480, 1)[2], 'invalid_composed_transform')
        far = np.array([[1,0,1000],[0,1,0],[0,0,1]], dtype=float)
        self.assertEqual(compose_to_reference(np.eye(3), far, 640, 480, 1)[2], 'insufficient_reference_overlap')
        self.assertEqual(compose_to_reference(np.eye(3), np.eye(3), 640, 480, THRESHOLDS['max_chain_frames']+1)[2], 'chain_limit_exceeded')

    def test_holdout_detects_bad_unseen_correspondences(self):
        bad = self.current.copy()
        bad[::5] += 50
        matrix, info, _, _ = estimate_link(self.previous, bad, 640, 480)
        self.assertIsNone(matrix)
        self.assertEqual(info['reason'], 'high_holdout_error')

    def test_roi_coordinates_restored_before_reference_transform(self):
        landmark = Mock(x=.6, y=.5, visibility=.99)
        pose = Mock()
        pose.process.return_value.pose_landmarks.landmark = [landmark] * 33
        frame = np.zeros((480, 640, 3), np.uint8)
        result = analyze_pose_frame(pose, frame, (100, 50, 200, 100))
        hip = result['right_hip']
        self.assertEqual((hip['x_px'], hip['y_px']), (220, 100))
        transform = np.array([[1,0,-10],[0,1,5],[0,0,1]], dtype=float)
        np.testing.assert_allclose(project(transform, [[hip['x_px'], hip['y_px']]]), [[210,105]])

    def test_runner_box_and_manual_mask_exclude_background_features(self):
        points = [{'x_px': 200 + i, 'y_px': 100 + i} for i in range(33)]
        box = pose_box({'landmarks': points}, 640, 480)
        self.assertIsNotNone(box)
        mask = background_mask(640, 480, [box, (10, 20, 40, 50)])
        self.assertEqual(mask[110, 210], 0)
        self.assertEqual(mask[30, 20], 0)
        self.assertEqual(mask[400, 600], 255)

    def test_sequence_saves_diagnostics_and_never_recovers_after_failed_link(self):
        rng = np.random.default_rng(9)
        reference = rng.integers(0, 256, (240, 320, 3), dtype=np.uint8)
        moved = cv2.warpAffine(reference, np.float32([[1, 0, 5], [0, 1, 3]]), (320, 240))
        frames = [reference, moved, np.zeros_like(reference), reference, moved]
        capture = Mock()
        capture.isOpened.return_value = True
        capture.read.side_effect = [(True, frame.copy()) for frame in frames]
        pose = Mock()
        empty_pose = {'pose_detected': False, 'right_hip': None, 'landmarks': []}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            video = root / 'source.mp4'
            video.touch()
            output = root / 'result'
            with (
                patch.object(diagnostic, 'PRIVATE_ROOT', root),
                patch.object(diagnostic, 'read_frame_timestamps', return_value=[5.0, 5.04, 5.09, 5.15, 5.20]),
                patch.object(diagnostic.cv2, 'VideoCapture', return_value=capture),
                patch.object(diagnostic, 'create_pose', return_value=pose),
                patch.object(diagnostic, 'analyze_pose_frame', return_value=empty_pose),
            ):
                self.assertEqual(diagnostic.run(video, output, 'ffprobe', None, [(0, 0, 20, 20)], 5, 1,
                                                [(2, 3, (50, 50, 30, 30))], [2, 5]), 5)
            result = json.loads((output / 'diagnostics.json').read_text())
            rows = result['frames']
            self.assertEqual([row['frame_number'] for row in rows], [1, 2, 3, 4, 5])
            self.assertAlmostEqual(rows[1]['timestamp_seconds'], .04)
            self.assertTrue(rows[1]['valid'], rows[1])
            restored = project(np.asarray(rows[1]['current_to_reference']), [[165, 123]])
            np.testing.assert_allclose(restored, [[160, 120]], atol=1.0)
            self.assertFalse(rows[2]['valid'])
            self.assertEqual(rows[3]['reason'], 'previous_transform_invalid')
            self.assertIsNone(rows[3]['current_to_reference'])
            self.assertTrue(rows[4]['local_valid'])
            self.assertFalse(rows[4]['reference_valid'])
            self.assertEqual(rows[4]['reference_reason'], 'previous_transform_invalid')
            self.assertEqual(rows[0]['manual_exclusion_boxes'], [[0, 0, 20, 20]])
            self.assertEqual(rows[1]['manual_exclusion_boxes'], [[0, 0, 20, 20], [50, 50, 30, 30]])
            self.assertEqual(rows[3]['manual_exclusion_boxes'], [[0, 0, 20, 20]])
            self.assertTrue((output / 'frame-000002.jpg').is_file())
            self.assertFalse((output / 'frame-000001.jpg').exists())
        capture.release.assert_called_once()
        pose.close.assert_called_once()

    def test_direct_reconnection_skips_gap_without_filling_it(self):
        rng = np.random.default_rng(28)
        first = rng.integers(0, 256, (240, 320, 3), dtype=np.uint8)
        shifted = cv2.warpAffine(first, np.float32([[1, 0, 5], [0, 1, 3]]), (320, 240))
        later = cv2.warpAffine(first, np.float32([[1, 0, 8], [0, 1, 4]]), (320, 240))
        capture = Mock()
        capture.isOpened.return_value = True
        capture.read.side_effect = [(True, f.copy()) for f in [first, shifted, np.zeros_like(first), later]]
        pose = Mock()
        empty_pose = {'pose_detected': False, 'right_hip': None, 'landmarks': []}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            video = root / 'video.mp4'
            video.touch()
            output = root / 'result'
            with (
                patch.object(diagnostic, 'PRIVATE_ROOT', root),
                patch.object(diagnostic, 'read_frame_timestamps', return_value=[0., .1, .2, .3]),
                patch.object(diagnostic.cv2, 'VideoCapture', return_value=capture),
                patch.object(diagnostic, 'create_pose', return_value=pose),
                patch.object(diagnostic, 'analyze_pose_frame', return_value=empty_pose),
            ):
                diagnostic.run(video, output, 'ffprobe', None, [(0, 0, 10, 10)], 4, 1,
                               reconnect_anchor=2, reconnect_candidates=[4], segment_start=4)
            rows = json.loads((output / 'diagnostics.json').read_text())['frames']
        self.assertFalse(rows[2]['reference_valid'])
        self.assertIsNone(rows[2]['current_to_reference'])
        self.assertFalse(rows[3]['local_valid'])
        self.assertTrue(rows[3]['direct_reconnection']['local_valid'])
        self.assertTrue(rows[3]['reference_valid'])
        self.assertEqual(rows[3]['reference_reason'], 'reconnected')
        self.assertEqual(rows[3]['segment_reason'], 'segment_origin')
        restored = project(np.asarray(rows[3]['current_to_reference']), [[168, 124]])
        np.testing.assert_allclose(restored, [[160, 120]], atol=1)


if __name__ == '__main__':
    unittest.main()
