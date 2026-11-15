<?php

namespace Tests\Feature;

use App\Models\CalculatedData;
use App\Models\ManualData;
use Tests\TestCase;

class AnalysisResultViewTest extends TestCase
{
    public function test_legacy_analysis_results_still_render_without_inventing_distance_or_duration(): void
    {
        $manual = new ManualData();
        $manual->id = 5;
        $manual->run_distance = 100;

        $calculated = new CalculatedData();
        $calculated->pixel_distance = 500;
        $calculated->scale_m_per_px = 0.02;
        $calculated->velocity_avg = 3.5;
        $calculated->velocity_max = 4.2;

        $html = view('data.manual.analysis_result', [
            'manual' => $manual,
            'calculated' => $calculated,
            'result' => [
                'pixel_distance' => 500,
                'scale_m_per_px' => 0.02,
                'velocity_avg' => 3.5,
                'velocity_max' => 4.2,
                'segment_speeds' => [
                    ['start' => 0, 'end' => 10, 'avg_velocity' => 3.5],
                ],
            ],
        ])->render();

        $this->assertStringContainsString('Unavailable for this saved result', $html);
        $this->assertStringContainsString('3.50 m/s', $html);
        $this->assertStringContainsString('4.20 m/s', $html);
        $this->assertStringContainsString('0.00-10.00 m', $html);
    }

    public function test_frame_diagnostics_render_detection_state_and_landmark_values(): void
    {
        $manual = new ManualData();
        $manual->id = 5;
        $manual->run_distance = 100;

        $calculated = new CalculatedData();
        $calculated->pixel_distance = 500;
        $calculated->scale_m_per_px = 0.02;
        $calculated->velocity_avg = 3.5;
        $calculated->velocity_max = 4.2;

        $html = view('data.manual.analysis_result', [
            'manual' => $manual,
            'calculated' => $calculated,
            'result' => [
                'pixel_distance' => 500,
                'scale_m_per_px' => 0.02,
                'velocity_avg' => 3.5,
                'velocity_max' => 4.2,
                'detection_count' => 1,
                'pose_detection_count' => 1,
                'accepted_point_count' => 1,
                'frame_count' => 2,
                'landmark_used' => 'right_hip',
                'segment_speeds' => [],
                'frame_diagnostics' => [
                    [
                        'frame_number' => 1,
                        'timestamp_seconds' => 0.0,
                        'pose_detected' => true,
                        'calculation_accepted' => true,
                        'rejection_reason' => null,
                        'landmark_x_px' => 100,
                        'landmark_y_px' => 60,
                        'landmark_visibility' => 0.9,
                    ],
                    [
                        'frame_number' => 2,
                        'timestamp_seconds' => 0.033,
                        'pose_detected' => false,
                        'calculation_accepted' => false,
                        'rejection_reason' => 'pose_not_detected',
                        'landmark_x_px' => null,
                        'landmark_y_px' => null,
                        'landmark_visibility' => null,
                    ],
                ],
            ],
        ])->render();

        $this->assertStringContainsString('Pose Detection Diagnostics', $html);
        $this->assertStringContainsString('Pose detected in 1', $html);
        $this->assertStringContainsString('points were accepted for calculation.', $html);
        $this->assertStringContainsString('of 2 frames.', $html);
        $this->assertStringContainsString('100.00', $html);
        $this->assertStringContainsString('0.900', $html);
        $this->assertStringContainsString('0.033000', $html);
        $this->assertStringContainsString('Accepted', $html);
        $this->assertStringContainsString('Rejection reason', $html);
    }

    public function test_insufficient_pose_result_renders_diagnostics_without_velocity_chart(): void
    {
        $manual = new ManualData();
        $manual->id = 5;

        $html = view('data.manual.analysis_diagnostics', [
            'manual' => $manual,
            'error' => 'The video did not contain enough detectable poses.',
            'result' => [
                'analysis_status' => 'detection_quality_insufficient',
                'pose_detection_count' => 1,
                'pose_detection_rate' => 0.5,
                'accepted_point_count' => 1,
                'accepted_point_rate' => 0.5,
                'first_accepted_timestamp_seconds' => 0.033,
                'last_accepted_timestamp_seconds' => 0.033,
                'maximum_gap_between_accepted_points_seconds' => null,
                'maximum_missing_interval_seconds' => 0.033,
                'missing_intervals' => [],
                'quality_thresholds' => [],
                'quality_checks' => [],
                'frame_count' => 2,
                'detection_count' => 1,
                'landmark_used' => 'right_hip',
                'frame_diagnostics' => [
                    [
                        'frame_number' => 1,
                        'timestamp_seconds' => 0.0,
                        'pose_detected' => false,
                        'landmark_x_px' => null,
                        'landmark_y_px' => null,
                        'landmark_visibility' => null,
                    ],
                    [
                        'frame_number' => 2,
                        'timestamp_seconds' => 0.033,
                        'pose_detected' => true,
                        'landmark_x_px' => 120,
                        'landmark_y_px' => 70,
                        'landmark_visibility' => 0.999,
                    ],
                ],
            ],
        ])->render();

        $this->assertStringContainsString('No velocity result was saved.', $html);
        $this->assertStringContainsString('Pose Detection Diagnostics', $html);
        $this->assertStringContainsString('120.00', $html);
        $this->assertStringContainsString('0.999', $html);
        $this->assertStringNotContainsString('velocityChart', $html);
    }
}
