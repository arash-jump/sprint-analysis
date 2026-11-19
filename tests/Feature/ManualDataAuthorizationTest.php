<?php

namespace Tests\Feature;

use App\Models\ManualData;
use App\Models\User;
use App\Services\VideoTranscoder;
use App\Services\VideoFrameTimeline;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\Route;
use Illuminate\Support\Facades\Storage;
use Mockery\MockInterface;
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
        $this->get(route('manual.frame_timestamps', $manual->id))->assertNotFound();
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
            ->get(route('manual.calibration', $manual->id))
            ->assertOk()
            ->assertSee('<video id="video"', false)
            ->assertSee('controls playsinline preload="metadata"', false)
            ->assertSee(route('manual.video', $manual->id), false);

        $this->actingAs($owner)
            ->get(route('manual.video', $manual->id))
            ->assertOk();
    }

    public function test_only_the_owner_can_read_the_video_frame_timeline(): void
    {
        Storage::fake('local');
        $owner = User::factory()->create();
        $manual = $this->createManualData($owner);
        $timeline = $this->mock(VideoFrameTimeline::class);
        $timeline->shouldReceive('read')
            ->once()
            ->andReturn([0.0, 0.04, 0.12]);

        $this->actingAs($owner)
            ->get(route('manual.frame_timestamps', $manual->id))
            ->assertOk()
            ->assertJson([
                'timestamps_seconds' => [0.0, 0.04, 0.12],
                'frame_count' => 3,
            ]);

        $this->actingAs($owner)
            ->get(route('manual.detail', $manual->id))
            ->assertOk()
            ->assertViewIs('data.manual.input_detail')
            ->assertSee(route('manual.frame_timestamps', $manual->id), false)
            ->assertSee('Start frame (inclusive)')
            ->assertSee('End frame (inclusive)');
    }

    public function test_video_upload_saves_a_private_file_before_measurements_are_entered(): void
    {
        Storage::fake('local');
        Storage::fake('public');
        $user = User::factory()->create();
        Storage::disk('local')->put('movies/test.mp4', 'private video content');
        $this->mock(VideoTranscoder::class, function (MockInterface $mock): void {
            $mock->shouldReceive('transcode')
                ->once()
                ->andReturn('movies/test.mp4');
        });

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
