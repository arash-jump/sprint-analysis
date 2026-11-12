@if (isset($result['frame_diagnostics']) && is_array($result['frame_diagnostics']))
    <div class="bg-white shadow rounded p-4 mb-5">
        <h2 class="h5 text-secondary mb-3">Pose Detection Diagnostics</h2>
        <p>
            Usable {{ ($result['landmark_used'] ?? 'right_hip') === 'left_hip' ? 'left-hip' : 'right-hip' }} detections in {{ $result['detection_count'] ?? 0 }}
            of {{ $result['frame_count'] ?? count($result['frame_diagnostics']) }} frames.
            {{ ($result['landmark_used'] ?? 'right_hip') === 'left_hip' ? 'Left' : 'Right' }}-hip visibility is shown for inspection only; it is not used to filter detections.
        </p>
        <details>
            <summary>Show per-frame timestamps and hip measurements</summary>
            <div class="table-responsive mt-3" style="max-height: 28rem; overflow-y: auto;">
                <table class="table table-sm table-striped">
                    <thead>
                        <tr>
                            <th>Frame</th>
                            <th>Time since first frame (s)</th>
                            <th>Pose detected</th>
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
