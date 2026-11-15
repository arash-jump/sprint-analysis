import math
import unittest

from analysis_quality import assess_detection_quality, assess_right_hip


def frame(number, timestamp, pose_detected, accepted):
    return {
        "frame_number": number,
        "timestamp_seconds": timestamp,
        "pose_detected": pose_detected,
        "calculation_accepted": accepted,
        "rejection_reason": (
            None
            if accepted
            else ("pose_not_detected" if not pose_detected else "low_visibility")
        ),
    }


class AssessRightHipTest(unittest.TestCase):
    def test_accepts_finite_in_frame_coordinates_with_sufficient_visibility(self):
        accepted, reason = assess_right_hip({
            "x_normalized": 1.0,
            "y_normalized": 0.0,
            "visibility": 0.5,
        })

        self.assertTrue(accepted)
        self.assertIsNone(reason)

    def test_rejects_non_finite_coordinates_out_of_frame_and_low_visibility(self):
        invalid_landmarks = [
            ({"x_normalized": math.nan, "y_normalized": 0.5, "visibility": 0.9},
             "non_finite_coordinate"),
            ({"x_normalized": 1.01, "y_normalized": 0.5, "visibility": 0.9},
             "coordinate_out_of_frame"),
            ({"x_normalized": 0.5, "y_normalized": 0.5, "visibility": 0.49},
             "low_visibility"),
            ({"x_normalized": 0.5, "y_normalized": 0.5, "visibility": math.inf},
             "invalid_visibility"),
        ]

        for landmark, expected_reason in invalid_landmarks:
            with self.subTest(expected_reason=expected_reason):
                accepted, reason = assess_right_hip(landmark)
                self.assertFalse(accepted)
                self.assertEqual(reason, expected_reason)


class AssessDetectionQualityTest(unittest.TestCase):
    def test_zero_one_two_or_three_accepted_frames_never_pass(self):
        for accepted_count in range(4):
            diagnostics = [
                frame(
                    index + 1,
                    index * 0.1,
                    pose_detected=index < accepted_count,
                    accepted=index < accepted_count,
                )
                for index in range(5)
            ]

            with self.subTest(accepted_count=accepted_count):
                report = assess_detection_quality(diagnostics)
                self.assertEqual(
                    report["analysis_status"],
                    "detection_quality_insufficient",
                )
                self.assertEqual(report["accepted_point_count"], accepted_count)

    def test_good_sample_reports_detection_and_accepted_rates_separately(self):
        diagnostics = [
            frame(1, 0.0, True, True),
            frame(2, 0.1, True, False),
            frame(3, 0.2, True, True),
            frame(4, 0.3, True, True),
            frame(5, 0.4, True, True),
        ]

        report = assess_detection_quality(diagnostics)

        self.assertEqual(report["analysis_status"], "quality_check_passed")
        self.assertEqual(report["pose_detection_count"], 5)
        self.assertEqual(report["accepted_point_count"], 4)
        self.assertAlmostEqual(report["pose_detection_rate"], 1.0)
        self.assertAlmostEqual(report["accepted_point_rate"], 4 / 5)

    def test_variable_timestamps_measure_missing_intervals_in_seconds(self):
        diagnostics = [
            frame(1, 0.0, True, True),
            frame(2, 0.1, True, True),
            frame(3, 0.2, False, False),
            frame(4, 0.9, False, False),
            frame(5, 1.0, True, True),
            frame(6, 1.1, True, True),
            frame(7, 1.2, True, True),
            frame(8, 1.3, True, True),
        ]

        report = assess_detection_quality(diagnostics)

        self.assertEqual(report["analysis_status"], "detection_quality_insufficient")
        self.assertAlmostEqual(
            report["maximum_gap_between_accepted_points_seconds"],
            0.9,
        )
        self.assertEqual(len(report["missing_intervals"]), 1)
        self.assertAlmostEqual(
            report["missing_intervals"][0]["duration_seconds"],
            0.8,
        )
        self.assertEqual(
            report["missing_intervals"][0]["rejection_reasons"],
            {"pose_not_detected": 2},
        )

    def test_missing_intervals_include_leading_and_trailing_frames(self):
        diagnostics = [
            frame(1, 0.0, False, False),
            frame(2, 0.1, True, True),
            frame(3, 0.2, True, True),
            frame(4, 0.3, True, True),
            frame(5, 0.4, True, True),
            frame(6, 0.5, False, False),
        ]

        report = assess_detection_quality(diagnostics)

        self.assertEqual(len(report["missing_intervals"]), 2)
        self.assertEqual(report["missing_intervals"][0]["start_seconds"], 0.0)
        self.assertAlmostEqual(report["missing_intervals"][0]["end_seconds"], 0.1)
        self.assertAlmostEqual(report["missing_intervals"][1]["end_seconds"], 0.6)
        self.assertTrue(report["missing_intervals"][1]["duration_estimated"])


if __name__ == "__main__":
    unittest.main()
