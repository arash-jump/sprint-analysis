from __future__ import annotations

import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2

from pose_detection import RIGHT_HIP_INDEX, draw_pose_overlay
from video_timestamps import VideoTimestampError, read_frame_timestamps


MICROSECONDS_PER_SECOND = 1_000_000


def build_setpts_expression(timestamps: list[float]) -> str:
    if not timestamps or any(
        not math.isfinite(timestamp)
        or (index > 0 and timestamp <= timestamps[index - 1])
        for index, timestamp in enumerate(timestamps)
    ):
        raise ValueError("Overlay timestamps must be finite and strictly increasing.")

    relative_pts = [
        round((timestamp - timestamps[0]) * MICROSECONDS_PER_SECOND)
        for timestamp in timestamps
    ]
    if any(
        current <= previous
        for previous, current in zip(relative_pts, relative_pts[1:])
    ):
        raise ValueError("Overlay timestamps cannot be represented at microsecond precision.")
    def expression(start: int, end: int) -> str:
        if end - start == 1:
            return str(relative_pts[start])
        middle = (start + end) // 2
        return f"if(lt(N\\,{middle})\\,{expression(start, middle)}\\,{expression(middle, end)})"

    return expression(0, len(relative_pts))


def _read_landmark_records(path: Path) -> list[dict]:
    records = []
    with path.open(encoding="utf-8") as records_file:
        for line in records_file:
            record = json.loads(line)
            if not isinstance(record, dict):
                raise ValueError("Pose landmark data is invalid.")
            records.append(record)
    if not records:
        raise ValueError("No pose landmark data is available for rendering.")
    return records


