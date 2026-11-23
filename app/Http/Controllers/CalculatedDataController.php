<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Storage;
use Illuminate\Support\Str;
use App\Models\CalculatedData;
use App\Models\ManualData;
use App\Services\PoseAnalysisRunner;
use App\Services\PoseOverlayVideo;
use Symfony\Component\HttpFoundation\BinaryFileResponse;

class CalculatedDataController extends Controller
{
    private $calculated;

    public function __construct(CalculatedData $calculated){
        
        $this->calculated = $calculated;
    }

    public function analysis(
        $id,
        PoseAnalysisRunner $analysisRunner,
        PoseOverlayVideo $poseOverlayVideo
    ) {
        $manual = ManualData::query()
            ->where('user_id', Auth::id())
            ->findOrFail($id);

        $disk = Storage::disk('local');
        if ($manual->pose_preview_path !== null) {
            $poseOverlayVideo->delete($manual->pose_preview_path);
            $manual->pose_preview_path = null;
            $manual->save();
        }

        $disk->makeDirectory('pose-previews/tmp');
        $poseRecordsRelativePath = 'pose-previews/tmp/'.Str::uuid().'.jsonl';
        $payload = [
            'movie_path' => $disk->path($manual->movie),
            'ffprobe_binary' => config('services.ffprobe.binary', 'ffprobe'),
            'calibration_point' => $manual->calibration_point ? json_decode($manual->calibration_point, true): null,
            'calibration_distance' => $manual->calibration_distance,
            'measurement_start_frame' => $manual->measurement_start_frame,
            'measurement_end_frame' => $manual->measurement_end_frame,
            'roi' => $manual->analysis_roi,
            'pose_landmarks_output_path' => $disk->path($poseRecordsRelativePath),
        ];

        try {
            try {
                $result = $analysisRunner->run($payload);
            } catch (\RuntimeException $exception) {
                return back()->with('error', $exception->getMessage());
            }

            if (isset($result['error'])) {
                if (
                    ($result['analysis_status'] ?? null) === 'detection_quality_insufficient'
                    && isset($result['frame_diagnostics'])
                    && is_array($result['frame_diagnostics'])
                ) {
                    $previewPath = $this->generatePosePreviewIfAvailable(
                        $manual,
                        $poseRecordsRelativePath,
                        $result,
                        $poseOverlayVideo
                    );
                    if ($previewPath !== null) {
                        $manual->pose_preview_path = $previewPath;
                        $manual->save();
                    }

                    return view('data.manual.analysis_diagnostics', [
                        'manual' => $manual,
                        'error' => $result['error'],
                        'result' => $result,
                        'posePreviewUrl' => $previewPath !== null
                            ? route('manual.pose_preview', $manual->id)
                            : null,
                        'posePreviewError' => $this->previewError($result, $previewPath),
                    ]);
                }

                return back()->with('error', $result['error']);
            }

            if (($result['analysis_status'] ?? null) !== 'quality_check_passed') {
                return back()->with('error', 'Analysis did not pass the detection quality check.');
            }

            foreach ([
                'pixel_distance',
                'scale_m_per_px',
                'velocity_max',
                'velocity_avg',
                'estimated_distance_m',
                'analysis_duration_seconds',
                'segment_speeds',
                'frame_count',
                'pose_detection_count',
                'pose_detection_rate',
                'accepted_point_count',
                'accepted_point_rate',
                'first_accepted_timestamp_seconds',
                'last_accepted_timestamp_seconds',
                'maximum_gap_between_accepted_points_seconds',
                'maximum_missing_interval_seconds',
                'missing_intervals',
                'quality_checks',
                'quality_thresholds',
                'frame_diagnostics',
                'measurement_interval',
                'roi',
            ] as $key) {
                if (! array_key_exists($key, $result)) {
                    return back()->with('error', 'Incomplete analysis result returned from Python.');
                }
            }

            $this->calculated->pixel_distance = $result['pixel_distance'];
            $this->calculated->scale_m_per_px = $result['scale_m_per_px'];
            $this->calculated->velocity_max   = $result['velocity_max'];
            $this->calculated->velocity_avg   = $result['velocity_avg'];
            $this->calculated->manual_id      = $id;
            $this->calculated->user_id        = Auth::user()->id;

            $this->calculated->raw_result = json_encode($result);

            $this->calculated->save();

            $previewPath = $this->generatePosePreviewIfAvailable(
                $manual,
                $poseRecordsRelativePath,
                $result,
                $poseOverlayVideo
            );
            $result['pose_preview_path'] = $previewPath;
            $result['pose_preview_available'] = $previewPath !== null;
            $result['pose_preview_error'] = $this->previewError($result, $previewPath);
            $this->calculated->raw_result = json_encode($result);
            $this->calculated->save();

            return view('data.manual.analysis_result', [
                'manual' => $manual,
                'result' => $result,
                'calculated' => $this->calculated,
                'posePreviewUrl' => $previewPath !== null
                    ? route('calculated.pose_preview', $this->calculated->id)
                    : null,
                'posePreviewError' => $result['pose_preview_error'],
            ]);
        } finally {
            $disk->delete($poseRecordsRelativePath);
        }
    }

    public function posePreview($id): BinaryFileResponse
    {
        $calculated = CalculatedData::query()
            ->where('user_id', Auth::id())
            ->findOrFail($id);
        $manual = ManualData::query()
            ->where('user_id', Auth::id())
            ->findOrFail($calculated->manual_id);
        $result = json_decode($calculated->raw_result ?? '', true);
        $path = is_array($result) ? ($result['pose_preview_path'] ?? null) : null;
        abort_unless(is_string($path), 404);

        $disk = Storage::disk('local');
        abort_unless($disk->exists($path), 404);

        return response()->file($disk->path($path), [
            'Content-Type' => 'video/mp4',
            'Cache-Control' => 'private, no-store',
        ]);
    }

    private function generatePosePreviewIfAvailable(
        ManualData $manual,
        string $poseRecordsRelativePath,
        array $result,
        PoseOverlayVideo $poseOverlayVideo
    ): ?string {
        foreach ($result['frame_diagnostics'] ?? [] as $frame) {
            if (! empty($frame['pose_detected'])) {
                try {
                    return $poseOverlayVideo->generate(
                        Storage::disk('local')->path($manual->movie),
                        Storage::disk('local')->path($poseRecordsRelativePath)
                    );
                } catch (\RuntimeException $exception) {
                    Log::warning('Pose review video generation failed.', [
                        'manual_data_id' => $manual->id,
                        'error' => $exception->getMessage(),
                    ]);
                    return null;
                }
            }
        }

        return null;
    }

    private function previewError(array $result, ?string $previewPath): ?string
    {
        if ($previewPath !== null) {
            return null;
        }
        foreach ($result['frame_diagnostics'] ?? [] as $frame) {
            if (! empty($frame['pose_detected'])) {
                return 'The analysis completed, but the pose review video could not be generated.';
            }
        }

        return 'No detected poses are available to show in a review video.';
    }
}
