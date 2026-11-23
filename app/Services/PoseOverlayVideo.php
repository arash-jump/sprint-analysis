<?php

namespace App\Services;

use Illuminate\Support\Facades\Storage;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Str;
use RuntimeException;
use Symfony\Component\Process\Exception\ProcessStartFailedException;
use Symfony\Component\Process\Exception\ProcessTimedOutException;
use Symfony\Component\Process\Process;

class PoseOverlayVideo
{
    public function generate(string $moviePath, string $poseRecordsPath): string
    {
        $disk = Storage::disk('local');
        $disk->makeDirectory('pose-previews');
        $relativePath = 'pose-previews/'.Str::uuid().'.mp4';
        $outputPath = $disk->path($relativePath);
        $process = new Process([
            base_path('venv/bin/python3'),
            base_path('python/pose_overlay_video.py'),
            $moviePath,
            $poseRecordsPath,
            config('services.ffprobe.binary', 'ffprobe'),
            config('services.ffmpeg.binary', 'ffmpeg'),
            $outputPath,
        ]);
        $process->setTimeout(600);

        try {
            $process->run();
        } catch (ProcessStartFailedException | ProcessTimedOutException $exception) {
            $disk->delete($relativePath);
            Log::warning('Pose review process failed.', [
                'stage' => $exception instanceof ProcessTimedOutException ? 'timeout' : 'start',
                'exit_code' => $process->getExitCode(),
            ]);
            throw new RuntimeException(
                'The pose review video could not be generated.',
                0,
                $exception
            );
        }

        if (
            ! $process->isSuccessful()
            || ! $disk->exists($relativePath)
            || $disk->size($relativePath) === 0
        ) {
            Log::warning('Pose review process failed.', [
                'stage' => $process->isSuccessful() ? 'output_file' : 'process',
                'exit_code' => $process->getExitCode(),
                'stderr_category' => self::stderrCategory($process->getErrorOutput()),
            ]);
            $disk->delete($relativePath);
            throw new RuntimeException(
                'The pose review video could not be generated.'
            );
        }

        return $relativePath;
    }

    private static function stderrCategory(string $stderr): string
    {
        foreach ([
            'ffprobe_start' => ['FFprobe could not be started'],
            'ffmpeg_missing' => ['FFmpeg executable could not be found'],
            'ffmpeg_permission' => ['FFmpeg executable permission denied'],
            'render_io_error' => ['The pose review video could not be generated.'],
            'python_module_missing' => ['ModuleNotFoundError', 'ImportError'],
            'executable_missing' => ['No such file or directory', 'not found'],
            'permission_denied' => ['Permission denied', 'Operation not permitted'],
            'unsupported_option' => ['Unrecognized option', 'Option not found'],
            'timeline_mismatch' => ['do not match the converted video timeline', 'timestamps'],
            'landmark_data' => ['Pose landmark data', 'No pose landmark data'],
            'video_decode' => ['could not be opened for rendering', 'no decodable frames', 'ended before all pose frames'],
            'ffmpeg_failure' => ['FFmpeg could not create'],
            'python_traceback' => ['Traceback (most recent call last)'],
        ] as $category => $messages) {
            foreach ($messages as $message) {
                if (stripos($stderr, $message) !== false) {
                    return $category;
                }
            }
        }

        return $stderr === '' ? 'empty' : 'other';
    }

    public function delete(string $relativePath): void
    {
        if (! preg_match('/\Apose-previews\/[0-9a-f-]{36}\.mp4\z/iD', $relativePath)) {
            throw new RuntimeException('Invalid pose review video path.');
        }

        $disk = Storage::disk('local');
        if ($disk->exists($relativePath) && ! $disk->delete($relativePath)) {
            throw new RuntimeException('The pose review video could not be deleted.');
        }
    }

    public function filePath(string $relativePath): ?string
    {
        if (! preg_match('/\Apose-previews\/[0-9a-f-]{36}\.mp4\z/iD', $relativePath)) {
            return null;
        }

        $disk = Storage::disk('local');
        return $disk->exists($relativePath) ? $disk->path($relativePath) : null;
    }

    public function deleteFromResult(?string $rawResult): void
    {
        if ($rawResult === null) {
            return;
        }

        $result = json_decode($rawResult, true);
        $relativePath = is_array($result)
            ? ($result['pose_preview_path'] ?? null)
            : null;

        if (is_string($relativePath)) {
            $this->delete($relativePath);
        }
    }
}
