# Project Instructions

## Project and workflow

This is a Laravel 12 sprint-video analysis app. Authenticated users upload videos; Laravel validates them and `VideoTranscoder` converts them with FFmpeg to H.264/AAC MP4 files on private storage while preserving frame timestamps. The calibration page records points in the source video's pixel coordinates. Users enter a calibration distance and a reference run distance; no FPS is entered. `CalculatedDataController` passes the video path, calibration points, and calibration distance to `python/calculate.py`. Python uses FFprobe presentation timestamps and OpenCV/MediaPipe's right-hip horizontal position. `python/analysis_metrics.py` calculates timestamp-based velocity and 10 m distance segments, which Laravel saves and displays with a chart.

Calibration points are mapped from the displayed video size to the video's intrinsic dimensions; Python measures landmarks in decoded-frame pixels. `run_distance` is stored and displayed as reference information but does not affect the estimated distance or speed.

## Environment and commands

Requirements: PHP 8.2+, Composer, Node.js/npm, Python 3 with dependencies from `requirements.txt`, and FFmpeg with H.264/AAC encoders. Analysis expects the interpreter at `venv/bin/python3`.

Typical local setup and run (see `README.md` or `README.ja.md` for details):

```bash
composer install
cp .env.example .env
php artisan key:generate
touch database/database.sqlite
php artisan migrate
python3 -m venv venv
./venv/bin/python -m pip install -r requirements.txt
npm install
npm run build
php artisan serve
```

Run the configured Laravel tests, Python metric tests, and frontend build with:

```bash
php artisan test
./venv/bin/python -m unittest discover -s python -p 'test_*.py'
npm run build
```

## Change scope

Keep changes limited to the requested behavior. Avoid unrelated refactoring and preserve existing behavior unless a change is required. Add or update focused tests for behavior changes.

## Code reviews

When asked to review code, read [`docs/code-review.md`](docs/code-review.md) and follow its review-only rules. The instruction not to change code applies only to review requests; it does not restrict implementation work when changes are requested.
