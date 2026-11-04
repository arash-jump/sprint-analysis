<?php

namespace Tests\Feature;

use App\Models\ManualData;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\Route;
use Illuminate\Support\Facades\Storage;
use Tests\TestCase;

class ManualDataAuthorizationTest extends TestCase
{
    use RefreshDatabase;

    public function test_users_cannot_access_another_users_manual_data(): void
    {
        $owner = User::factory()->create();
        $manual = $this->createManualData($owner);

        $this->actingAs(User::factory()->create());

        $this->get(route('manual.calibration', $manual->id))->assertNotFound();
        $this->get(route('manual.video', $manual->id))->assertNotFound();
        $this->get(route('manual.detail', $manual->id))->assertNotFound();
        $this->post(route('manual.add_point', $manual->id), [
            'calibration_point' => '[]',
        ])->assertNotFound();
        $this->post(route('manual.input_detail', $manual->id), [
            'fps' => 30,
            'calibration_distance' => 10,
            'run_distance' => 100,
        ])->assertNotFound();
        $this->get(route('calculated.analysis', $manual->id))->assertNotFound();

        $this->assertDatabaseMissing('manual_data', [
            'id' => $manual->id,
            'calibration_point' => '[]',
        ]);
    }

    public function test_manual_upload_route_does_not_accept_a_client_supplied_owner_id(): void
    {
        $this->actingAs(User::factory()->create());

        $this->assertSame([], Route::getRoutes()->getByName('manual.save')->parameterNames());
        $this->get(route('manual.input'))
            ->assertOk()
            ->assertSee('action="' . route('manual.save') . '"', false);
        $this->post('/manual/999/save')->assertNotFound();
    }

    public function test_owner_can_stream_a_video_from_private_storage(): void
    {
        Storage::fake('local');
        $owner = User::factory()->create();
        $manual = $this->createManualData($owner);
        Storage::disk('local')->put($manual->movie, 'private video content');

        $this->actingAs($owner)
            ->get(route('manual.video', $manual->id))
            ->assertOk();
    }

    public function test_video_upload_saves_a_private_file_before_measurements_are_entered(): void
    {
        Storage::fake('local');
        Storage::fake('public');
        $user = User::factory()->create();

        $this->actingAs($user)
            ->post(route('manual.save'), [
                'movie' => UploadedFile::fake()->create('sprint.mp4', 100, 'video/mp4'),
            ])
            ->assertRedirect();

        $manual = ManualData::query()->where('user_id', $user->id)->firstOrFail();

        Storage::disk('local')->assertExists($manual->movie);
        Storage::disk('public')->assertMissing($manual->movie);
        $this->assertNull($manual->calibration_distance);
        $this->assertNull($manual->run_distance);
    }

    private function createManualData(User $owner): ManualData
    {
        $manual = new ManualData();
        $manual->user_id = $owner->id;
        $manual->movie = 'sprint.mp4';
        $manual->calibration_distance = 10;
        $manual->run_distance = 100;
        $manual->save();

        return $manual;
    }
}
