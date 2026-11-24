# Experimental camera-motion diagnostic

This independent local tool investigates fixed-position horizontal camera pans without zoom. It does not alter production pose acceptance, calibration, distance, or velocity. A single homography is only an approximation: parallax, nearby objects, lens distortion, camera translation, zoom, rolling shutter, and moving backgrounds may invalidate it. Neither a passing diagnostic nor a visually good overlay proves speed accuracy.

Run from the project root, using a new output directory below `storage/app/private` (the command refuses an existing output directory):

```sh
./venv/bin/python python/diagnose_camera_motion.py \
  storage/app/private/movies/example.mp4 \
  storage/app/private/camera-motion-diagnostics/example-run \
  --roi 365,317,1384,244 --exclude 0,0,100,100 \
  --max-frames 150 --image-every 10
```

Replace all example coordinates and paths. `--roi` is optional and affects pose detection only; background tracking still uses the entire video frame. `--exclude` is an optional repeatable fixed rectangle in original-frame pixels, for moving objects or areas that may contain the runner. It must cover all relevant movement over the frames where pose detection is missing. The tool also expands a bounding box around detected pose landmarks and excludes that region in both ends of each tracked pair. This is only a heuristic: limbs, other people, shadows, vegetation and vehicles can extend outside these boxes. Review and exclude them manually; RANSAC and the numeric thresholds do not guarantee static background points. If neither a pose box nor a manual exclusion exists for a frame, the transform is invalid. A manual exclusion is an operator assertion, not proof that all moving objects were masked.

For a rectangle active only on inclusive 1-based frames 216–240, use `--exclude-range 216,240,300,130,650,590`. This option is repeatable. A pair is masked with each endpoint's own frame mask, so include the previous frame when both endpoints need exclusion. Use repeated `--image-frame 217 --image-frame 232` to save selected frames instead of periodic images (up to the same image limit). Settings and per-frame active rectangles are recorded in JSON.

Frames are 1-based and use relative FFprobe presentation timestamps. One MediaPipe video-mode instance processes frames in order, and the existing pose code restores ROI-local landmarks to original decoded-frame pixels before a hip point is transformed. Hip positions are recorded only when they satisfy the existing right-hip acceptance test. This run performs fresh inference with the same code and settings; it does not reuse a saved production inference result. Production JSONL landmarks are temporary and are deleted after analysis.

## Direction and failure policy

The RANSAC homography `H_prev_to_curr` maps the previous frame to the current frame. The transform reported in `diagnostics.json` maps the current frame to frame 1:

```text
H_current_to_reference = H_previous_to_reference × inverse(H_prev_to_curr)
```

Frame 1 is the reference and has the identity transform only when its exclusion requirement is met. Every fifth correspondence is held out of RANSAC; its median error is evaluated separately. Inlier ratios use the remaining training correspondences as their denominator. The training and inlier spread values are the smaller convex-hull area of the two point sets divided by frame area; a large hull can still conceal gaps or clusters. Thresholds in `THRESHOLDS` are provisional. Too few or poorly distributed points, low inlier count or ratio, high training or held-out error, non-finite/singular transforms, limited overlap with frame 1, and the maximum chain length invalidate a transform. A failed link invalidates the connection to the reference for all subsequent frames rather than silently using an identity matrix or restarting a disconnected coordinate system. Adjacent-pair estimates still run and are recorded separately as `local_valid`/`local_reason`; they do not restore the broken reference chain (`reference_valid`/`reference_reason`). These checks limit, but do not measure or eliminate, accumulated drift. Held-out errors assess each adjacent pair, not long-term alignment to frame 1. Inspect the reference overlay throughout the sequence.

An optional explicit reconnect experiment retains an already reference-connected anchor and tests direct tracking to selected later frames: `--reconnect-anchor 233 --reconnect-candidate 235 --reconnect-candidate 236`. It uses the same feature detector, Lucas–Kanade tracking settings and thresholds as adjacent tracking, with the masks of both endpoints. `direct_reconnection` records its anchor, candidate, local test, reference overlap and outcome. The direct homography maps anchor to candidate, and the candidate-to-frame-1 transform is `anchor_to_frame_1 @ inverse(anchor_to_candidate)`. Earlier missing frames remain invalid; failed candidates cannot restore the chain. Held-out correspondences are selected independently per estimate and are not a matched common evaluation set across the direct and adjacent estimates.

`--segment-start 235` additionally records a separate segment coordinate system based on that frame, as `current_to_segment` and `segment_reason`. This does not reconnect the segment to frame 1. A bad subsequent link invalidates that segment's chain as well. The default remains no reconnect and no new segment.

## Output

`diagnostics.json` records each processed frame, relative PTS, point counts and held-out errors, status and reason, overlap, matrix, and raw and transformed hip positions. Files may contain sensitive footage and coordinates; keep them private. Output images are limited to 12, one every `--image-every` frames. On the left, the original frame has pose overlay, exclusion rectangles, accepted training points (green), rejected or excluded tracks (red), held-out points (cyan), and the original hip trajectory (yellow). On the right, a half-blend compares frame 1 and the warped current frame, with transformed hip trajectory (magenta). The held-out current and previous positions mapped to the reference are marked cyan and yellow and joined by a line; their separation is a visual cross-check not used for the fit. An invalid alignment is explicitly labelled and has no transformed trajectory for that frame.

The command reads the input without modifying it. It stops at `--max-frames` (default 300) or the end of the timestamp list and does not diagnose later frames. The output directory is not removed on a failure, so partial files can be inspected and are never overwritten by a retry.

## Comparing Lucas–Kanade and ORB

`compare_camera_matching.py VIDEO PREVIOUS_DIAGNOSTICS NEW_PRIVATE_OUTPUT --ffprobe ffprobe` compares 233→234, 234→235 and 233→235. It reuses endpoint masks stored in the supplied diagnostic; use only with the exact same video and run (timestamps are checked, but file identity is not). `--pair START,END` can be repeated for other pairs already present in that diagnostic. It does not rerun pose inference or change the original records. The script applies the same `estimate_link` RANSAC and quality thresholds to both methods.

ORB detects at most 1500 features per frame with the settings recorded in `comparison.json`. Its binary descriptors use Hamming distance, a 0.75 nearest/second-nearest ratio in both directions, and mutual best matches to remove ambiguous and duplicate pairs. Keypoint centres respect both exclusion masks; the descriptor patch may still overlap a mask boundary, so this does not prove that moving content was fully excluded. LK uses the existing feature detector and LK settings. The JSON contains filter counts, original-frame coordinate transforms, timing (one run, including feature/matching and RANSAC, not decoding or drawing), and independently selected holdout errors. Holdout point sets differ between methods and have not been manually verified as static ground truth. Rates and holdout medians alone do not establish a fair accuracy comparison.

Each pair produces a bounded correspondence image and, only for a locally accepted transform, a blend of the source and aligned target. Magenta rectangles are the saved exclusion boxes. These are local pair comparisons, not proof of alignment to frame 1. For 233→235, only an accepted local transform is composed with the saved 233-to-frame-1 transform; the existing reference-overlap threshold still applies. No transform is emitted if reference composition fails, and frame 234 is not filled in.
