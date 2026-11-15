from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import cv2

from analysis_quality import (
    QUALITY_THRESHOLDS,
    assess_detection_quality,
    assess_right_hip,
)
from pose_detection import (
    POSE_MODEL_SETTINGS,
    analyze_pose_frame,
    create_pose,
    draw_pose_overlay,
    validate_roi,
)
from video_timestamps import VideoTimestampError, read_frame_timestamps


MAX_DIAGNOSTIC_IMAGES = 20
MAX_DETECTION_REPRESENTATIVES = 4
MAX_UNDETECTED_REPRESENTATIVES = 4
PROJECT_ROOT = Path(__file__).resolve().parents[1]
PRIVATE_DIAGNOSTIC_ROOT = (
    PROJECT_ROOT / "storage" / "app" / "private" / "pose-diagnostics"
).resolve()


def parse_roi(value: str) -> tuple[int, int, int, int]:
    try:
        parts = tuple(int(part) for part in value.split(","))
    except ValueError as exception:
        raise argparse.ArgumentTypeError(
            "ROI must be four comma-separated integers: x,y,width,height."
        ) from exception
    if len(parts) != 4:
        raise argparse.ArgumentTypeError(
            "ROI must be four comma-separated integers: x,y,width,height."
        )
    return parts


def validate_output_directory(output_dir: Path) -> Path:
    resolved = output_dir.expanduser().resolve()
    if "public" in resolved.parts:
        raise ValueError("Diagnostic images must not be written under a public directory.")

    try:
        resolved.relative_to(PROJECT_ROOT)
    except ValueError:
        return resolved

    try:
        resolved.relative_to(PRIVATE_DIAGNOSTIC_ROOT)
    except ValueError as exception:
        raise ValueError(
            "Output inside the repository is allowed only under "
            "storage/app/private/pose-diagnostics."
        ) from exception
    return resolved


def select_diagnostic_frames(
    frame_diagnostics: list[dict],
    neighbor_frames: list[dict] | None = None,
) -> dict[int, set[str]]:
    selected: dict[int, set[str]] = {}
    if not frame_diagnostics:
        return selected

    target_frames = [
        frame
        for frame in frame_diagnostics
        if frame["calculation_accepted"]
    ]
    if not target_frames:
        target_frames = [
            frame for frame in frame_diagnostics if frame["pose_detected"]
        ]
    representative_frames = _evenly_spaced(
        target_frames, MAX_DETECTION_REPRESENTATIVES
    )

    frame_by_number = {
        frame["frame_number"]: frame
        for frame in (neighbor_frames or frame_diagnostics)
    }
    for frame in representative_frames:
        number = frame["frame_number"]
        selected.setdefault(number, set()).add("detected_representative")
        for neighbor, label in (
            (number - 1, "before_detected_representative"),
            (number + 1, "after_detected_representative"),
        ):
            if neighbor in frame_by_number:
                selected.setdefault(neighbor, set()).add(label)

    for frame in _undetected_representatives(frame_diagnostics):
        selected.setdefault(frame["frame_number"], set()).add(
            "undetected_representative"
        )

    return dict(list(selected.items())[:MAX_DIAGNOSTIC_IMAGES])


