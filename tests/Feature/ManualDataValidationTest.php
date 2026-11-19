<?php

namespace Tests\Feature;

use App\Models\ManualData;
use App\Models\User;
use App\Services\VideoFrameTimeline;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class ManualDataValidationTest extends TestCase
{
    use RefreshDatabase;

    public function test_legacy_fps_value_is_preserved_but_ignored_when_saving_new_analysis_inputs(): void
    {
        $user = User::factory()->create();
        $manual = new ManualData();
        $manual->user_id = $user->id;
        $manual->movie = 'movies/sprint.mp4';
        $manual->fps = 24;
        $manual->save();
        $this->mock(VideoFrameTimeline::class)
            ->shouldReceive('read')
            ->once()
            ->andReturn([0.0, 0.041, 0.133]);

        $this->actingAs($user)
            ->post(route('manual.input_detail', $manual->id), [
                'fps' => 0,
                'calibration_distance' => 5,
                'run_distance' => 100,
            ])
            ->assertRedirect(route('calculated.analysis', ['id' => $manual->id]))
            ->assertSessionHasNoErrors();

        $this->assertDatabaseHas('manual_data', [
            'id' => $manual->id,
            'fps' => 24,
            'calibration_distance' => 5,
            'run_distance' => 100,
        ]);
    }

    public function test_non_positive_analysis_measurements_are_rejected(): void
    {
        $user = User::factory()->create();
        $manual = new ManualData();
        $manual->user_id = $user->id;
        $manual->movie = 'movies/sprint.mp4';
        $manual->calibration_distance = 10;
        $manual->run_distance = 100;
        $manual->save();

        $response = $this->actingAs($user)->from(route('manual.detail', $manual->id))
            ->post(route('manual.input_detail', $manual->id), [
                'fps' => 0,
                'calibration_distance' => -1,
                'run_distance' => 0,
            ]);

        $response->assertRedirect(route('manual.detail', $manual->id))
            ->assertSessionHasErrors(['calibration_distance', 'run_distance'])
            ->assertSessionDoesntHaveErrors(['fps']);

        $this->assertDatabaseHas('manual_data', [
            'id' => $manual->id,
            'calibration_distance' => 10,
            'run_distance' => 100,
        ]);
    }

    public function test_default_interval_is_the_full_timestamped_video_and_roi_is_saved_as_pixels(): void
    {
        $user = User::factory()->create();
        $manual = new ManualData();
        $manual->user_id = $user->id;
        $manual->movie = 'movies/sprint.mp4';
        $manual->save();

        $this->mock(VideoFrameTimeline::class)
            ->shouldReceive('read')
            ->once()
            ->andReturn([0.0, 0.043, 0.12, 0.31]);

        $this->actingAs($user)
            ->post(route('manual.input_detail', $manual->id), [
                'calibration_distance' => 10,
                'run_distance' => 100,
                'roi_enabled' => 1,
                'roi_x' => 120,
                'roi_y' => 45,
                'roi_width' => 500,
                'roi_height' => 200,
            ])
            ->assertRedirect(route('calculated.analysis', ['id' => $manual->id]))
            ->assertSessionHasNoErrors();

        $manual->refresh();
        $this->assertSame(1, $manual->measurement_start_frame);
        $this->assertSame(4, $manual->measurement_end_frame);
        $this->assertSame([
            'x' => 120,
            'y' => 45,
            'width' => 500,
            'height' => 200,
        ], $manual->analysis_roi);
    }

    public function test_selected_range_stores_inclusive_one_based_frames_from_pts_selection(): void
    {
        $user = User::factory()->create();
        $manual = new ManualData();
        $manual->user_id = $user->id;
        $manual->movie = 'movies/sprint.mp4';
        $manual->save();
        $this->mock(VideoFrameTimeline::class)
            ->shouldReceive('read')
            ->once()
            ->andReturn([0.0, 0.041, 0.133, 0.209]);

        $this->actingAs($user)
            ->post(route('manual.input_detail', $manual->id), [
                'calibration_distance' => 10,
                'run_distance' => 100,
                'measurement_start_frame' => 2,
                'measurement_end_frame' => 3,
            ])
            ->assertRedirect(route('calculated.analysis', ['id' => $manual->id]))
            ->assertSessionHasNoErrors();

        $this->assertDatabaseHas('manual_data', [
            'id' => $manual->id,
            'measurement_start_frame' => 2,
            'measurement_end_frame' => 3,
        ]);
    }

    public function test_reversed_or_out_of_video_frame_ranges_are_rejected(): void
    {
        $user = User::factory()->create();
        $manual = new ManualData();
        $manual->user_id = $user->id;
        $manual->movie = 'movies/sprint.mp4';
        $manual->save();

        $this->mock(VideoFrameTimeline::class)
            ->shouldReceive('read')
            ->twice()
            ->andReturn([0.0, 0.043, 0.12, 0.31]);

        foreach ([
            ['measurement_start_frame' => 3, 'measurement_end_frame' => 2],
            ['measurement_start_frame' => 1, 'measurement_end_frame' => 5],
        ] as $range) {
            $this->actingAs($user)
                ->from(route('manual.detail', $manual->id))
                ->post(route('manual.input_detail', $manual->id), [
                    'calibration_distance' => 10,
                    'run_distance' => 100,
                    ...$range,
                ])
                ->assertRedirect(route('manual.detail', $manual->id))
                ->assertSessionHasErrors([
                    'measurement_start_frame',
                    'measurement_end_frame',
                ]);
        }

        $this->actingAs($user)
            ->from(route('manual.detail', $manual->id))
            ->post(route('manual.input_detail', $manual->id), [
                'calibration_distance' => 10,
                'run_distance' => 100,
                'measurement_start_frame' => 'NaN',
                'measurement_end_frame' => 3,
            ])
            ->assertRedirect(route('manual.detail', $manual->id))
            ->assertSessionHasErrors(['measurement_start_frame']);

        $manual->refresh();
        $this->assertNull($manual->measurement_start_frame);
        $this->assertNull($manual->measurement_end_frame);
    }
}
