"""Compare background correspondences only; does not alter analysis or reconnect chains."""
from __future__ import annotations
import argparse
import json
import time
from pathlib import Path
import cv2
import numpy as np
from diagnose_camera_motion import (PRIVATE_ROOT, THRESHOLDS, background_mask,
    compose_to_reference, estimate_link)
from video_timestamps import read_frame_timestamps

ORB_SETTINGS = {'nfeatures': 1500, 'scaleFactor': 1.2, 'nlevels': 8,
                'edgeThreshold': 31, 'firstLevel': 0, 'WTA_K': 2,
                'scoreType': cv2.ORB_HARRIS_SCORE, 'patchSize': 31, 'fastThreshold': 20}
RATIO = .75


def ratio_matches(forward, reverse, ratio=RATIO):
    """Bidirectional ratio test and mutual best produce unique pairs."""
    def select(rows):
        return {pair[0].queryIdx: pair[0] for pair in rows
                if len(pair) >= 2 and pair[0].distance < ratio * pair[1].distance}
    f, r = select(forward), select(reverse)
    result = [m for m in f.values() if m.trainIdx in r and r[m.trainIdx].trainIdx == m.queryIdx]
    return sorted(result, key=lambda m: (m.queryIdx, m.trainIdx)), len(f), len(r)


def orb_correspondences(source, target, source_mask, target_mask):
    orb = cv2.ORB_create(**ORB_SETTINGS)
    a, da = orb.detectAndCompute(source, source_mask)
    b, db = orb.detectAndCompute(target, target_mask)
    counts = {'source_keypoints': len(a), 'target_keypoints': len(b),
              'forward_knn_queries': 0, 'reverse_knn_queries': 0,
              'forward_ratio': 0, 'reverse_ratio': 0, 'mutual_unique': 0}
    empty = np.empty((0, 2), np.float32)
    if da is None or db is None or len(da) < 2 or len(db) < 2:
        return empty, empty, counts
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
    forward = matcher.knnMatch(da, db, k=2)
    reverse = matcher.knnMatch(db, da, k=2)
    counts['forward_knn_queries'], counts['reverse_knn_queries'] = len(forward), len(reverse)
    matches, counts['forward_ratio'], counts['reverse_ratio'] = ratio_matches(forward, reverse)
    counts['mutual_unique'] = len(matches)
    if not matches:
        return empty, empty, counts
    return (np.asarray([a[m.queryIdx].pt for m in matches], np.float32),
            np.asarray([b[m.trainIdx].pt for m in matches], np.float32), counts)


def lk_correspondences(source, target, source_mask, target_mask):
    h, w = source.shape
    features = cv2.goodFeaturesToTrack(source, maxCorners=THRESHOLDS['max_features'], qualityLevel=.01, minDistance=8, mask=source_mask)
    counts = {'source_keypoints': 0, 'lk_status_ok': 0, 'inside_target': 0, 'outside_target_exclusion': 0}
    empty = np.empty((0, 2), np.float32)
    if features is None:
        return empty, empty, counts
    counts['source_keypoints'] = len(features)
    tracked, status, _ = cv2.calcOpticalFlowPyrLK(source, target, features, None)
    if tracked is None or status is None:
        return empty, empty, counts
    old, new = features.reshape(-1, 2), tracked.reshape(-1, 2)
    idx = np.flatnonzero(status.ravel().astype(bool) & np.isfinite(new).all(axis=1))
    counts['lk_status_ok'] = len(idx)
    idx = idx[(new[idx,0]>=0)&(new[idx,0]<w)&(new[idx,1]>=0)&(new[idx,1]<h)]
    counts['inside_target'] = len(idx)
    idx = idx[target_mask[new[idx,1].astype(int),new[idx,0].astype(int)] != 0]
    counts['outside_target_exclusion'] = len(idx)
    return old[idx], new[idx], counts


def visuals(out, name, first, second, old, new, inliers, held, matrix, boxes_by_frame):
    h,w=first.shape[:2]
    canvas=np.hstack([first.copy(),second.copy()])
    for side, boxes in enumerate(boxes_by_frame):
        for x,y,bw,bh in boxes:
            cv2.rectangle(canvas,(x+side*w,y),(x+bw+side*w,y+bh),(255,0,255),2)
    for mask,color in [(inliers,(0,255,0)),(~inliers & ~held,(0,0,255)),(held,(255,255,0))]:
        indices=np.flatnonzero(mask)
        if len(indices):
            for i in indices[np.linspace(0,len(indices)-1,min(12,len(indices)),dtype=int)]:
                a=tuple(np.rint(old[i]).astype(int)); b=tuple(np.rint(new[i]+[w,0]).astype(int))
                cv2.line(canvas,a,b,color,1,cv2.LINE_AA);cv2.circle(canvas,a,3,color,-1);cv2.circle(canvas,b,3,color,-1)
    cv2.putText(canvas,'GREEN inlier RED outlier CYAN holdout', (8,24), cv2.FONT_HERSHEY_SIMPLEX,.6,(255,255,255),2)
    if not cv2.imwrite(str(out/f'{name}-matches.jpg'),canvas): raise OSError('Could not write image')
    if matrix is not None:
        aligned=cv2.warpPerspective(second,np.linalg.inv(matrix),(w,h))
        blend=cv2.addWeighted(first,.5,aligned,.5,0)
        cv2.putText(blend,'source + warped target (local only)',(8,24),cv2.FONT_HERSHEY_SIMPLEX,.6,(255,255,255),2)
        if not cv2.imwrite(str(out/f'{name}-aligned.jpg'),blend): raise OSError('Could not write image')


