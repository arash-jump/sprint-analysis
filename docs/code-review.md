# Local Code Review Guide

Use this guide for local reviews of this repository. A review is read-only unless the user explicitly asks for fixes.

## Establish the review scope

- State the base and head branches or commits being compared.
- Check the branch and worktree first. Identify staged, unstaged, and untracked changes; do not overwrite or silently include pre-existing work.
- For PRs, prioritize problems introduced by the change. Report pre-existing problems separately.
- Read relevant callers, callees, views, and tests when the diff alone is insufficient.
- Prioritize incorrect metrics, functional regressions, data protection, and reliability over style preferences.
- Distinguish confirmed behavior from assumptions. Do not invent findings to fill a report.

## Measurement and analysis

- Trace coordinates through the uploaded source, FFmpeg output, browser video display, canvas backing dimensions, saved calibration points, and OpenCV-decoded frames. Check scaling, aspect ratio, rotation, crop/padding, and coordinate bounds. Calibration clicks are mapped to intrinsic video dimensions; Python measures the right-hip x-position in decoded-frame pixels.
- Check video dimensions and time information before and after transcoding. FFmpeg uses timestamp passthrough and FFprobe supplies per-frame `best_effort_timestamp_time` for the converted video. Verify decoded-frame count/order agrees with the timestamp list, including variable-frame-rate inputs; do not infer constant frame rate from a reported FPS.
- Verify units and definitions end to end: calibration coordinates are pixels, calibration distance is used to derive metres per pixel, and velocity is reported in metres per second. The current segment length defaults to 10 m.
- Check missing pose detections, low landmark visibility, outliers, and coordinate jitter. The script uses the right-hip landmark without a visibility threshold or smoothing; elapsed time across missing detections comes from the timestamps of the adjacent valid detections. If fewer than two usable hip detections exist, analysis must fail and expose available per-frame diagnostics without saving a velocity result.
- Check calibration-point count, numeric finiteness, bounds, and duplicate points at both request and analysis boundaries. The current request validates JSON syntax; Python reads the first two points and rejects non-finite or coincident coordinates.
- Compare displayed distance segments with the actual measured range. Segments follow accumulated horizontal displacement, end at the actual estimated distance, and the chart labels their start/end distances. `run_distance` is stored and displayed as a reference only; it is not passed to Python and must not affect the metric calculation.
- Trace each input field to its calculation and display. Do not assume a stored or displayed value affects the metrics.
- Separate mathematical correctness from real-video estimation accuracy: tests with synthetic positions can verify formulas, but cannot establish pose-detection accuracy for real footage or camera setups.

## Application behavior and data protection

- Verify owner-scoped access for calibration pages, video streaming, input details, and analysis. The current controllers query `ManualData` by the authenticated user; analysis results are saved with that user's ID.
- Review upload type/size validation, private-disk storage, and whether converted or temporary files can be served without owner authorization.
- For FFmpeg and Python process execution, inspect argument handling, exit status, timeouts, error reporting, and cleanup after startup, conversion, or analysis failures. The transcoder uses Symfony Process with a 600-second timeout and cleans up its temporary source; the Python analysis is currently invoked through `shell_exec`.
- Check retries, browser refreshes, and repeated analysis requests for duplicate result records. The current analysis endpoint saves a result whenever it is requested.
- Ensure user-visible errors and logs are useful without exposing credentials, private video contents, or unnecessary filesystem details.

## Tests and verification

- Look for focused regression tests and boundary cases for the changed behavior.
- Separate what mocks prove from real integrations. The transcoding feature tests use a fake FFmpeg executable; they do not prove real codec compatibility. Python metric tests use synthetic positions; real-video playback, decoding, and pose-estimation behavior require an actual supported video.
- Run relevant existing checks when practical:

  ```bash
  php artisan test
  ./venv/bin/python -m unittest discover -s python -p 'test_*.py'
  npm run build
  ```

- Report exactly which checks ran and their results. State any unrun checks and what they would verify; do not imply that a build or mock test validates real-video accuracy.

## Findings format

Report actionable findings only. For each finding, include:

- **Importance:** severity and a short title
- **File and line:** precise location
- **Trigger:** conditions required to reproduce it
- **Impact:** user, data, or metric consequence
- **Verification:** test, scenario, or evidence that confirms it

Separate confirmed findings from hypotheses. If no findings are confirmed, say so and list important unverified areas.