def _draw_status(frame, record: dict, roi: dict | None) -> None:
    frame_height, frame_width = frame.shape[:2]
    in_interval = record["within_measurement_interval"]
    pose_detected = record["pose_detected"]
    calculation_accepted = record["calculation_accepted"]

    if roi is not None:
        x, y = roi["x"], roi["y"]
        width, height = roi["width"], roi["height"]
        cv2.rectangle(frame, (x, y), (x + width, y + height), (0, 220, 255), 2)

    interval_label = "MEASUREMENT INTERVAL" if in_interval else "OUTSIDE INTERVAL - NOT MEASURED"
    pose_label = "POSE DETECTED" if pose_detected else "POSE NOT DETECTED"
    if not in_interval:
        hip_label = "RIGHT HIP NOT USED"
    elif calculation_accepted:
        hip_label = "RIGHT HIP ACCEPTED"
    else:
        reason = record.get("rejection_reason") or "unavailable"
        hip_label = f"RIGHT HIP NOT ACCEPTED ({reason})"

    cv2.rectangle(frame, (0, 0), (frame_width, 72), (0, 0, 0), -1)
    color = (80, 230, 80) if in_interval else (180, 180, 180)
    cv2.putText(
        frame,
        f"Frame {record['frame_number']} | {record['timestamp_seconds']:.6f}s | {interval_label}",
        (8, 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        color,
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        frame,
        f"{pose_label} | {hip_label}",
        (8, 46),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        frame,
        "Visual review only - measurement accuracy is not guaranteed",
        (8, 66),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.4,
        (220, 220, 220),
        1,
        cv2.LINE_AA,
    )


def _draw_frame(frame, record: dict, roi: dict | None) -> None:
    if record.get("pose_detected"):
        raw_landmarks = record.get("landmarks")
        if not isinstance(raw_landmarks, list) or len(raw_landmarks) <= RIGHT_HIP_INDEX:
            raise ValueError("Pose landmark data is incomplete.")
        landmarks = [
            {
                "x_px": point[0],
                "y_px": point[1],
            }
            for point in raw_landmarks
        ]
        draw_pose_overlay(frame, landmarks)
    _draw_status(frame, record, roi)


def render_pose_overlay_video(
    movie_path: Path,
    records_path: Path,
    ffprobe_binary: str,
    ffmpeg_binary: str,
    output_path: Path,
) -> int:
    records = _read_landmark_records(records_path)
    source_timestamps = read_frame_timestamps(str(movie_path), ffprobe_binary)
    if len(records) > len(source_timestamps):
        raise ValueError("Pose landmark data exceeds the converted video's frames.")

    timestamps = [
        timestamp - source_timestamps[0]
        for timestamp in source_timestamps[:len(records)]
    ]
    for index, record in enumerate(records):
        if (
            record.get("frame_number") != index + 1
            or not isinstance(record.get("timestamp_seconds"), (int, float))
            or not math.isclose(
                record["timestamp_seconds"],
                timestamps[index],
                rel_tol=0,
                abs_tol=1e-6,
            )
        ):
            raise ValueError("Pose landmarks do not match the converted video timeline.")

    cap = cv2.VideoCapture(str(movie_path))
    if not cap.isOpened():
        cap.release()
        raise ValueError("The converted video could not be opened for rendering.")

    first_ret, first_frame = cap.read()
    if not first_ret:
        cap.release()
        raise ValueError("The converted video contains no decodable frames.")
    height, width = first_frame.shape[:2]

    roi = records[0].get("roi")
    filter_graph = (
        f"[0:v]settb=AVTB,setpts={build_setpts_expression(timestamps)}[overlay]"
    )
    try:
        with tempfile.TemporaryDirectory() as filter_dir:
            filter_path = Path(filter_dir) / "overlay.filter"
            filter_path.write_text(filter_graph, encoding="utf-8")
            command = [
                ffmpeg_binary,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "rawvideo",
                "-pixel_format",
                "bgr24",
                "-video_size",
                f"{width}x{height}",
                "-framerate",
                "1000",
                "-i",
                "pipe:0",
                "-/filter_complex",
                str(filter_path),
                "-map",
                "[overlay]",
                "-an",
                "-fps_mode",
                "passthrough",
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "23",
                "-pix_fmt",
                "yuv420p",
                "-bf",
                "0",
                "-enc_time_base",
                "1:1000000",
                "-video_track_timescale",
                str(MICROSECONDS_PER_SECOND),
                "-movflags",
                "+faststart",
                str(output_path),
            ]
            with tempfile.TemporaryFile() as error_file:
                try:
                    process = subprocess.Popen(
                        command,
                        stdin=subprocess.PIPE,
                        stdout=subprocess.DEVNULL,
                        stderr=error_file,
                    )
                except FileNotFoundError as exception:
                    cap.release()
                    raise RuntimeError("FFmpeg executable could not be found.") from exception
                except PermissionError as exception:
                    cap.release()
                    raise RuntimeError("FFmpeg executable permission denied.") from exception
                try:
                    frame = first_frame
                    for index, record in enumerate(records):
                        if frame.shape[:2] != (height, width):
                            raise ValueError("Video dimensions changed during rendering.")
                        _draw_frame(frame, record, roi)
                        process.stdin.write(frame.tobytes())
                        if index + 1 < len(records):
                            ret, frame = cap.read()
                            if not ret:
                                raise ValueError(
                                    "The video ended before all pose frames were rendered."
                                )
                    process.stdin.close()
                    return_code = process.wait()
                except BrokenPipeError as exception:
                    if process.poll() is None:
                        process.kill()
                    process.wait()
                    error_file.seek(0)
                    error = error_file.read().decode("utf-8", errors="replace").strip()
                    detail = f": {error[:500]}" if error else ""
                    raise RuntimeError(
                        f"FFmpeg could not create the pose review video{detail}"
                    ) from exception
                except BaseException:
                    if process.poll() is None:
                        process.kill()
                    process.wait()
                    raise
                finally:
                    cap.release()

                error_file.seek(0)
                error = error_file.read().decode("utf-8", errors="replace").strip()
                if return_code != 0:
                    raise RuntimeError(
                        f"FFmpeg could not create the pose review video: {error[:500]}"
                    )
    except OSError as exception:
        cap.release()
        raise RuntimeError("The pose review video could not be generated.") from exception

    return len(records)


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if len(argv) != 5:
        print(
            "Usage: pose_overlay_video.py VIDEO RECORDS FFPROBE FFMPEG OUTPUT",
            file=sys.stderr,
        )
        return 2
    movie_path, records_path, ffprobe_binary, ffmpeg_binary, output_path = argv
    try:
        frame_count = render_pose_overlay_video(
            Path(movie_path),
            Path(records_path),
            ffprobe_binary,
            ffmpeg_binary,
            Path(output_path),
        )
    except (OSError, RuntimeError, ValueError, VideoTimestampError) as exception:
        print(str(exception), file=sys.stderr)
        return 1
    print(json.dumps({"frame_count": frame_count}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
