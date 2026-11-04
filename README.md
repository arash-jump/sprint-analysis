# Sprint Analysis

[日本語版 README](README.ja.md)

A web application for analyzing sprint performance from video. Upload a video, mark calibration points, and enter the recording conditions to calculate and display velocity metrics.

## Features

- User registration and login
- Sprint video upload
- Calibration point selection on the video
- Input for frame rate (FPS), calibration distance, and running distance
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

### 2. Set up the Python analysis environment

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
deactivate
```

### 3. Build the frontend and start the application

```bash
npm install
npm run build
php artisan serve
```

Open <http://127.0.0.1:8000> in your browser and register or log in.

## Usage

1. After logging in, open `/manual/input` and upload a video.
2. Select calibration points on the video and save them.
3. Enter the FPS, calibration distance, and running distance.
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
| `requirements.txt` | Pinned direct Python dependencies for video analysis |
| `routes/web.php` | Web routes |

## Data and Notes

- This project does not currently declare a license. Its source code is not granted additional reuse or redistribution permissions; third-party dependencies remain subject to their own licenses. MediaPipe is distributed under Apache License 2.0.
- Do not commit `.env`, the SQLite database, uploaded videos, or the Python virtual environment to GitHub.
- Uploaded videos are stored privately in `storage/app/private/movies/` and streamed only to their authenticated owner. If videos contain identifiable people, obtain their consent and handle the files responsibly.
- Videos uploaded before this private-storage change may still be in `storage/app/public/movies/`. They are not served through the new private route. Move any videos you need to keep into `storage/app/private/movies/` and remove their public copies.
- The analysis controller invokes `venv/bin/python3` relative to the project root. Running the app on Windows requires changing the interpreter path.
- Direct Python dependencies are pinned in `requirements.txt`. Use Python 3.9 or later; compatible package versions may vary by Python version and platform.
