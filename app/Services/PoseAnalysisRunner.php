<?php

namespace App\Services;

use JsonException;
use RuntimeException;

class PoseAnalysisRunner
{
    public function run(array $payload): array
    {
        try {
            $json = json_encode($payload, JSON_THROW_ON_ERROR);
        } catch (JsonException $exception) {
            throw new RuntimeException('Analysis input could not be encoded.', 0, $exception);
        }

        $pythonBinary = base_path('venv/bin/python3');
        $pythonScriptPath = base_path('python/calculate.py');
        $command = escapeshellarg($pythonBinary)
            . ' '
            . escapeshellarg($pythonScriptPath)
            . ' '
            . escapeshellarg($json)
            . ' 2>&1';

        $output = shell_exec($command);
        if ($output === null) {
            throw new RuntimeException('Failed to execute Python script.');
        }

        $lines = preg_split("/\r\n|\r|\n/", trim($output));
        $result = json_decode(end($lines), true);
        if (! is_array($result)) {
            throw new RuntimeException('Invalid JSON returned from Python.');
        }

        return $result;
    }
}
