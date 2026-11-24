"""Experimental background alignment diagnostic; never changes production metrics.

H_prev_to_curr maps previous-frame pixels to current-frame pixels. The stored
H_curr_to_ref is H_prev_to_ref @ inverse(H_prev_to_curr); all points are in
original decoded-frame pixels. A failed link invalidates the remaining chain.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import cv2
import numpy as np

from analysis_quality import assess_right_hip
from diagnose_pose import parse_roi
from pose_detection import analyze_pose_frame, create_pose, draw_pose_overlay, validate_roi
from video_timestamps import read_frame_timestamps

PRIVATE_ROOT = (Path(__file__).resolve().parents[1] / 'storage/app/private').resolve()
# Provisional diagnostics, not accuracy guarantees.
THRESHOLDS = {
    'max_features': 600, 'min_correspondences': 16, 'min_inliers': 12,
    'min_inlier_ratio': 0.65, 'ransac_px': 3.0, 'max_median_error_px': 2.0,
    'min_spread_fraction': 0.015, 'min_holdout': 4,
    'max_holdout_median_error_px': 5.0, 'min_reference_overlap': 0.15,
    'max_chain_frames': 300, 'max_condition': 1e9, 'pose_margin_px': 30,
    'max_output_images': 12,
}


def project(matrix, points):
    points = np.asarray(points, dtype=np.float64).reshape(-1, 2)
    homogeneous = np.column_stack([points, np.ones(len(points))]) @ matrix.T
    if not np.isfinite(homogeneous).all() or np.any(np.abs(homogeneous[:, 2]) < 1e-8):
        raise ValueError('invalid_projective_coordinates')
    out = homogeneous[:, :2] / homogeneous[:, 2, None]
    if not np.isfinite(out).all():
        raise ValueError('invalid_projective_coordinates')
    return out


def spread(points, width, height):
    if len(points) < 3:
        return 0.0
    return float(cv2.contourArea(cv2.convexHull(np.asarray(points, np.float32)))) / (width * height)


def estimate_link(previous, current, width, height):
    """Estimate previous -> current using training points; every fifth is held out."""
    previous = np.asarray(previous, dtype=np.float32).reshape(-1, 2)
    current = np.asarray(current, dtype=np.float32).reshape(-1, 2)
    result = {'correspondences': len(previous), 'inliers': 0, 'inlier_ratio': None,
              'median_reprojection_error_px': None, 'holdout_count': 0,
              'holdout_median_error_px': None, 'valid': False, 'reason': None,
              'training_spread_fraction': None, 'inlier_spread_fraction': None,
              'training_count': 0}
    mask = np.zeros(len(previous), dtype=bool)
    held = np.arange(len(previous)) % 5 == 0
    result['holdout_count'] = int(held.sum())
    result['training_count'] = int((~held).sum())
    def fail(reason):
        result['reason'] = reason
        return None, result, mask, held
    if len(previous) != len(current) or len(previous) < THRESHOLDS['min_correspondences']:
        return fail('insufficient_correspondences')
    if held.sum() < THRESHOLDS['min_holdout']:
        return fail('insufficient_holdout')
    if not np.isfinite(previous).all() or not np.isfinite(current).all():
        return fail('non_finite_points')
    result['training_spread_fraction'] = min(spread(previous[~held], width, height), spread(current[~held], width, height))
    if result['training_spread_fraction'] < THRESHOLDS['min_spread_fraction']:
        return fail('points_poorly_distributed')
    matrix, inliers = cv2.findHomography(previous[~held], current[~held], cv2.RANSAC, THRESHOLDS['ransac_px'])
    if matrix is None or inliers is None or not np.isfinite(matrix).all():
        return fail('homography_unavailable')
    if abs(matrix[2, 2]) < 1e-10:
        return fail('invalid_homography')
    matrix = matrix / matrix[2, 2]
    if np.linalg.cond(matrix) > THRESHOLDS['max_condition']:
        return fail('invalid_homography')
    mask[~held] = inliers.ravel().astype(bool)
    result['inliers'] = int(mask.sum())
    result['inlier_ratio'] = float(mask.sum() / (~held).sum())
    result['inlier_spread_fraction'] = min(spread(previous[mask], width, height), spread(current[mask], width, height))
    try:
        errors = np.linalg.norm(project(matrix, previous) - current, axis=1)
        if mask.any():
            result['median_reprojection_error_px'] = float(np.median(errors[mask]))
        result['holdout_median_error_px'] = float(np.median(errors[held]))
    except ValueError:
        return fail('invalid_homography')
    if result['inliers'] < THRESHOLDS['min_inliers'] or result['inlier_ratio'] < THRESHOLDS['min_inlier_ratio']:
        return fail('insufficient_inliers')
    if result['inlier_spread_fraction'] < THRESHOLDS['min_spread_fraction']:
        return fail('inliers_poorly_distributed')
    if result['median_reprojection_error_px'] > THRESHOLDS['max_median_error_px']:
        return fail('high_reprojection_error')
    if result['holdout_median_error_px'] > THRESHOLDS['max_holdout_median_error_px']:
        return fail('high_holdout_error')
    result.update(valid=True, reason='ok')
    return matrix, result, mask, held


def compose_to_reference(previous_to_reference, previous_to_current, width, height, link_count):
    if link_count > THRESHOLDS['max_chain_frames']:
        return None, 0.0, 'chain_limit_exceeded'
    try:
        matrix = previous_to_reference @ np.linalg.inv(previous_to_current)
        if not np.isfinite(matrix).all() or abs(matrix[2, 2]) < 1e-10:
            raise ValueError()
        matrix /= matrix[2, 2]
        if np.linalg.cond(matrix) > THRESHOLDS['max_condition']:
            raise ValueError()
        corners = project(matrix, [[0, 0], [width, 0], [width, height], [0, height]]).astype(np.float32)
        polygon = corners.reshape(-1, 1, 2)
        if not cv2.isContourConvex(polygon):
            raise ValueError()
        ref = np.array([[0, 0], [width, 0], [width, height], [0, height]], np.float32)
        overlap, _ = cv2.intersectConvexConvex(corners, ref)
        overlap = float(overlap / (width * height))
    except (ValueError, np.linalg.LinAlgError, cv2.error):
        return None, 0.0, 'invalid_composed_transform'
    if overlap < THRESHOLDS['min_reference_overlap']:
        return None, overlap, 'insufficient_reference_overlap'
    return matrix, overlap, 'ok'


def pose_box(pose, width, height):
    points = [(p['x_px'], p['y_px']) for p in pose['landmarks']
              if p['x_px'] is not None and p['y_px'] is not None
              and math.isfinite(p['x_px']) and math.isfinite(p['y_px'])]
    if len(points) < 10:
        return None
    margin = THRESHOLDS['pose_margin_px']
    xs, ys = zip(*points)
    x1, y1 = max(0, math.floor(min(xs))-margin), max(0, math.floor(min(ys))-margin)
    x2, y2 = min(width, math.ceil(max(xs))+margin), min(height, math.ceil(max(ys))+margin)
    return (x1, y1, x2-x1, y2-y1) if x2 > x1 and y2 > y1 else None


def background_mask(width, height, boxes):
    mask = np.full((height, width), 255, np.uint8)
    for x, y, w, h in boxes:
        mask[y:y+h, x:x+w] = 0
    return mask


def direct_correspondences(source_gray, target_gray, source_mask, target_mask):
    """Track a retained anchor directly to a later frame using the same LK settings."""
    h, w = source_gray.shape
    features = cv2.goodFeaturesToTrack(source_gray, maxCorners=THRESHOLDS['max_features'],
                                       qualityLevel=.01, minDistance=8, mask=source_mask)
    empty = np.empty((0, 2), np.float32)
    if features is None:
        return empty, empty
    tracked, status, _ = cv2.calcOpticalFlowPyrLK(source_gray, target_gray, features, None)
    if tracked is None or status is None:
        return empty, empty
    old, new = features.reshape(-1, 2), tracked.reshape(-1, 2)
    keep = status.ravel().astype(bool) & np.isfinite(new).all(axis=1)
    indices = np.flatnonzero(keep)
    inside = (new[indices, 0] >= 0) & (new[indices, 0] < w) & (new[indices, 1] >= 0) & (new[indices, 1] < h)
    indices = indices[inside]
    indices = indices[target_mask[new[indices, 1].astype(int), new[indices, 0].astype(int)] != 0]
    return old[indices], new[indices]


def draw_trajectory(image, points, color):
    for a, b in zip(points, points[1:]):
        if a is not None and b is not None:
            if max(abs(v) for v in (*a, *b)) < 100000:
                cv2.line(image, tuple(np.rint(a).astype(int)), tuple(np.rint(b).astype(int)), color, 2)


def save_diagnostic(path, frame, reference, pose, boxes, points, accepted, held, transform, raw_path, aligned_path, previous_points, previous_to_reference):
    height, width = frame.shape[:2]
    left = frame.copy()
    if pose['pose_detected']:
        draw_pose_overlay(left, pose['landmarks'])
    for x, y, w, h in boxes:
        cv2.rectangle(left, (x, y), (x+w, y+h), (0, 0, 255), 2)
    for i, point in enumerate(points):
        color = (255, 255, 0) if held[i] else ((0, 255, 0) if accepted[i] else (0, 0, 255))
        cv2.circle(left, tuple(np.rint(point).astype(int)), 3, color, -1)
    draw_trajectory(left, raw_path, (0, 255, 255))
    if transform is None:
        right = reference.copy()
        cv2.putText(right, 'INVALID ALIGNMENT', (10, 65), cv2.FONT_HERSHEY_SIMPLEX, .7, (0, 0, 255), 2)
    else:
        aligned = cv2.warpPerspective(frame, transform, (width, height))
        right = cv2.addWeighted(reference, .5, aligned, .5, 0)
        draw_trajectory(right, aligned_path, (255, 0, 255))
        if previous_to_reference is not None and np.any(held):
            try:
                current_checks = project(transform, points[held])
                previous_checks = project(previous_to_reference, previous_points[held])
                for a, b in zip(current_checks, previous_checks):
                    if max(abs(v) for v in (*a, *b)) < 100000:
                        a, b = tuple(np.rint(a).astype(int)), tuple(np.rint(b).astype(int))
                        cv2.line(right, a, b, (0, 255, 255), 1)
                        cv2.circle(right, a, 3, (255, 255, 0), -1)
                        cv2.circle(right, b, 2, (0, 255, 255), -1)
            except ValueError:
                pass
    cv2.putText(left, 'GREEN inlier | RED rejected/mask | CYAN holdout | YELLOW raw hip', (8, 22), cv2.FONT_HERSHEY_SIMPLEX, .45, (255,255,255), 1)
    cv2.putText(right, 'Reference + aligned frame | MAGENTA aligned hip', (8, 22), cv2.FONT_HERSHEY_SIMPLEX, .45, (255,255,255), 1)
    if not cv2.imwrite(str(path), np.hstack([left, right])):
        raise OSError('Could not write diagnostic image')


def run(video, output, ffprobe, roi, exclusions, max_frames, image_every, ranged_exclusions=None, image_frames=None, reconnect_anchor=None, reconnect_candidates=None, segment_start=None):
    ranged_exclusions = ranged_exclusions or []
    image_frames = set(image_frames or [])
    reconnect_candidates = set(reconnect_candidates or [])
    output = output.expanduser().resolve()
    try:
        output.relative_to(PRIVATE_ROOT)
    except ValueError as e:
        raise ValueError('Output must be under storage/app/private') from e
    if output == PRIVATE_ROOT or output.exists():
        raise ValueError('Output directory must be a new directory under storage/app/private')
    video = video.expanduser().resolve()
    if not video.is_file():
        raise ValueError('Input video not found')
    timestamps = read_frame_timestamps(str(video), ffprobe)
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        cap.release()
        raise ValueError('Input video cannot be decoded')
    pose = None
    try:
        pose = create_pose()
        output.mkdir(mode=0o700, parents=True, exist_ok=False)
        diagnostics = []
        previous_gray = previous_mask = previous_to_ref = reference = None
        raw_path, aligned_path = [], []
        chain_broken = False
        previous_exclusion_available = False
        anchor = None
        segment_to_reference = None
        segment_broken = False
        for index in range(min(max_frames, len(timestamps))):
            ok, frame = cap.read()
            if not ok:
                raise ValueError('Video ended before requested timestamped frame')
            h, w = frame.shape[:2]
            if reference is not None and reference.shape != frame.shape:
                raise ValueError('Video dimensions changed')
            if roi is not None:
                validate_roi(roi, w, h)
            manual_boxes = exclusions + [box for start, end, box in ranged_exclusions if start <= index + 1 <= end]
            for box in manual_boxes:
                validate_roi(box, w, h)
            detected = analyze_pose_frame(pose, frame, roi)
            box = pose_box(detected, w, h)
            boxes = manual_boxes + ([box] if box else [])
            mask = background_mask(w, h, boxes)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            points = np.empty((0, 2), np.float32)
            old = np.empty((0, 2), np.float32)
            accepted = held = np.zeros(0, dtype=bool)
            info = {'correspondences': 0, 'inliers': 0, 'inlier_ratio': None,
                    'median_reprojection_error_px': None, 'holdout_count': 0,
                    'holdout_median_error_px': None, 'valid': False, 'reason': None,
                    'training_spread_fraction': None, 'inlier_spread_fraction': None}
            transform = None
            overlap = None
            link = None
            reference_failure_reason = None
            reconnect = None
            reconnected = False
            display_previous_to_ref = previous_to_ref
            if index == 0:
                reference = frame.copy()
                if boxes:
                    transform = np.eye(3)
                    overlap = 1.0
                    info.update(valid=True, reason='reference_frame')
                else:
                    info['reason'] = 'runner_exclusion_unavailable'
                    chain_broken = True
            elif not boxes or not previous_exclusion_available:
                info['reason'] = 'runner_exclusion_unavailable'
            else:
                features = cv2.goodFeaturesToTrack(previous_gray, maxCorners=THRESHOLDS['max_features'], qualityLevel=.01, minDistance=8, mask=previous_mask)
                if features is not None:
                    tracked, status, _ = cv2.calcOpticalFlowPyrLK(previous_gray, gray, features, None)
                    if tracked is not None and status is not None:
                        old, new = features.reshape(-1,2), tracked.reshape(-1,2)
                        keep = status.ravel().astype(bool) & np.isfinite(new).all(axis=1)
                        indices = np.flatnonzero(keep)
                        inside = (new[indices,0] >= 0) & (new[indices,0] < w) & (new[indices,1] >= 0) & (new[indices,1] < h)
                        indices = indices[inside]
                        excluded_indices = indices[mask[new[indices,1].astype(int), new[indices,0].astype(int)] == 0]
                        indices = indices[mask[new[indices,1].astype(int), new[indices,0].astype(int)] != 0]
                        old, points = old[indices], new[indices]
                        link, info, accepted, held = estimate_link(old, points, w, h)
                        if len(excluded_indices):
                            points = np.vstack([points, new[excluded_indices]])
                            old = np.vstack([old, features.reshape(-1, 2)[excluded_indices]])
                            accepted = np.concatenate([accepted, np.zeros(len(excluded_indices), dtype=bool)])
                            held = np.concatenate([held, np.zeros(len(excluded_indices), dtype=bool)])
                        if link is not None and not chain_broken:
                            transform, overlap, reason = compose_to_reference(previous_to_ref, link, w, h, index)
                            if transform is None:
                                reference_failure_reason = reason
            if index > 0:
                if info['reason'] is None:
                    info['reason'] = 'insufficient_correspondences'
                local_valid, local_reason = info['valid'], info['reason']
                if chain_broken and index + 1 in reconnect_candidates:
                    reconnect = {'anchor_frame': reconnect_anchor, 'target_frame': index + 1,
                                 'method': 'direct_lucas_kanade', 'valid': False}
                    if anchor is None or not boxes:
                        reconnect['reason'] = 'anchor_or_runner_exclusion_unavailable'
                    else:
                        anchor_gray, anchor_mask, anchor_to_reference = anchor
                        direct_old, direct_points = direct_correspondences(anchor_gray, gray, anchor_mask, mask)
                        direct_link, direct_info, direct_accepted, direct_held = estimate_link(direct_old, direct_points, w, h)
                        reconnect.update(direct_info)
                        reconnect['local_valid'] = direct_info['valid']
                        reconnect['local_reason'] = direct_info['reason']
                        if direct_link is not None:
                            transform, overlap, reason = compose_to_reference(anchor_to_reference, direct_link, w, h, index)
                            reconnect['reference_reason'] = reason
                            reconnect['reference_overlap'] = overlap
                            if transform is not None:
                                reconnected = True
                                chain_broken = False
                                old, points, accepted, held = direct_old, direct_points, direct_accepted, direct_held
                                display_previous_to_ref = anchor_to_reference
                            else:
                                reconnect['reason'] = reason
                                reconnect['valid'] = False
                if reconnected:
                    reference_reason = 'reconnected'
                elif chain_broken:
                    reference_reason = 'previous_transform_invalid'
                elif not local_valid:
                    reference_reason = 'local_transform_invalid'
                elif transform is None:
                    reference_reason = reference_failure_reason or 'reference_transform_unavailable'
                else:
                    reference_reason = 'ok'
                if transform is None:
                    chain_broken = True
                info['valid'] = transform is not None
                info['reason'] = reference_reason
            else:
                local_valid, local_reason = None, 'reference_frame'
            segment_reason = None
            if index + 1 == segment_start:
                if boxes:
                    segment_to_reference = np.eye(3)
                    segment_reason = 'segment_origin'
                else:
                    segment_broken = True
                    segment_reason = 'runner_exclusion_unavailable'
            elif segment_start is not None and index + 1 > segment_start:
                if segment_broken:
                    segment_reason = 'previous_segment_transform_invalid'
                elif link is None:
                    segment_to_reference = None
                    segment_broken = True
                    segment_reason = 'local_transform_invalid'
                else:
                    segment_to_reference, _, segment_reason = compose_to_reference(segment_to_reference, link, w, h, index + 1 - segment_start)
                    if segment_to_reference is None:
                        segment_broken = True
            hip = detected['right_hip']
            is_accepted, _ = assess_right_hip(hip)
            raw = [float(hip['x_px']), float(hip['y_px'])] if is_accepted else None
            aligned = None
            if raw is not None and transform is not None:
                try:
                    aligned = project(transform, [raw])[0].tolist()
                except ValueError:
                    pass
            raw_path.append(raw)
            aligned_path.append(aligned)
            info.update(frame_number=index+1, timestamp_seconds=float(timestamps[index]-timestamps[0]),
                        local_valid=local_valid, local_reason=local_reason,
                        reference_valid=transform is not None, reference_reason=info['reason'],
                        manual_exclusion_boxes=manual_boxes,
                        direct_reconnection=reconnect,
                        segment_origin_frame=segment_start if segment_reason else None,
                        segment_reason=segment_reason,
                        current_to_segment=segment_to_reference.tolist() if segment_reason and segment_to_reference is not None else None,
                        reference_overlap=overlap, raw_hip_px=raw, aligned_hip_px=aligned,
                        current_to_reference=transform.tolist() if transform is not None else None,
                        pose_detected=detected['pose_detected'], automatic_runner_box=box)
            diagnostics.append(info)
            if index + 1 == reconnect_anchor and transform is not None:
                anchor = (gray.copy(), mask.copy(), transform.copy())
            if ((image_frames and index + 1 in image_frames) or
                (not image_frames and index % image_every == 0 and index // image_every < THRESHOLDS['max_output_images'])):
                save_diagnostic(output / f'frame-{index+1:06d}.jpg', frame, reference, detected, boxes, points, accepted, held, transform, raw_path, aligned_path, old, display_previous_to_ref)
            previous_gray, previous_mask, previous_to_ref = gray, mask, transform
            previous_exclusion_available = bool(boxes)
        (output / 'diagnostics.json').write_text(json.dumps({'thresholds': THRESHOLDS, 'direction': 'current pixels to frame 1 pixels', 'fixed_exclusions': exclusions, 'ranged_exclusions': ranged_exclusions, 'frames': diagnostics}, indent=2, allow_nan=False), encoding='utf-8')
        return len(diagnostics)
    finally:
        cap.release()
        if pose is not None:
            pose.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('video', type=Path)
    parser.add_argument('output', type=Path, help='New directory under storage/app/private')
    parser.add_argument('--roi', type=parse_roi, help='Pose ROI in original pixels: x,y,width,height')
    parser.add_argument('--exclude', type=parse_roi, action='append', default=[], help='Fixed background exclusion rectangle; repeatable')
    parser.add_argument('--exclude-range', action='append', default=[], metavar='START,END,X,Y,W,H', help='Inclusive 1-based frame range and fixed exclusion rectangle; repeatable')
    parser.add_argument('--image-frame', type=int, action='append', default=[], help='Save this 1-based frame instead of interval sampling; repeatable')
    parser.add_argument('--reconnect-anchor', type=int, help='Retain this reference-connected frame for direct reconnection')
    parser.add_argument('--reconnect-candidate', type=int, action='append', default=[], help='Try this frame after a chain failure; repeatable')
    parser.add_argument('--segment-start', type=int, help='Start a separate, disconnected diagnostic coordinate system at this frame')
    parser.add_argument('--ffprobe', default='ffprobe')
    parser.add_argument('--max-frames', type=int, default=300)
    parser.add_argument('--image-every', type=int, default=25)
    args = parser.parse_args()
    if args.max_frames < 1 or args.image_every < 1:
        parser.error('Frame limits must be positive')
    if len(set(args.image_frame)) > THRESHOLDS['max_output_images'] or any(n < 1 for n in args.image_frame):
        parser.error('Invalid image frame list')
    if bool(args.reconnect_anchor) != bool(args.reconnect_candidate) or (args.reconnect_anchor is not None and (args.reconnect_anchor < 1 or any(n <= args.reconnect_anchor + 1 for n in args.reconnect_candidate))):
        parser.error('Reconnection requires an anchor and later candidates with at least one skipped frame')
    if args.segment_start is not None and not 1 <= args.segment_start <= args.max_frames:
        parser.error('Segment start must be within the processed frame range')
    ranged_exclusions = []
    for value in args.exclude_range:
        try:
            start, end, x, y, w, h = map(int, value.split(','))
            if start < 1 or end < start:
                raise ValueError()
        except ValueError:
            parser.error('Expected START,END,X,Y,W,H with a valid inclusive frame range')
        ranged_exclusions.append((start, end, (x, y, w, h)))
    try:
        count = run(args.video, args.output, args.ffprobe, args.roi, args.exclude, args.max_frames, args.image_every, ranged_exclusions, args.image_frame, args.reconnect_anchor, args.reconnect_candidate, args.segment_start)
    except (ValueError, OSError, RuntimeError) as error:
        parser.exit(1, f'Diagnostic failed: {error}\n')
    print(f'Processed {count} frames; diagnostic output is private.')


if __name__ == '__main__':
    main()
