<?php

namespace Tests\Feature;

use App\Models\ManualData;
use App\Models\User;
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
}
