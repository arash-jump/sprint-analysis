# Sprint Analysis

[日本語版 README](README.ja.md)

A web application for analyzing sprint performance from video. Upload a video, mark calibration points, and enter the recording conditions to calculate and display velocity metrics.

## Features

- User registration and login
- Sprint video upload
- Calibration point selection on the video
- Input for calibration distance and reference run distance
- Analysis results and a velocity chart

## Tech Stack

- PHP 8.2+ / Laravel 12
- SQLite (default configuration)
- JavaScript / Bootstrap / Vite
- Python 3 / OpenCV / MediaPipe

## Requirements

- PHP 8.2+ and Composer
- Node.js and npm
- Python 3 and pip
- FFmpeg with the `libx264` and AAC encoders
- FFprobe (included with FFmpeg)

The instructions below are for macOS and Linux. The analysis controller expects the Python interpreter at `venv/bin/python3` in the project root, so create the virtual environment at that location.

## Setup

### 1. Install PHP dependencies and configure the app

```bash
git clone <repository-url>
cd sprint_analysis

composer install
cp .env.example .env
php artisan key:generate
```

In `.env`, keep the filesystem disk set to `local` so uploaded videos remain private and are served through authenticated routes:

```dotenv
FILESYSTEM_DISK=local
```

The default configuration uses SQLite. Create the database file if it does not exist, then run the migrations and create the public storage symlink:

```bash
touch database/database.sqlite
php artisan migrate
```

Uploaded videos are stored on Laravel's private local disk, so a public storage symlink is not needed.

### 2. Install FFmpeg

Video uploads are converted to H.264 MP4 for browser compatibility. Install FFmpeg with H.264 and AAC encoding support:

```bash
# macOS with Homebrew
brew install ffmpeg

# Debian/Ubuntu
sudo apt install ffmpeg
```

If FFmpeg or FFprobe is not on `PATH`, set `FFMPEG_BINARY` or `FFPROBE_BINARY` in `.env` to the corresponding executable path.

### 3. Set up the Python analysis environment

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
deactivate
```

Run the Python calculation tests with:

```bash
./venv/bin/python -m unittest discover -s python -p 'test_*.py'
```

### 4. Build the frontend and start the application

```bash
npm install
npm run build
php artisan serve
```

Open <http://127.0.0.1:8000> in your browser and register or log in.

## Usage

1. After logging in, open `/manual/input` and upload a video.
2. Select calibration points on the video and save them.
3. Enter the calibration distance and reference run distance. FPS is not entered manually; analysis uses frame timestamps from the converted video.
4. Review the calculated metrics and velocity chart.

## Project Structure

| Path | Description |
| --- | --- |
| `app/Http/Controllers/` | Handles requests, renders pages, and invokes analysis |
| `app/Models/` | Database models for users, video input, and analysis results |
| `database/migrations/` | Database schema definitions and changes |
| `resources/views/` | Blade view templates |
| `resources/js/`, `resources/sass/` | Frontend assets built with Vite |
| `public/js/`, `public/css/` | Static assets served directly to the browser |
| `python/calculate.py` | Video analysis and velocity calculations |
| `python/analysis_metrics.py` | Timestamp- and pixel-distance-based velocity and segment calculations |
| `python/video_timestamps.py` | Reads per-frame timestamps with FFprobe |
| `python/test_analysis_metrics.py` | Unit tests for velocity calculations |
| `python/test_video_timestamps.py` | Unit tests for video timestamps |
| `requirements.txt` | Pinned direct Python dependencies for video analysis |
| `routes/web.php` | Web routes |

## Data and Notes

- This project does not currently declare a license. Its source code is not granted additional reuse or redistribution permissions; third-party dependencies remain subject to their own licenses. MediaPipe is distributed under Apache License 2.0.
- Do not commit `.env`, the SQLite database, uploaded videos, or the Python virtual environment to GitHub.
- Uploaded videos are stored privately in `storage/app/private/movies/` and streamed only to their authenticated owner. If videos contain identifiable people, obtain their consent and handle the files responsibly.
- Uploaded videos are converted to H.264/AAC MP4 using FFmpeg before they are stored. Videos uploaded before this conversion was added must be uploaded again to get a browser-compatible copy.
- Velocity is estimated from the horizontal movement of the MediaPipe right-hip landmark. Results depend on camera angle, calibration, and landmark detection quality.
- Time is taken from FFprobe `best_effort_timestamp_time` for the converted MP4 that is analyzed. A reported FPS alone is not treated as proof of constant frame rate; elapsed time comes from the presentation timestamps of detected frames, including gaps between detections. Videos with missing, duplicate, or decreasing timestamps, or a mismatch between FFprobe and decoder frame counts, fail with an analysis error. Transcoding is configured to preserve frame timestamps, but real-video timing accuracy depends on the input and codecs.
- Estimated distance is the accumulated absolute horizontal displacement of the right-hip landmark multiplied by the calibration scale (m/px). Average speed is that horizontal path distance divided by the time from the first to last valid detection. Maximum speed is the largest speed between adjacent valid detections, not an instantaneous peak. No smoothing or outlier rejection is applied.
- Distance sections follow accumulated horizontal path distance in 10 m intervals. When an observed interval crosses a section boundary, time is apportioned in proportion to distance, assuming constant speed within that interval. The final section ends at the actual estimated distance.
- The result page's "Pose Detection Diagnostics" table shows each frame's timestamp, whether pose landmarks were detected, the right-hip image coordinates, and MediaPipe visibility. Visibility is diagnostic information only and is not used to filter detections.
- The entered run distance is reference information only; it does not correct the estimated distance or stop analysis. Speeds use video playback time. Slow-motion or playback-rate-adjusted footage cannot be converted to real-world movement time or speed without separate capture-rate metadata.
- Videos uploaded before this private-storage change may still be in `storage/app/public/movies/`. They are not served through the new private route. Move any videos you need to keep into `storage/app/private/movies/` and remove their public copies.
- The analysis controller invokes `venv/bin/python3` relative to the project root. Running the app on Windows requires changing the interpreter path.
- Direct Python dependencies are pinned in `requirements.txt`. Use Python 3.9 or later; compatible package versions may vary by Python version and platform.
