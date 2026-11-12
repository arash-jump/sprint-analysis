<?php

namespace App\Services;

use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Storage;
use Illuminate\Support\Str;
use Illuminate\Validation\ValidationException;
use Symfony\Component\Process\Exception\ProcessFailedException;
use Symfony\Component\Process\Exception\ProcessTimedOutException;
use Symfony\Component\Process\Process;
use RuntimeException;

class VideoTranscoder
{
    private const TEMPORARY_FOLDER = 'movies/tmp';
    private const OUTPUT_FOLDER = 'movies';

    public function transcode(UploadedFile $upload): string
    {
        $disk = Storage::disk('local');
        $id = (string) Str::uuid();
        $sourceName = $id . '.' . ($upload->guessExtension() ?: 'upload');
        $sourceRelativePath = self::TEMPORARY_FOLDER . '/' . $sourceName;
        $outputRelativePath = self::OUTPUT_FOLDER . '/' . $id . '.mp4';

        $storedPath = $upload->storeAs(self::TEMPORARY_FOLDER, $sourceName, 'local');
        if ($storedPath === false) {
            throw new RuntimeException('Failed to store uploaded video for conversion.');
        }

        $sourcePath = $disk->path($sourceRelativePath);
        $outputPath = $disk->path($outputRelativePath);
        $converted = false;

        try {
            $process = new Process([
                config('services.ffmpeg.binary', 'ffmpeg'),
                '-nostdin',
                '-hide_banner',
                '-loglevel',
                'error',
                '-y',
                '-i',
                $sourcePath,
                '-map',
                '0:v:0',
                '-map',
                '0:a?',
                '-c:v',
                'libx264',
                '-preset',
                'fast',
                '-crf',
                '23',
                '-pix_fmt',
                'yuv420p',
                '-tag:v',
                'avc1',
                '-c:a',
                'aac',
                '-fps_mode',
                'passthrough',
                '-movflags',
                '+faststart',
                $outputPath,
            ]);
            $process->setTimeout(600);
            $process->mustRun();

            if (! $disk->exists($outputRelativePath) || $disk->size($outputRelativePath) === 0) {
                Log::warning('FFmpeg completed without creating a converted video.', [
                    'output_path' => $outputRelativePath,
                    'output' => $process->getOutput(),
                    'error_output' => $process->getErrorOutput(),
                ]);

                throw ValidationException::withMessages([
                    'movie' => 'The video could not be converted. Check that FFmpeg is installed and try another video.',
                ]);
            }

            $converted = true;

            return $outputRelativePath;
        } catch (ProcessFailedException|ProcessTimedOutException $exception) {
            Log::warning('Uploaded video conversion failed.', [
                'exit_code' => $exception instanceof ProcessFailedException
                    ? $exception->getProcess()->getExitCode()
                    : null,
                'error' => $exception->getMessage(),
            ]);

            throw ValidationException::withMessages([
                'movie' => 'The video could not be converted. Check that FFmpeg is installed and try another video.',
            ]);
        } finally {
            $disk->delete($sourceRelativePath);
            if (! $converted) {
                $disk->delete($outputRelativePath);
            }
        }
    }
}
