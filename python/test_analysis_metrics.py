import unittest

from analysis_metrics import calculate_velocity_metrics


class CalculateVelocityMetricsTest(unittest.TestCase):
    def test_same_one_second_motion_has_same_speed_at_30_and_60_fps(self):
        results = []
        for fps in (30, 60):
            positions = [
                (frame / fps, 3 * frame / fps)
                for frame in range(fps + 1)
            ]
            results.append(calculate_velocity_metrics(positions, scale_m_per_px=1.0))

        for result in results:
            self.assertAlmostEqual(result["estimated_distance_m"], 3.0)
            self.assertAlmostEqual(result["analysis_duration_seconds"], 1.0)
            self.assertAlmostEqual(result["velocity_avg"], 3.0)

    def test_average_speed_is_total_distance_over_first_to_last_detection_time(self):
        result = calculate_velocity_metrics(
            [(0.0, 0.0), (0.25, 0.75), (1.0, 3.0)],
            scale_m_per_px=1.0,
        )

        self.assertAlmostEqual(result["estimated_distance_m"], 3.0)
        self.assertAlmostEqual(result["analysis_duration_seconds"], 1.0)
        self.assertAlmostEqual(result["velocity_avg"], 3.0)
        self.assertAlmostEqual(result["velocity_max"], 3.0)

    def test_detection_gap_uses_the_actual_timestamp_difference(self):
        result = calculate_velocity_metrics(
            [(0.0, 0.0), (0.9, 2.7)],
            scale_m_per_px=1.0,
        )

        self.assertAlmostEqual(result["analysis_duration_seconds"], 0.9)
        self.assertAlmostEqual(result["velocity_avg"], 3.0)

    def test_23_meters_has_a_three_meter_final_segment(self):
        result = calculate_velocity_metrics(
            [(0.0, 0.0), (2.3, 23.0)],
            scale_m_per_px=1.0,
        )

        self.assertEqual(
            [(segment["start"], segment["end"]) for segment in result["segment_speeds"]],
            [(0.0, 10.0), (10.0, 20.0), (20.0, 23.0)],
        )
        self.assertAlmostEqual(result["segment_speeds"][-1]["distance_m"], 3.0)
        self.assertAlmostEqual(result["segment_speeds"][-1]["duration_seconds"], 0.3)
        self.assertAlmostEqual(result["segment_speeds"][-1]["avg_velocity"], 10.0)

    def test_exact_segment_boundary_does_not_create_an_empty_segment(self):
        result = calculate_velocity_metrics(
            [(0.0, 0.0), (2.0, 20.0)],
            scale_m_per_px=1.0,
        )

        self.assertEqual(
            [(segment["start"], segment["end"]) for segment in result["segment_speeds"]],
            [(0.0, 10.0), (10.0, 20.0)],
        )

    def test_exact_boundary_with_floating_point_input_does_not_create_a_tiny_segment(self):
        result = calculate_velocity_metrics(
            [(0.0, 0.0), (2.0, 0.1 + 0.2 + 19.7)],
            scale_m_per_px=1.0,
        )

        self.assertEqual(len(result["segment_speeds"]), 2)
        self.assertAlmostEqual(result["estimated_distance_m"], 20.0)

    def test_interval_crossing_boundaries_preserves_distance_and_time(self):
        result = calculate_velocity_metrics(
            [(0.0, 0.0), (5.0, 25.0)],
            scale_m_per_px=1.0,
        )
        segments = result["segment_speeds"]

        self.assertAlmostEqual(sum(segment["distance_m"] for segment in segments), 25.0)
        self.assertAlmostEqual(sum(segment["duration_seconds"] for segment in segments), 5.0)
        self.assertTrue(all(abs(segment["avg_velocity"] - 5.0) < 1e-9 for segment in segments))

    def test_stationary_detections_are_distinct_from_insufficient_detections(self):
        with self.assertRaisesRegex(ValueError, "At least two"):
            calculate_velocity_metrics([(0.0, 12.0)], scale_m_per_px=0.01)

        result = calculate_velocity_metrics(
            [(0.0, 12.0), (1.0, 12.0)],
            scale_m_per_px=0.01,
        )

        self.assertFalse(result["movement_detected"])
        self.assertEqual(result["estimated_distance_m"], 0.0)
        self.assertEqual(result["velocity_avg"], 0.0)
        self.assertEqual(result["velocity_max"], 0.0)
        self.assertEqual(result["segment_speeds"], [])

    def test_invalid_or_non_increasing_timestamps_are_rejected(self):
        invalid_positions = [
            [(0.0, 0.0), (0.0, 1.0)],
            [(1.0, 0.0), (0.5, 1.0)],
            [(0.0, 0.0), (float("nan"), 1.0)],
            [(0.0, 0.0), (float("inf"), 1.0)],
        ]
        for positions in invalid_positions:
            with self.subTest(positions=positions):
                with self.assertRaises(ValueError):
                    calculate_velocity_metrics(positions, scale_m_per_px=1.0)

    def test_overflowing_interval_metrics_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "must be finite"):
            calculate_velocity_metrics(
                [(0.0, -1e308), (1.0, 1e308)],
                scale_m_per_px=1.0,
            )

    def test_invalid_scale_or_segment_length_is_rejected(self):
        for scale, segment_length in [
            (0.0, 10.0),
            (float("nan"), 10.0),
            (float("inf"), 10.0),
            (1.0, 0.0),
            (1.0, float("nan")),
        ]:
            with self.subTest(scale=scale, segment_length=segment_length):
                with self.assertRaises(ValueError):
                    calculate_velocity_metrics(
                        [(0.0, 0.0), (1.0, 1.0)],
                        scale_m_per_px=scale,
                        segment_length=segment_length,
                    )


if __name__ == "__main__":
    unittest.main()
