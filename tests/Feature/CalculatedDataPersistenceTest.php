<?php

namespace Tests\Feature;

use App\Models\CalculatedData;
use App\Models\ManualData;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Storage;
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

    public function test_pose_preview_is_owner_scoped_and_deleted_with_its_result(): void
    {
        Storage::fake('local');
        $owner = User::factory()->create();
        $manual = new ManualData();
        $manual->user_id = $owner->id;
        $manual->movie = 'movies/sprint.mp4';
        $manual->save();
        $path = 'pose-previews/22222222-2222-4222-8222-222222222222.mp4';
        Storage::disk('local')->put($path, 'private preview content');

        $result = new CalculatedData();
        $result->manual_id = $manual->id;
        $result->user_id = $owner->id;
        $result->raw_result = json_encode(['pose_preview_path' => $path]);
        $result->save();

        $this->actingAs(User::factory()->create())
            ->get(route('calculated.pose_preview', $result->id))
            ->assertNotFound();

        $this->actingAs($owner)
            ->get(route('calculated.pose_preview', $result->id))
            ->assertOk()
            ->assertHeader('content-type', 'video/mp4');

        $result->delete();

        Storage::disk('local')->assertMissing($path);
    }

    public function test_manual_deletion_removes_its_result_and_quality_diagnostic_previews(): void
    {
        Storage::fake('local');
        $owner = User::factory()->create();
        $manual = new ManualData();
        $manual->user_id = $owner->id;
        $manual->movie = 'movies/sprint.mp4';
        $manual->pose_preview_path = 'pose-previews/33333333-3333-4333-8333-333333333333.mp4';
        $manual->save();
        $resultPath = 'pose-previews/44444444-4444-4444-8444-444444444444.mp4';
        Storage::disk('local')->put($manual->pose_preview_path, 'diagnostic preview');
        Storage::disk('local')->put($resultPath, 'calculated preview');

        $result = new CalculatedData();
        $result->manual_id = $manual->id;
        $result->user_id = $owner->id;
        $result->raw_result = json_encode(['pose_preview_path' => $resultPath]);
        $result->save();

        $manual->delete();

        Storage::disk('local')->assertMissing($manual->pose_preview_path);
        Storage::disk('local')->assertMissing($resultPath);
        $this->assertDatabaseMissing('calcurated_data', ['id' => $result->id]);
    }
}
