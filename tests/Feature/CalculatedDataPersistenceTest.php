<?php

namespace Tests\Feature;

use App\Models\CalculatedData;
use App\Models\ManualData;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class CalculatedDataPersistenceTest extends TestCase
{
    use RefreshDatabase;

    public function test_analysis_result_saves_to_the_existing_calcurated_data_table(): void
    {
        $user = User::factory()->create();
        $manual = new ManualData();
        $manual->user_id = $user->id;
        $manual->movie = 'movies/sprint.mp4';
        $manual->save();

        $result = new CalculatedData();
        $result->manual_id = $manual->id;
        $result->user_id = $user->id;
        $result->pixel_distance = 200;
        $result->scale_m_per_px = 0.025;
        $result->velocity_max = 3;
        $result->velocity_avg = 3;
        $result->save();

        $this->assertDatabaseHas('calcurated_data', [
            'id' => $result->id,
            'manual_id' => $manual->id,
            'user_id' => $user->id,
            'stride' => null,
            'ptich' => null,
        ]);
    }
}