def _evenly_spaced(frames: list[dict], maximum: int) -> list[dict]:
    if len(frames) <= maximum:
        return frames
    if maximum == 1:
        return [frames[len(frames) // 2]]
    indexes = {
        round(index * (len(frames) - 1) / (maximum - 1))
        for index in range(maximum)
    }
    return [frames[index] for index in sorted(indexes)]


def _undetected_representatives(frame_diagnostics: list[dict]) -> list[dict]:
    runs = []
    index = 0
    while index < len(frame_diagnostics):
        if frame_diagnostics[index]["pose_detected"]:
            index += 1
            continue
        start = index
        while (
            index + 1 < len(frame_diagnostics)
            and not frame_diagnostics[index + 1]["pose_detected"]
        ):
            index += 1
        runs.append((index - start + 1, frame_diagnostics[(start + index) // 2]))
        index += 1

    runs.sort(key=lambda run: run[0], reverse=True)
    return [
        frame
        for _, frame in runs[:MAX_UNDETECTED_REPRESENTATIVES]
    ]


def _frame_diagnostic(frame_number: int, timestamp: float, pose_frame: dict) -> dict:
    right_hip = pose_frame["right_hip"]
    accepted, rejection_reason = assess_right_hip(right_hip)
    if not pose_frame["pose_detected"]:
        rejection_reason = "pose_not_detected"

    return {
        "frame_number": frame_number,
        "timestamp_seconds": timestamp,
        "pose_detected": pose_frame["pose_detected"],
        "landmark_x_px": right_hip["x_px"] if right_hip else None,
        "landmark_y_px": right_hip["y_px"] if right_hip else None,
        "landmark_visibility": (
            right_hip["visibility"]
            if right_hip
            and isinstance(right_hip["visibility"], (int, float))
            and math.isfinite(right_hip["visibility"])
            else None
        ),
        "calculation_accepted": accepted,
        "rejection_reason": rejection_reason,
    }


def _draw_label(frame, frame_number: int, timestamp: float, pose_frame: dict):
    if pose_frame["pose_detected"]:
        frame = draw_pose_overlay(frame, pose_frame["landmarks"])

    right_hip = pose_frame["right_hip"]
    visibility = (
        f"{right_hip['visibility']:.3f}"
        if right_hip
        and isinstance(right_hip["visibility"], (int, float))
        and math.isfinite(right_hip["visibility"])
        else "n/a"
    )
    label = (
        f"frame {frame_number} | t={timestamp:.3f}s | "
        f"pose={'yes' if pose_frame['pose_detected'] else 'no'} | "
        f"right hip visibility={visibility}"
    )
    cv2.rectangle(frame, (0, 0), (frame.shape[1], 32), (0, 0, 0), -1)
    cv2.putText(
        frame,
        label,
        (8, 23),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )
    return frame


def _prepare_output_directory(output_dir: Path) -> Path:
    output_dir = validate_output_directory(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise ValueError("Output directory must be empty to avoid overwriting files.")
    return output_dir


def diagnose_video(
    video_path: Path,
    output_dir: Path,
    ffprobe_binary: str = "ffprobe",
    start_seconds: float | None = None,
    end_seconds: float | None = None,
    roi: tuple[int, int, int, int] | None = None,
) -> dict:
    if not video_path.is_file():
        raise ValueError("Input video file does not exist.")
    if start_seconds is not None and (
        not math.isfinite(start_seconds) or start_seconds < 0
    ):
        raise ValueError("Start time must be finite and at least zero.")
    if end_seconds is not None and (
        not math.isfinite(end_seconds) or end_seconds < 0
    ):
        raise ValueError("End time must be finite and at least zero.")
    if (
        start_seconds is not None
        and end_seconds is not None
        and end_seconds <= start_seconds
    ):
        raise ValueError("End time must be later than start time.")

    output_dir = _prepare_output_directory(output_dir)
    timestamps = read_frame_timestamps(str(video_path), ffprobe_binary)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        cap.release()
        raise ValueError("The video could not be opened.")

    pose = create_pose()
    frame_diagnostics = []
    all_frame_diagnostics = []
    total_frames = 0
    video_width = None
    video_height = None
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if total_frames >= len(timestamps):
                raise ValueError(
                    "Decoded video frames do not match the available frame timestamps."
                )

            frame_height, frame_width = frame.shape[:2]
            if video_width is None:
                video_width = frame_width
                video_height = frame_height
            if roi is not None and total_frames == 0:
                validate_roi(roi, frame_width, frame_height)
            timestamp = timestamps[total_frames] - timestamps[0]
            total_frames += 1
            pose_frame = analyze_pose_frame(pose, frame, roi)
            diagnostic = _frame_diagnostic(total_frames, timestamp, pose_frame)
            all_frame_diagnostics.append(diagnostic)
            if (
                (start_seconds is None or timestamp >= start_seconds)
                and (end_seconds is None or timestamp <= end_seconds)
            ):
                frame_diagnostics.append(diagnostic)
    finally:
        cap.release()
        pose.close()

    if total_frames != len(timestamps):
        raise ValueError(
            "Decoded video frames do not match the available frame timestamps."
        )
    if not frame_diagnostics:
        raise ValueError("The selected time window does not include any video frames.")

    quality = assess_detection_quality(frame_diagnostics)
    selected = select_diagnostic_frames(
        frame_diagnostics,
        neighbor_frames=all_frame_diagnostics,
    )
    if len(selected) > MAX_DIAGNOSTIC_IMAGES:
        raise RuntimeError("The diagnostic image limit was exceeded.")

    images = _render_selected_frames(
        video_path,
        timestamps,
        selected,
        output_dir,
        roi,
    )
    report = {
        **quality,
        "video_path": str(video_path.resolve()),
        "diagnostic_tool_version": 1,
        "ffprobe_binary": ffprobe_binary,
        "total_video_frame_count": total_frames,
        "video_frame_size": {
            "width": video_width,
            "height": video_height,
        },
        "selected_time_window_seconds": {
            "start": start_seconds,
            "end": end_seconds,
        },
        "roi": (
            {"x": roi[0], "y": roi[1], "width": roi[2], "height": roi[3]}
            if roi is not None
            else None
        ),
        "model_settings": POSE_MODEL_SETTINGS,
        "quality_thresholds": QUALITY_THRESHOLDS,
        "maximum_diagnostic_images": MAX_DIAGNOSTIC_IMAGES,
        "diagnostic_images": images,
        "frame_diagnostics": frame_diagnostics,
    }
    (output_dir / "diagnostics.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return report


def _render_selected_frames(
    video_path: Path,
    timestamps: list[float],
    selected: dict[int, set[str]],
    output_dir: Path,
    roi: tuple[int, int, int, int] | None,
) -> list[dict]:
    if not selected:
        return []

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        cap.release()
        raise ValueError("The video could not be reopened for diagnostic images.")
    pose = create_pose()
    images = []
    try:
        for index in range(len(timestamps)):
            ret, frame = cap.read()
            if not ret:
                raise ValueError(
                    "The video ended while creating diagnostic images."
                )
            frame_number = index + 1
            pose_frame = analyze_pose_frame(pose, frame, roi)
            if frame_number not in selected:
                continue

            timestamp = timestamps[index] - timestamps[0]
            annotated = _draw_label(frame, frame_number, timestamp, pose_frame)
            category = "+".join(sorted(selected[frame_number]))
            filename = (
                f"frame-{frame_number:06d}-t{timestamp:.3f}-"
                f"{'detected' if pose_frame['pose_detected'] else 'not-detected'}.png"
            )
            if not cv2.imwrite(str(output_dir / filename), annotated):
                raise RuntimeError(f"Could not write diagnostic image: {filename}")
            images.append({
                "file": filename,
                "frame_number": frame_number,
                "timestamp_seconds": timestamp,
                "pose_detected": pose_frame["pose_detected"],
                "right_hip_visibility": (
                    pose_frame["right_hip"]["visibility"]
                    if pose_frame["right_hip"]
                    and isinstance(
                        pose_frame["right_hip"]["visibility"], (int, float)
                    )
                    and math.isfinite(
                        pose_frame["right_hip"]["visibility"]
                    )
                    else None
                ),
                "right_hip_accepted": (
                    assess_right_hip(pose_frame["right_hip"])[0]
                    if pose_frame["pose_detected"]
                    else False
                ),
                "category": category,
            })
    finally:
        cap.release()
        pose.close()

    if len(images) > MAX_DIAGNOSTIC_IMAGES:
        raise RuntimeError("The diagnostic image limit was exceeded.")
    return images


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create local pose-detection diagnostics without modifying the video."
    )
    parser.add_argument("video", type=Path, help="Input video file")
    parser.add_argument("output_dir", type=Path, help="Empty local diagnostics directory")
    parser.add_argument("--ffprobe-binary", default="ffprobe")
    parser.add_argument("--start-seconds", type=float)
    parser.add_argument("--end-seconds", type=float)
    parser.add_argument(
        "--roi",
        type=parse_roi,
        help="Optional fixed ROI in source-frame pixels: x,y,width,height",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        report = diagnose_video(
            args.video,
            args.output_dir,
            ffprobe_binary=args.ffprobe_binary,
            start_seconds=args.start_seconds,
            end_seconds=args.end_seconds,
            roi=args.roi,
        )
    except (OSError, RuntimeError, ValueError, VideoTimestampError) as exception:
        print(json.dumps({
            "analysis_status": "processing_error",
            "error": str(exception),
        }), file=sys.stderr)
        return 1

    print(json.dumps({
        "analysis_status": report["analysis_status"],
        "diagnostics_json": str(
            (args.output_dir.expanduser().resolve() / "diagnostics.json")
        ),
        "diagnostic_image_count": len(report["diagnostic_images"]),
        "maximum_diagnostic_images": MAX_DIAGNOSTIC_IMAGES,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
