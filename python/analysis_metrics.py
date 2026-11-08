from math import floor
from math import isfinite
from typing import Optional


def calculate_velocity_metrics(
    positions: list[tuple[int, float]],
    fps: float,
    scale_m_per_px: Optional[float],
    segment_length: float = 10.0,
) -> dict:
    if (
        not isfinite(fps)
        or fps <= 0
        or scale_m_per_px is None
        or not isfinite(scale_m_per_px)
        or scale_m_per_px <= 0
        or not isfinite(segment_length)
        or segment_length <= 0
    ):
        return {
            "velocity_max": 0.0,
            "velocity_avg": 0.0,
            "segment_speeds": [],
        }

    if any(
        not isfinite(frame) or not isfinite(x)
        for frame, x in positions
    ):
        raise ValueError("Position frames and coordinates must be finite.")

    ordered_positions = sorted(positions, key=lambda position: position[0])
    total_distance = 0.0
    total_time = 0.0
    max_velocity = 0.0
    segment_times: dict[int, float] = {}
    segment_distances: dict[int, float] = {}

    for (previous_frame, previous_x), (current_frame, current_x) in zip(
        ordered_positions, ordered_positions[1:]
    ):
        elapsed_time = (current_frame - previous_frame) / fps
        distance = abs(current_x - previous_x) * scale_m_per_px
        if elapsed_time <= 0:
            continue

        velocity = distance / elapsed_time
        max_velocity = max(max_velocity, velocity)
        total_distance += distance
        total_time += elapsed_time

        traversed_distance = total_distance - distance
        if distance == 0:
            segment_index = floor(traversed_distance / segment_length)
            segment_times[segment_index] = (
                segment_times.get(segment_index, 0.0) + elapsed_time
            )
            continue

        remaining_distance = distance
        while remaining_distance > 0:
            segment_index = floor(traversed_distance / segment_length)
            segment_offset = traversed_distance - segment_index * segment_length
            distance_in_segment = min(
                remaining_distance, segment_length - segment_offset
            )
            time_in_segment = elapsed_time * distance_in_segment / distance

            segment_distances[segment_index] = (
                segment_distances.get(segment_index, 0.0) + distance_in_segment
            )
            segment_times[segment_index] = (
                segment_times.get(segment_index, 0.0) + time_in_segment
            )

            traversed_distance += distance_in_segment
            remaining_distance -= distance_in_segment

    segment_speeds = [
        {
            "start": index * segment_length,
            "end": (index + 1) * segment_length,
            "avg_velocity": segment_distances[index] / segment_times[index],
        }
        for index in sorted(segment_distances)
        if segment_times[index] > 0
    ]

    return {
        "velocity_max": max_velocity,
        "velocity_avg": total_distance / total_time if total_time > 0 else 0.0,
        "segment_speeds": segment_speeds,
    }
