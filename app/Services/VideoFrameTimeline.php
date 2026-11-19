<?php

namespace App\Services;

use JsonException;
use RuntimeException;
use Symfony\Component\Process\Exception\ProcessStartFailedException;
use Symfony\Component\Process\Exception\ProcessTimedOutException;
use Symfony\Component\Process\Process;

class VideoFrameTimeline
{
    public function read(string $moviePath, string $ffprobeBinary): array
    {
        $process = new Process([
            base_path('venv/bin/python3'),
            base_path('python/video_timestamps.py'),
            $moviePath,
            $ffprobeBinary,
        ]);
        $process->setTimeout(600);
        try {
            $process->run();
        } catch (ProcessStartFailedException | ProcessTimedOutException $exception) {
            throw new RuntimeException(
                'Could not read the converted video timestamp timeline.',
                0,
                $exception
            );
        }

        if (! $process->isSuccessful()) {
            $detail = trim(preg_replace('/\s+/', ' ', $process->getErrorOutput()) ?? '');
            $detail = substr($detail, 0, 500);
            $reason = $detail === '' ? '' : ' Details: '.$detail;
            throw new RuntimeException(
                'Could not read frame timestamps from the converted video.'.$reason
            );
        }

        try {
            $result = json_decode(
                $process->getOutput(),
                true,
                512,
                JSON_THROW_ON_ERROR
            );
        } catch (JsonException $exception) {
            throw new RuntimeException(
                'The video timestamp command returned invalid data.',
                0,
                $exception
            );
        }

        if (! is_array($result)) {
            throw new RuntimeException('The video timestamp command returned invalid data.');
        }

        $timestamps = $result['timestamps_seconds'] ?? null;
        if (! is_array($timestamps) || $timestamps === []) {
            throw new RuntimeException('The video has no usable frame timestamps.');
        }

        $previous = null;
        foreach ($timestamps as $timestamp) {
            if (! is_int($timestamp) && ! is_float($timestamp)) {
                throw new RuntimeException('The video has invalid frame timestamps.');
            }
            if (
                ! is_finite((float) $timestamp)
                || ($previous !== null && $timestamp <= $previous)
            ) {
                throw new RuntimeException('The video has invalid frame timestamps.');
            }
            $previous = $timestamp;
        }

        return $timestamps;
    }
}
