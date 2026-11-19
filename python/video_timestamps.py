from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys


class VideoTimestampError(ValueError):
    pass


def parse_frame_timestamps(probe_output: str) -> list[float]:
    try:
        probe_data = json.loads(probe_output)
        frames = probe_data["frames"]
        timestamps = [
            float(frame["best_effort_timestamp_time"])
            for frame in frames
        ]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        raise VideoTimestampError(
            "The video does not contain usable frame timestamps."
        ) from None

    if not timestamps or not all(math.isfinite(timestamp) for timestamp in timestamps):
        raise VideoTimestampError(
            "The video does not contain usable frame timestamps."
        )

    if any(current <= previous for previous, current in zip(timestamps, timestamps[1:])):
        raise VideoTimestampError(
            "The video frame timestamps are not strictly increasing."
        )

    return timestamps


def read_frame_timestamps(movie_path: str, ffprobe_binary: str) -> list[float]:
    try:
        process = subprocess.run(
            [
                ffprobe_binary,
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "frame=best_effort_timestamp_time",
                "-of",
                "json",
                movie_path,
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=600,
        )
    except FileNotFoundError:
        raise VideoTimestampError(
            "FFprobe could not be started. Install FFmpeg/FFprobe and try again."
        ) from None
    except subprocess.TimeoutExpired:
        raise VideoTimestampError(
            "Reading video timestamps timed out. Try a shorter video."
        ) from None
    except subprocess.CalledProcessError as exception:
        detail = " ".join((exception.stderr or "").split())[:400]
        reason = f" FFprobe reported: {detail}" if detail else ""
        raise VideoTimestampError(
            f"Could not read timestamps from the converted video "
            f"(FFprobe exit code {exception.returncode}).{reason}"
        ) from None
    except OSError:
        raise VideoTimestampError(
            "FFprobe could not read the converted video."
        ) from None

    return parse_frame_timestamps(process.stdout)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Print relative per-frame presentation timestamps as JSON."
    )
    parser.add_argument("movie_path")
    parser.add_argument("ffprobe_binary", nargs="?", default="ffprobe")
    args = parser.parse_args(argv)

    try:
        timestamps = read_frame_timestamps(args.movie_path, args.ffprobe_binary)
    except VideoTimestampError as exception:
        print(str(exception), file=sys.stderr)
        return 1

    first_timestamp = timestamps[0]
    print(json.dumps({
        "timestamps_seconds": [
            timestamp - first_timestamp for timestamp in timestamps
        ],
    }, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
