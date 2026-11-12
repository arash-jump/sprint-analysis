from math import floor
from math import isfinite


def calculate_velocity_metrics(
    positions: list[tuple[float, float]],
    scale_m_per_px: float,
    segment_length: float = 10.0,
) -> dict:
    if (
        not isfinite(scale_m_per_px)
        or scale_m_per_px <= 0
        or not isfinite(segment_length)
        or segment_length <= 0
    ):
        raise ValueError("Scale and segment length must be finite and greater than zero.")

    if len(positions) < 2:
        raise ValueError("At least two valid pose detections are required.")

    if any(
        not isfinite(timestamp) or not isfinite(x)
        for timestamp, x in positions
    ):
        raise ValueError("Position timestamps and coordinates must be finite.")

    total_distance = 0.0
    total_time = 0.0
    max_velocity = 0.0
    segment_times: dict[int, float] = {}
    segment_distances: dict[int, float] = {}

    for (previous_time, previous_x), (current_time, current_x) in zip(
        positions, positions[1:]
    ):
        elapsed_time = current_time - previous_time
        if elapsed_time <= 0:
            raise ValueError("Position timestamps must be strictly increasing.")

        distance = abs(current_x - previous_x) * scale_m_per_px
        velocity = distance / elapsed_time
        if not all(isfinite(value) for value in (elapsed_time, distance, velocity)):
            raise ValueError("Position interval metrics must be finite.")

        traversed_distance = total_distance
        max_velocity = max(max_velocity, velocity)
        next_total_distance = total_distance + distance
        next_total_time = total_time + elapsed_time
        if not isfinite(next_total_distance) or not isfinite(next_total_time):
            raise ValueError("Total distance and duration must be finite.")
        total_distance = next_total_distance
        total_time = next_total_time

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

    segment_speeds = []
    for index in sorted(segment_distances):
        segment_distance = segment_distances[index]
        segment_time = segment_times[index]
        if segment_distance <= 0 or segment_time <= 0:
            continue

        start = index * segment_length
        segment_speeds.append({
            "start": start,
            "end": min(start + segment_length, total_distance),
            "distance_m": segment_distance,
            "duration_seconds": segment_time,
            "avg_velocity": segment_distance / segment_time,
        })

    return {
        "velocity_max": max_velocity,
        "velocity_avg": total_distance / total_time if total_time > 0 else 0.0,
        "estimated_distance_m": total_distance,
        "analysis_duration_seconds": positions[-1][0] - positions[0][0],
        "movement_detected": total_distance > 0,
        "segment_speeds": segment_speeds,
    }
