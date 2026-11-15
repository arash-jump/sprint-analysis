@if (isset($result['frame_diagnostics']) && is_array($result['frame_diagnostics']))
    @include('data.manual.partials.quality_summary')
    <div class="bg-white shadow rounded p-4 mb-5">
        <h2 class="h5 text-secondary mb-3">Pose Detection Diagnostics</h2>
        <p>
            @if (array_key_exists('pose_detection_count', $result))
                Pose detected in {{ $result['pose_detection_count'] }}
                of {{ $result['frame_count'] ?? count($result['frame_diagnostics']) }} frames.
            @else
                Legacy recorded calculation detections: {{ $result['detection_count'] ?? 0 }}.
                Pose count and current quality checks were not recorded for this result.
            @endif
            @if (array_key_exists('accepted_point_count', $result))
                {{ $result['accepted_point_count'] }}
                {{ ($result['landmark_used'] ?? 'right_hip') === 'left_hip' ? 'left-hip' : 'right-hip' }} points were accepted for calculation.
                Visibility, coordinate bounds, and missing detections are used by the operational quality check; passing it does not guarantee measurement accuracy.
            @endif
        </p>
        <details>
            <summary>Show per-frame timestamps, detection, acceptance, and hip measurements</summary>
            <div class="table-responsive mt-3" style="max-height: 28rem; overflow-y: auto;">
                <table class="table table-sm table-striped">
                    <thead>
                        <tr>
                            <th>Frame</th>
                            <th>Time since first frame (s)</th>
                            <th>Pose detected</th>
                            <th>Accepted</th>
                            <th>Rejection reason</th>
                            <th>{{ ($result['landmark_used'] ?? 'right_hip') === 'left_hip' ? 'Left' : 'Right' }} hip X (px)</th>
                            <th>{{ ($result['landmark_used'] ?? 'right_hip') === 'left_hip' ? 'Left' : 'Right' }} hip Y (px)</th>
                            <th>Visibility</th>
                        </tr>
                    </thead>
                    <tbody>
                        @foreach ($result['frame_diagnostics'] as $frame)
                            <tr>
                                <td>{{ $frame['frame_number'] }}</td>
                                <td>{{ number_format((float) $frame['timestamp_seconds'], 6) }}</td>
                                <td>{{ $frame['pose_detected'] ? 'Yes' : 'No' }}</td>
                                <td>
                                    @if (array_key_exists('calculation_accepted', $frame))
                                        {{ $frame['calculation_accepted'] ? 'Yes' : 'No' }}
                                    @else
                                        Not recorded
                                    @endif
                                </td>
                                <td>{{ $frame['rejection_reason'] ?? '-' }}</td>
                                <td>{{ $frame['landmark_x_px'] !== null ? number_format((float) $frame['landmark_x_px'], 2) : '-' }}</td>
                                <td>{{ $frame['landmark_y_px'] !== null ? number_format((float) $frame['landmark_y_px'], 2) : '-' }}</td>
                                <td>{{ $frame['landmark_visibility'] !== null ? number_format((float) $frame['landmark_visibility'], 3) : '-' }}</td>
                            </tr>
                        @endforeach
                    </tbody>
                </table>
            </div>
        </details>
    </div>
@endif
