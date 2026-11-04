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
                <li><strong>Max Velocity:</strong> {{number_format($result['velocity_max'], 2) ?? $calculated->velocity_max}}</li>
                <li><strong>Avg Velocity:</strong> {{number_format($result['velocity_avg'], 2) ?? $calculated->velocity_avg}}</li>
            </ul>
        </div>

        <div class="bg-white shadow rouinded p-4 mb-5">
            <h2 class="text-secondary mb-3">Sprint Video</h2>
            <video class="w-100" src="{{route('manual.video', $manual->id)}}" controls></video>
        </div>

        <div class="bg-white shadow rounded p-4">
            <h2 class="h5 text-secondary mb-3">Velocity Chart</h2>
            <canvas id="velocityChart" width="400" height="200" 
                    data-max="{{ $result['dummy_max_velocity'] ?? $result['velocity_max'] ?? $calculated->velocity_max}}"
                    data-avg="{{ $result['dummy_avg_velocity'] ?? $result['velocity_avg'] ?? $calculated->velocity_avg}}"
                    data-labels='@json(collect($result['segment_speeds'])->map(fn($s) => $s['start'].'-'.$s['end']))'
                    data-values='@json(collect($result['segment_speeds'])->pluck('avg_velocity'))'
                    ></canvas>
            <script src="{{asset('js/chart_velocity.js')}}"></script>
        </div>

       
    </div>
@endsection
