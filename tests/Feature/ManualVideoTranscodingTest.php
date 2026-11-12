<?php

namespace Tests\Feature;

use App\Models\ManualData;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\Storage;
use Illuminate\Support\Str;
use Tests\TestCase;

class ManualVideoTranscodingTest extends TestCase
{
    use RefreshDatabase;

    private ?string $fakeFfmpegPath = null;

    protected function tearDown(): void
    {
        if ($this->fakeFfmpegPath !== null && file_exists($this->fakeFfmpegPath)) {
            unlink($this->fakeFfmpegPath);
        }

        parent::tearDown();
    }

    public function test_uploaded_video_is_saved_as_a_private_mp4(): void
    {
        Storage::fake('local');
        Storage::fake('public');
        config(['services.ffmpeg.binary' => $this->createFakeFfmpeg()]);
        $user = User::factory()->create();

        $response = $this->actingAs($user)
            ->post(route('manual.save'), [
                'movie' => UploadedFile::fake()->create('sprint.mov', 100, 'video/quicktime'),
            ]);
        $response->assertRedirect()->assertSessionHasNoErrors();

        $manual = ManualData::query()->where('user_id', $user->id)->firstOrFail();

        $this->assertSame('mp4', pathinfo($manual->movie, PATHINFO_EXTENSION));
        Storage::disk('local')->assertExists($manual->movie);
        $this->assertCount(1, Storage::disk('local')->allFiles('movies'));
        $this->assertSame([], Storage::disk('public')->allFiles());
    }

    public function test_upload_shows_an_error_when_ffmpeg_cannot_start(): void
    {
        Storage::fake('local');
        config(['services.ffmpeg.binary' => sys_get_temp_dir() . '/missing-ffmpeg-' . Str::uuid()]);
        $user = User::factory()->create();

        $this->actingAs($user)
            ->from(route('manual.input'))
            ->post(route('manual.save'), [
                'movie' => UploadedFile::fake()->create('sprint.mov', 100, 'video/quicktime'),
            ])
            ->assertRedirect(route('manual.input'))
            ->assertSessionHasErrors('movie');

        $this->assertDatabaseCount('manual_data', 0);
        $this->assertSame([], Storage::disk('local')->allFiles());
    }

    private function createFakeFfmpeg(): string
    {
        $this->fakeFfmpegPath = sys_get_temp_dir() . '/fake-ffmpeg-' . Str::uuid();
        $script = <<<'SH'
#!/bin/sh
output=
has_input=0
has_video_codec=0
has_audio_codec=0
has_timestamp_passthrough=0
previous=
for argument do
    case "$argument" in
        libx264) has_video_codec=1 ;;
        aac) has_audio_codec=1 ;;
        passthrough)
            if [ "$previous" = "-fps_mode" ]; then
                has_timestamp_passthrough=1
            fi
            ;;
    esac
    if [ "$previous" = "-i" ]; then
        has_input=1
    fi
    previous=$argument
    output=$argument
done
[ "$has_input" -eq 1 ] && [ "$has_video_codec" -eq 1 ] && [ "$has_audio_codec" -eq 1 ] && [ "$has_timestamp_passthrough" -eq 1 ] || exit 2
mkdir -p "$(dirname "$output")"
printf 'converted video' > "$output"
SH;

        file_put_contents($this->fakeFfmpegPath, $script);
        chmod($this->fakeFfmpegPath, 0700);

        return $this->fakeFfmpegPath;
    }
}
