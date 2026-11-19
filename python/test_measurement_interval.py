import math
import unittest

from measurement_interval import MeasurementFrameRange


class MeasurementFrameRangeTest(unittest.TestCase):
    def test_range_includes_both_boundary_frames(self):
        frame_range = MeasurementFrameRange(3, 5, 8)

        self.assertEqual(frame_range.frame_count, 3)
        self.assertFalse(frame_range.includes(2))
        self.assertTrue(frame_range.includes(3))
        self.assertTrue(frame_range.includes(5))
        self.assertFalse(frame_range.includes(6))

    def test_rejects_reversed_out_of_bounds_and_non_integer_ranges(self):
        invalid_ranges = [
            (0, 2, 8),
            (4, 3, 8),
            (3, 9, 8),
            (1, 1, 0),
            (True, 2, 8),
            (1.0, 2, 8),
            (math.nan, 2, 8),
            (1, math.inf, 8),
        ]

        for values in invalid_ranges:
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    MeasurementFrameRange(*values)
