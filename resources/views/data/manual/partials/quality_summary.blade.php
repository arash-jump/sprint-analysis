@if (isset($result['analysis_status']))
    @php($qualityPassed = $result['analysis_status'] === 'quality_check_passed')
    <div class="alert {{ $qualityPassed ? 'alert-info' : 'alert-warning' }}" role="status">
        <strong>{{ $qualityPassed ? 'Detection quality check passed' : 'Detection quality is insufficient' }}</strong>
        <span>
            Passing this operational check does not guarantee measurement accuracy.
        </span>
    </div>
    <div class="bg-white shadow rounded p-4 mb-5">
        <h2 class="h5 text-secondary mb-3">Detection Quality Summary</h2>
        <ul>
            <li>Total frames: {{ $result['frame_count'] ?? 0 }}</li>
            <li>
                Pose detected: {{ $result['pose_detection_count'] ?? 0 }}
                ({{ number_format((float) ($result['pose_detection_rate'] ?? 0) * 100, 1) }}%)
            </li>
            <li>
                Right-hip points accepted for calculation: {{ $result['accepted_point_count'] ?? 0 }}
                ({{ number_format((float) ($result['accepted_point_rate'] ?? 0) * 100, 1) }}%)
            </li>
            <li>First accepted point: {{ isset($result['first_accepted_timestamp_seconds']) ? number_format((float) $result['first_accepted_timestamp_seconds'], 3).' s' : 'None' }}</li>
            <li>Last accepted point: {{ isset($result['last_accepted_timestamp_seconds']) ? number_format((float) $result['last_accepted_timestamp_seconds'], 3).' s' : 'None' }}</li>
            <li>Maximum time between accepted points: {{ isset($result['maximum_gap_between_accepted_points_seconds']) ? number_format((float) $result['maximum_gap_between_accepted_points_seconds'], 3).' s' : 'Unavailable' }}</li>
            <li>Longest missing interval: {{ number_format((float) ($result['maximum_missing_interval_seconds'] ?? 0), 3) }} s</li>
            @if (isset($result['quality_thresholds']['minimum_right_hip_visibility']))
                <li>Right-hip minimum visibility for acceptance: {{ number_format((float) $result['quality_thresholds']['minimum_right_hip_visibility'], 2) }}</li>
            @endif
        </ul>

        @if (!empty($result['quality_checks']))
            <h3 class="h6 text-secondary mt-4">Operational checks</h3>
            <ul>
                @foreach ($result['quality_checks'] as $name => $check)
                    <li>
                        {{ str_replace('_', ' ', ucfirst($name)) }}:
                        {{ $check['passed'] ? 'Pass' : 'Fail' }}
                        ({{ is_numeric($check['actual']) ? number_format((float) $check['actual'], 3) : 'Unavailable' }}
                        / {{ $check['threshold'] }})
                    </li>
                @endforeach
            </ul>
        @endif

        @if (!empty($result['missing_intervals']))
            <h3 class="h6 text-secondary mt-4">Intervals without accepted points, including video edges</h3>
            <div class="table-responsive">
                <table class="table table-sm table-striped">
                    <thead>
                        <tr>
                            <th>Frames</th>
                            <th>Start (s)</th>
                            <th>End (s)</th>
                            <th>Duration (s)</th>
                            <th>Duration estimated</th>
                            <th>Rejection reasons</th>
                        </tr>
                    </thead>
                    <tbody>
                        @foreach ($result['missing_intervals'] as $interval)
                            <tr>
                                <td>{{ $interval['first_frame_number'] }}-{{ $interval['last_frame_number'] }}</td>
                                <td>{{ number_format((float) $interval['start_seconds'], 3) }}</td>
                                <td>{{ number_format((float) $interval['end_seconds'], 3) }}</td>
                                <td>{{ number_format((float) $interval['duration_seconds'], 3) }}</td>
                                <td>{{ $interval['duration_estimated'] ? 'Yes (median frame interval)' : 'No' }}</td>
                                <td>
                                    @foreach ($interval['rejection_reasons'] as $reason => $count)
                                        {{ $reason }} ({{ $count }})@if (!$loop->last), @endif
                                    @endforeach
                                </td>
                            </tr>
                        @endforeach
                    </tbody>
                </table>
            </div>
        @endif
    </div>
@endif
