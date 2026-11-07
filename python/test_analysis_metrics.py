import unittest

from analysis_metrics import calculate_velocity_metrics


class CalculateVelocityMetricsTest(unittest.TestCase):
    def test_velocity_uses_elapsed_frames_when_detections_are_missing(self):
        result = calculate_velocity_metrics(
            [(1, 0.0), (4, 30.0)],
            fps=30.0,
            scale_m_per_px=0.1,
        )

        self.assertAlmostEqual(result["velocity_max"], 30.0)
        self.assertAlmostEqual(result["velocity_avg"], 30.0)
        self.assertEqual(len(result["segment_speeds"]), 1)
        self.assertEqual(result["segment_speeds"][0]["start"], 0.0)
        self.assertEqual(result["segment_speeds"][0]["end"], 10.0)
        self.assertAlmostEqual(
            result["segment_speeds"][0]["avg_velocity"], 30.0
        )

    def test_average_velocity_is_weighted_by_elapsed_time(self):
        result = calculate_velocity_metrics(
            [(1, 0.0), (2, 10.0), (4, 30.0)],
            fps=10.0,
            scale_m_per_px=0.1,
        )

        self.assertAlmostEqual(result["velocity_max"], 10.0)
        self.assertAlmostEqual(result["velocity_avg"], 10.0)

    def test_distance_segments_split_intervals_at_segment_boundaries(self):
        result = calculate_velocity_metrics(
            [(1, 0.0), (2, 25.0)],
            fps=10.0,
            scale_m_per_px=0.1,
            segment_length=1.0,
        )

        self.assertEqual(len(result["segment_speeds"]), 3)
        for index, segment in enumerate(result["segment_speeds"]):
            with self.subTest(segment=index):
                self.assertEqual(segment["start"], float(index))
                self.assertEqual(segment["end"], float(index + 1))
                self.assertAlmostEqual(segment["avg_velocity"], 25.0)

    def test_no_motion_returns_zero_velocity_and_no_segments(self):
        result = calculate_velocity_metrics(
            [(1, 12.0), (10, 12.0)],
            fps=30.0,
            scale_m_per_px=0.01,
        )

        self.assertEqual(result["velocity_max"], 0.0)
        self.assertEqual(result["velocity_avg"], 0.0)
        self.assertEqual(result["segment_speeds"], [])

    def test_stationary_intervals_contribute_to_average_velocity(self):
        result = calculate_velocity_metrics(
            [(1, 0.0), (2, 10.0), (12, 10.0), (13, 20.0)],
            fps=10.0,
            scale_m_per_px=0.1,
        )

        self.assertAlmostEqual(result["velocity_avg"], 2.0 / 1.2)
        self.assertAlmostEqual(
            result["segment_speeds"][0]["avg_velocity"], 2.0 / 1.2
        )

    def test_invalid_fps_or_scale_returns_zero_metrics(self):
        for fps, scale in [
            (0.0, 0.1),
            (float("nan"), 0.1),
            (30.0, None),
            (30.0, 0.0),
            (30.0, float("inf")),
        ]:
            with self.subTest(fps=fps, scale=scale):
                result = calculate_velocity_metrics(
                    [(1, 0.0), (2, 10.0)],
                    fps=fps,
                    scale_m_per_px=scale,
                )

                self.assertEqual(result["velocity_max"], 0.0)
                self.assertEqual(result["velocity_avg"], 0.0)
                self.assertEqual(result["segment_speeds"], [])

    def test_invalid_segment_length_returns_zero_metrics(self):
        result = calculate_velocity_metrics(
            [(1, 0.0), (2, 10.0)],
            fps=30.0,
            scale_m_per_px=0.1,
            segment_length=0.0,
        )

        self.assertEqual(result["velocity_max"], 0.0)
        self.assertEqual(result["velocity_avg"], 0.0)
        self.assertEqual(result["segment_speeds"], [])

    def test_non_finite_positions_are_rejected(self):
        with self.assertRaises(ValueError):
            calculate_velocity_metrics(
                [(1, 0.0), (2, float("nan"))],
                fps=30.0,
                scale_m_per_px=0.1,
            )


if __name__ == "__main__":
    unittest.main()
