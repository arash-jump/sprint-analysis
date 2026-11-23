<?php

namespace Tests\Feature;

use App\Models\CalculatedData;
use App\Models\ManualData;
use App\Models\User;
use App\Services\PoseAnalysisRunner;
use App\Services\PoseOverlayVideo;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Mockery;
use Tests\TestCase;

class CalculatedDataQualityGateTest extends TestCase
{
    use RefreshDatabase;

    public function test_zero_one_or_two_accepted_points_show_diagnostics_without_saving_metrics(): void
    {
        $user = User::factory()->create();
        $manuals = [];
        $results = [];
        foreach (range(0, 2) as $acceptedCount) {
            $manual = new ManualData();
            $manual->user_id = $user->id;
            $manual->movie = 'movies/sprint-'.$acceptedCount.'.mp4';
            $manual->calibration_distance = 10;
            $manual->calibration_point = '[{"x":0,"y":0},{"x":100,"y":0}]';
            $manual->run_distance = 10;
            $manual->save();
            $manuals[] = $manual;
            $results[] = $this->insufficientResult($acceptedCount);
        }

        $runner = Mockery::mock(PoseAnalysisRunner::class);
        $runner->shouldReceive('run')->times(3)->andReturn(...$results);
        $this->app->instance(PoseAnalysisRunner::class, $runner);
        $this->mock(PoseOverlayVideo::class)
            ->shouldReceive('generate')
            ->twice()
            ->andReturn(
                'pose-previews/55555555-5555-4555-8555-555555555555.mp4',
                'pose-previews/66666666-6666-4666-8666-666666666666.mp4'
            );

        $this->actingAs($user);
        foreach ($manuals as $acceptedCount => $manual) {
            $response = $this->get(route('calculated.analysis', $manual->id))
                ->assertOk()
                ->assertViewIs('data.manual.analysis_diagnostics')
                ->assertSee('No velocity result was saved.')
                ->assertDontSee('velocityChart');
            if ($acceptedCount === 0) {
                $response->assertSee('No detected poses are available');
                $this->assertNull($manual->fresh()->pose_preview_path);
            } else {
                $response->assertSee('Pose review video');
                $this->assertNotNull($manual->fresh()->pose_preview_path);
            }
        }

        $this->assertDatabaseCount('calcurated_data', 0);
        $this->assertSame(0, CalculatedData::count());
    }

    public function test_result_without_quality_pass_status_is_not_saved_as_success(): void
    {
        $user = User::factory()->create();
        $manual = new ManualData();
        $manual->user_id = $user->id;
        $manual->movie = 'movies/sprint.mp4';
        $manual->calibration_distance = 10;
        $manual->calibration_point = '[{"x":0,"y":0},{"x":100,"y":0}]';
        $manual->run_distance = 10;
        $manual->save();

        $runner = Mockery::mock(PoseAnalysisRunner::class);
        $runner->shouldReceive('run')->once()->andReturn([
            'velocity_max' => 5,
            'velocity_avg' => 4,
            'segment_speeds' => [],
        ]);
        $this->app->instance(PoseAnalysisRunner::class, $runner);

        $this->actingAs($user)
            ->get(route('calculated.analysis', $manual->id))
            ->assertRedirect()
            ->assertSessionHas('error', 'Analysis did not pass the detection quality check.');

        $this->assertDatabaseCount('calcurated_data', 0);
    }

    public function test_quality_checked_result_is_saved_and_rendered_normally(): void
    {
        $user = User::factory()->create();
        $manual = new ManualData();
        $manual->user_id = $user->id;
        $manual->movie = 'movies/sprint.mp4';
        $manual->calibration_distance = 10;
        $manual->calibration_point = '[{"x":0,"y":0},{"x":100,"y":0}]';
        $manual->run_distance = 10;
        $manual->measurement_start_frame = 2;
        $manual->measurement_end_frame = 4;
        $manual->analysis_roi = [
            'x' => 100,
            'y' => 50,
            'width' => 500,
            'height' => 200,
        ];
        $manual->save();

        $result = $this->successfulResult();
        $runner = Mockery::mock(PoseAnalysisRunner::class);
        $runner->shouldReceive('run')
            ->once()
            ->withArgs(function (array $payload): bool {
                return $payload['measurement_start_frame'] === 2
                    && $payload['measurement_end_frame'] === 4
                    && str_contains($payload['pose_landmarks_output_path'], 'pose-previews/tmp/')
                    && $payload['roi'] === [
                        'x' => 100,
                        'y' => 50,
                        'width' => 500,
                        'height' => 200,
                    ];
            })
            ->andReturn($result);
        $this->app->instance(PoseAnalysisRunner::class, $runner);
        $this->mock(PoseOverlayVideo::class)
            ->shouldReceive('generate')
            ->once()
            ->andReturn('pose-previews/77777777-7777-4777-8777-777777777777.mp4');

        $this->actingAs($user)
            ->get(route('calculated.analysis', $manual->id))
            ->assertOk()
            ->assertViewIs('data.manual.analysis_result')
            ->assertSee('Detection Quality Summary')
            ->assertSee('3.00 m/s')
            ->assertSee('Pose review video');

        $this->assertDatabaseHas('calcurated_data', [
            'manual_id' => $manual->id,
            'user_id' => $user->id,
        ]);
        $savedResult = json_decode(
            CalculatedData::query()->where('manual_id', $manual->id)->firstOrFail()->raw_result,
            true
        );
        $this->assertSame(2, $savedResult['measurement_interval']['start_frame']);
        $this->assertSame(4, $savedResult['measurement_interval']['end_frame']);
        $this->assertSame(100, $savedResult['roi']['x']);
        $this->assertTrue($savedResult['pose_preview_available']);
        $this->assertSame(
            'pose-previews/77777777-7777-4777-8777-777777777777.mp4',
            $savedResult['pose_preview_path']
        );
    }

