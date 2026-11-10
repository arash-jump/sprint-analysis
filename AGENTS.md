# Project Instructions

## Project and workflow

This is a Laravel 12 sprint-video analysis app. Authenticated users upload videos; Laravel validates them and `VideoTranscoder` converts them with FFmpeg to H.264/AAC MP4 files on private storage. The calibration page records points in JavaScript. Users then enter FPS and distances; `CalculatedDataController` passes those values and the video path to `python/calculate.py`, which uses OpenCV and MediaPipe's right-hip horizontal position. `python/analysis_metrics.py` converts frame differences and pixel scale to velocity metrics, which Laravel saves and displays with a chart.

The current calibration script scales canvas coordinates using fixed 1920×1080 values, while Python measures positions using each decoded frame's width. The current metric code uses the entered FPS and calibration distance; `run_distance` is passed through but does not limit the analysis, and distance segments default to 10 m.

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
./venv/bin/python -m unittest discover -s python -p 'test_analysis_metrics.py'
npm run build
```

## Change scope

Keep changes limited to the requested behavior. Avoid unrelated refactoring and preserve existing behavior unless a change is required. Add or update focused tests for behavior changes.

## Code reviews

When asked to review code, read [`docs/code-review.md`](docs/code-review.md) and follow its review-only rules. The instruction not to change code applies only to review requests; it does not restrict implementation work when changes are requested.
