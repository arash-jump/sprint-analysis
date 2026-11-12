@extends('layouts.app')

@section('title', 'Analysis Result')

@section('content')
    <div class="container my-5">
        <h1 class="h2 text-primary mb-4"><i class="fa-solid fa-chart-line"></i>Analysis Result</h1>

        <div class="bg-white shadow rounded p-4 mb-5">
            <h2 class="h5 text-secondary mb-3">Calculated Data</h2>
            <ul>
                <li><strong>Pixel Distance:</strong> {{ $result['pixel_distance'] ?? $calculated->pixel_distance}}</li>
                <li><strong>Scale (m/px):</strong> {{ $result['scale_m_per_px'] ?? $calculated->scale_m_per_px}}</li>
                <li><strong>Estimated horizontal path distance:</strong> {{ isset($result['estimated_distance_m']) ? number_format($result['estimated_distance_m'], 2).' m' : 'Unavailable for this saved result' }}</li>
                <li><strong>Analysis duration (first to last detected pose):</strong> {{ isset($result['analysis_duration_seconds']) ? number_format($result['analysis_duration_seconds'], 2).' s' : 'Unavailable for this saved result' }}</li>
                <li><strong>Horizontal movement detected:</strong> {{ isset($result['movement_detected']) ? ($result['movement_detected'] ? 'Yes' : 'No') : 'Unavailable for this saved result' }}</li>
                <li><strong>Average speed (horizontal path distance / analysis duration):</strong> {{ number_format($result['velocity_avg'] ?? $calculated->velocity_avg, 2) }} m/s</li>
                <li><strong>Maximum interval speed:</strong> {{ number_format($result['velocity_max'] ?? $calculated->velocity_max, 2) }} m/s</li>
                <li><strong>Reference run distance (not used to adjust or stop the estimate):</strong> {{ number_format((float) $manual->run_distance, 2) }} m</li>
            </ul>
            <p class="text-muted mb-0">
                Speeds use {{ ($result['time_basis'] ?? null) === 'converted_video_presentation_timestamps' ? 'presentation timestamps from the converted video' : 'the time basis recorded for this result' }}
                and horizontal movement of the MediaPipe {{ ($result['landmark_used'] ?? 'right_hip') === 'left_hip' ? 'left-hip' : 'right-hip' }} landmark. Maximum interval speed is not an instantaneous peak.
                Slow-motion video reports playback-time speed, not real-world speed.
            </p>
        </div>

        @include('data.manual.partials.frame_diagnostics')

        <div class="bg-white shadow rouinded p-4 mb-5">
            <h2 class="text-secondary mb-3">Sprint Video</h2>
            <video class="w-100" src="{{route('manual.video', $manual->id)}}" controls></video>
        </div>

        <div class="bg-white shadow rounded p-4">
            <h2 class="h5 text-secondary mb-3">Velocity Chart</h2>
            <canvas id="velocityChart" width="400" height="200" 
                    data-max="{{ $result['dummy_max_velocity'] ?? $result['velocity_max'] ?? $calculated->velocity_max}}"
                    data-avg="{{ $result['dummy_avg_velocity'] ?? $result['velocity_avg'] ?? $calculated->velocity_avg}}"
                    data-labels='@json(collect($result['segment_speeds'])->map(fn($s) => number_format((float) $s['start'], 2).'-'.number_format((float) $s['end'], 2).' m'))'
                    data-values='@json(collect($result['segment_speeds'])->pluck('avg_velocity'))'
                    ></canvas>
            <script src="{{asset('js/chart_velocity.js')}}"></script>
        </div>

       
    </div>
@endsection