    public function test_pose_video_generation_failure_does_not_fail_a_successful_analysis(): void
    {
        $user = User::factory()->create();
        $manual = new ManualData();
        $manual->user_id = $user->id;
        $manual->movie = 'movies/sprint.mp4';
        $manual->calibration_distance = 10;
        $manual->calibration_point = '[{"x":0,"y":0},{"x":100,"y":0}]';
        $manual->run_distance = 10;
        $manual->save();

        $runner = Mockery::mock(PoseAnalysisRunner::class);
        $runner->shouldReceive('run')->once()->andReturn($this->successfulResult());
        $this->app->instance(PoseAnalysisRunner::class, $runner);
        $this->mock(PoseOverlayVideo::class)
            ->shouldReceive('generate')
            ->once()
            ->andThrow(new \RuntimeException('simulated encoding failure'));

        $this->actingAs($user)
            ->get(route('calculated.analysis', $manual->id))
            ->assertOk()
            ->assertSee('3.00 m/s')
            ->assertSee('pose review video could not be generated')
            ->assertDontSee('Pose review video</h2>');

        $savedResult = CalculatedData::query()->where('manual_id', $manual->id)->firstOrFail();
        $this->assertNull(json_decode($savedResult->raw_result, true)['pose_preview_path']);
        $this->assertDatabaseHas('calcurated_data', ['id' => $savedResult->id]);
    }

    private function successfulResult(): array
    {
        return [
            'analysis_status' => 'quality_check_passed',
            'pixel_distance' => 100,
            'scale_m_per_px' => 0.1,
            'velocity_max' => 3,
            'velocity_avg' => 3,
            'estimated_distance_m' => 0.9,
            'analysis_duration_seconds' => 0.3,
            'segment_speeds' => [],
            'frame_count' => 3,
            'pose_detection_count' => 3,
            'pose_detection_rate' => 1,
            'accepted_point_count' => 3,
            'accepted_point_rate' => 1,
            'first_accepted_timestamp_seconds' => 0.1,
            'last_accepted_timestamp_seconds' => 0.3,
            'maximum_gap_between_accepted_points_seconds' => 0.1,
            'maximum_missing_interval_seconds' => 0,
            'missing_intervals' => [],
            'quality_checks' => [],
            'quality_thresholds' => [],
            'frame_diagnostics' => [[
                'frame_number' => 1,
                'timestamp_seconds' => 0.0,
                'pose_detected' => true,
                'landmark_x_px' => 10,
                'landmark_y_px' => 20,
                'landmark_visibility' => 0.9,
                'within_measurement_interval' => true,
                'calculation_accepted' => true,
                'rejection_reason' => null,
            ]],
            'landmark_used' => 'right_hip',
            'model_input_frame_count' => 4,
            'measurement_interval' => [
                'start_frame' => 2,
                'end_frame' => 4,
                'frame_count' => 3,
                'start_timestamp_seconds' => 0.1,
                'end_timestamp_seconds' => 0.3,
                'boundaries_inclusive' => true,
            ],
            'roi' => ['x' => 100, 'y' => 50, 'width' => 500, 'height' => 200],
        ];
    }

    private function insufficientResult(int $acceptedCount): array
    {
        $diagnostics = [];
        for ($index = 0; $index < 6; $index++) {
            $accepted = $index < $acceptedCount;
            $diagnostics[] = [
                'frame_number' => $index + 1,
                'timestamp_seconds' => $index * 0.1,
                'pose_detected' => $accepted,
                'landmark_x_px' => $accepted ? 10 : null,
                'landmark_y_px' => $accepted ? 20 : null,
                'landmark_visibility' => $accepted ? 0.9 : null,
                'calculation_accepted' => $accepted,
                'rejection_reason' => $accepted ? null : 'pose_not_detected',
            ];
        }

        return [
            'analysis_status' => 'detection_quality_insufficient',
            'error' => 'Pose detection quality is insufficient for a sprint measurement.',
            'frame_count' => 6,
            'pose_detection_count' => $acceptedCount,
            'pose_detection_rate' => $acceptedCount / 6,
            'accepted_point_count' => $acceptedCount,
            'accepted_point_rate' => $acceptedCount / 6,
            'first_accepted_timestamp_seconds' => $acceptedCount ? 0 : null,
            'last_accepted_timestamp_seconds' => $acceptedCount
                ? ($acceptedCount - 1) * 0.1
                : null,
            'maximum_gap_between_accepted_points_seconds' => null,
            'maximum_missing_interval_seconds' => 0.6,
            'missing_intervals' => [],
            'quality_thresholds' => [],
            'quality_checks' => [],
            'detection_count' => $acceptedCount,
            'landmark_used' => 'right_hip',
            'frame_diagnostics' => $diagnostics,
        ];
    }
}
