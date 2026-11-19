@extends('layouts.app')

@section('title', 'Input Detailed Data')

@section('content')
    <div class="container my-4">
        <div class="row w-100 bg-white shadow mx-auto rounded p-3">
            <form
                action="{{ route('manual.input_detail', $manual->id) }}"
                class="w-100 mx-auto"
                method="post"
                id="analysis-settings-form"
                data-timeline-url="{{ route('manual.frame_timestamps', $manual->id) }}"
            >
                @csrf
                <h1 class="h2 my-3 text-primary"><i class="fa-solid fa-database"></i> Input Detailed Data</h1>

                @if (session('error'))
                    <div class="alert alert-danger" role="alert">{{ session('error') }}</div>
                @endif
                @if ($errors->any())
                    <div class="alert alert-danger" role="alert">
                        <ul class="mb-0">
                            @foreach ($errors->all() as $error)
                                <li>{{ $error }}</li>
                            @endforeach
                        </ul>
                    </div>
                @endif

                <div class="mb-4">
                    <h2 class="h5">Measurement interval and optional ROI</h2>
                    <div class="video-selection-wrapper">
                        <video id="measurement-video" class="w-100" controls playsinline preload="metadata">
                            <source src="{{ route('manual.video', $manual->id) }}">
                        </video>
                        <canvas id="roi-canvas" aria-label="ROI drawing surface"></canvas>
                    </div>
                    <p id="timeline-status" class="small text-muted mt-2" role="status" aria-live="polite">
                        Loading the video's presentation-timestamp timeline…
                    </p>
                    <p>
                        Current video position:
                        <strong><span id="current-frame">—</span></strong>
                    </p>
                    <div class="row g-3">
                        <div class="col-md-6">
                            <label class="form-label" for="measurement_start_frame">Start frame (inclusive)</label>
                            <div class="input-group">
                                <input
                                    class="form-control"
                                    type="number"
                                    min="1"
                                    step="1"
                                    name="measurement_start_frame"
                                    id="measurement_start_frame"
                                    value="{{ old('measurement_start_frame', $manual->measurement_start_frame ?? 1) }}"
                                    required
                                >
                                <button class="btn btn-outline-secondary" type="button" id="use-current-start">
                                    Use current frame
                                </button>
                            </div>
                            <small id="start-frame-time" class="form-text text-muted"></small>
                        </div>
                        <div class="col-md-6">
                            <label class="form-label" for="measurement_end_frame">End frame (inclusive)</label>
                            <div class="input-group">
                                <input
                                    class="form-control"
                                    type="number"
                                    min="1"
                                    step="1"
                                    name="measurement_end_frame"
                                    id="measurement_end_frame"
                                    value="{{ old('measurement_end_frame', $manual->measurement_end_frame ?? '') }}"
                                    required
                                >
                                <button class="btn btn-outline-secondary" type="button" id="use-current-end">
                                    Use current frame
                                </button>
                            </div>
                            <small id="end-frame-time" class="form-text text-muted"></small>
                        </div>
                    </div>
                    <p class="form-text">
                        Frames are numbered from 1. Both selected frames are included. Times and frame mapping use
                        the converted video's per-frame presentation timestamps, not an FPS estimate.
                        Frames before the start are still fed to the same model for tracking, but are excluded from
                        the measurement and its quality rates.
                    </p>
                    @error('measurement_start_frame') <p class="text-danger">{{ $message }}</p> @enderror
                    @error('measurement_end_frame') <p class="text-danger">{{ $message }}</p> @enderror

                    <hr>
                    <div class="form-check">
                        <input
                            class="form-check-input"
                            type="checkbox"
                            value="1"
                            id="roi_enabled"
                            name="roi_enabled"
                            @checked(old('roi_enabled', $manual->analysis_roi !== null))
                        >
                        <label class="form-check-label" for="roi_enabled">Use a fixed ROI from this video</label>
                    </div>
                    <p class="form-text">
                        Turn this on, then drag a rectangle around the subject. ROI coordinates are source-video pixels.
                        The same fixed rectangle is used for every model input frame; automatic tracking is not used.
                    </p>
                    <div class="d-flex gap-2 mb-2">
                        <button class="btn btn-outline-secondary btn-sm" type="button" id="clear-roi">Clear ROI</button>
                        <span id="roi-coordinates" class="small text-muted" aria-live="polite">No ROI selected (full frame).</span>
                    </div>
                    <input type="hidden" name="roi_x" id="roi_x" value="{{ old('roi_x', $manual->analysis_roi['x'] ?? '') }}">
                    <input type="hidden" name="roi_y" id="roi_y" value="{{ old('roi_y', $manual->analysis_roi['y'] ?? '') }}">
                    <input type="hidden" name="roi_width" id="roi_width" value="{{ old('roi_width', $manual->analysis_roi['width'] ?? '') }}">
                    <input type="hidden" name="roi_height" id="roi_height" value="{{ old('roi_height', $manual->analysis_roi['height'] ?? '') }}">
                </div>

                <div class="mb-3">
                    <label for="calibration_distance">Calibration Distance (m)</label>
                    <input
                        type="number"
                        class="form-control"
                        name="calibration_distance"
                        id="calibration_distance"
                        step="0.01"
                        value="{{ old('calibration_distance', $manual->calibration_distance) }}"
                        required
                    >
                    @error('calibration_distance')
                        <p class="text-danger">{{ $message }}</p>
                    @enderror
                </div>
                <div class="mb-3">
                    <label for="run_distance">Reference Run Distance (m)</label>
                    <input
                        type="number"
                        class="form-control"
                        name="run_distance"
                        id="run_distance"
                        step="0.01"
                        value="{{ old('run_distance', $manual->run_distance) }}"
                        required
                    >
                    <small class="form-text text-muted">For reference only; it does not change or limit the video-based estimate.</small>
                    @error('run_distance')
                        <p class="text-danger">{{ $message }}</p>
                    @enderror
                </div>
                <button type="submit" class="btn btn-primary my-3" id="submit-analysis" disabled>Save and analyze</button>
                <p class="small text-muted">
                    Selecting an interval does not certify measurement accuracy. Existing detection-quality checks still apply.
                </p>
            </form>
        </div>
    </div>
    <style>
        .video-selection-wrapper {
            position: relative;
            width: 100%;
        }

        #roi-canvas {
            position: absolute;
            inset: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
        }

        #roi-canvas.drawing {
            pointer-events: auto;
            cursor: crosshair;
        }
    </style>
    <script src="{{ asset('js/measurement-selection.js') }}"></script>
@endsection