def run(video, diagnostics, output, ffprobe, pairs=None):
    pairs = pairs or [(233,234),(234,235),(233,235)]
    frame_numbers = {n for pair in pairs for n in pair} | {1}
    out=output.resolve()
    try: out.relative_to(PRIVATE_ROOT)
    except ValueError as error: raise ValueError('Output must be under storage/app/private') from error
    if out == PRIVATE_ROOT or out.exists(): raise ValueError('Output must be a new directory')
    saved=json.loads(diagnostics.read_text())
    if saved['thresholds'] != THRESHOLDS: raise ValueError('Thresholds differ from source diagnostic')
    rows=saved['frames']; ts=read_frame_timestamps(str(video),ffprobe)
    capture=cv2.VideoCapture(str(video))
    if not capture.isOpened(): raise ValueError('Cannot open video')
    frames={}
    try:
        for i in range(1,max(frame_numbers)+1):
            ok, frame=capture.read()
            if not ok: raise ValueError('Video ended before requested frame')
            if i in frame_numbers: frames[i]=frame
    finally: capture.release()
    if any(abs(rows[n-1]['timestamp_seconds']-(ts[n-1]-ts[0]))>1e-6 for n in frame_numbers if n != 1):
        raise ValueError('Video timeline does not match diagnostic')
    out.mkdir(mode=0o700,parents=True)
    results=[]
    for a,b in pairs:
        h,w=frames[a].shape[:2]; masks=[]; boxes_by_frame=[]
        for n in (a,b):
            row=rows[n-1];boxes=row['manual_exclusion_boxes']+([row['automatic_runner_box']] if row['automatic_runner_box'] else [])
            if not boxes: raise ValueError('Missing runner exclusion')
            boxes_by_frame.append(boxes)
            masks.append(background_mask(w,h,boxes))
        source=cv2.cvtColor(frames[a],cv2.COLOR_BGR2GRAY); target=cv2.cvtColor(frames[b],cv2.COLOR_BGR2GRAY)
        for name,fn in [('lk',lk_correspondences),('orb',orb_correspondences)]:
            start=time.perf_counter();old,new,counts=fn(source,target,*masks)
            matrix,info,inliers,held=estimate_link(old,new,w,h);elapsed=time.perf_counter()-start
            record={'source_frame':a,'target_frame':b,'method':name,'counts':counts,'estimate':info,'elapsed_seconds':elapsed,
                    'local_transform_source_to_target':matrix.tolist() if matrix is not None else None,
                    'reference_composition':None}
            if a==233 and b==235 and matrix is not None:
                anchor=rows[232]['current_to_reference']
                if not rows[232]['reference_valid'] or anchor is None: raise ValueError('Reference anchor invalid')
                transform,overlap,reason=compose_to_reference(np.asarray(anchor),matrix,w,h,234)
                record['reference_composition']={'valid':transform is not None,'reason':reason,'overlap':overlap,
                    'target_to_frame1':transform.tolist() if transform is not None else None}
                if transform is not None:
                    warp=cv2.warpPerspective(frames[b],transform,(w,h));blend=cv2.addWeighted(frames[1],.5,warp,.5,0)
                    if not cv2.imwrite(str(out/f'{name}-233-235-reference.jpg'),blend): raise OSError('Could not write image')
            visuals(out,f'{name}-{a}-{b}',frames[a],frames[b],old,new,inliers,held,matrix,boxes_by_frame)
            results.append(record)
    (out/'comparison.json').write_text(json.dumps({'video_frames':sorted(frame_numbers),'pts_relative_seconds':{str(n):ts[n-1]-ts[0] for n in frame_numbers},'masks_from_saved_diagnostic':{str(n):{'manual':rows[n-1]['manual_exclusion_boxes'],'pose':rows[n-1]['automatic_runner_box']} for n in frame_numbers},'thresholds':THRESHOLDS,'orb_settings':ORB_SETTINGS,'orb_match_filter':{'distance':'Hamming','ratio':RATIO,'mutual_best':True},'results':results},indent=2,allow_nan=False))
    return results


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('video',type=Path);p.add_argument('diagnostics',type=Path);p.add_argument('output',type=Path);p.add_argument('--ffprobe',default='ffprobe');p.add_argument('--pair',action='append',default=[]);a=p.parse_args()
    try:
        pairs=[tuple(map(int,value.split(','))) for value in a.pair]
        if any(len(pair)!=2 or pair[0]<1 or pair[1]<=pair[0] for pair in pairs): raise ValueError()
    except ValueError: p.error('Each pair must be START,END with 1 <= START < END')
    try:
        results=run(a.video,a.diagnostics,a.output,a.ffprobe,pairs)
    except (ValueError,OSError,RuntimeError,cv2.error) as e: p.exit(1,f'Comparison failed: {e}\n')
    for r in results: print(r['method'],r['source_frame'],r['target_frame'],r['estimate']['reason'])
if __name__=='__main__': main()
