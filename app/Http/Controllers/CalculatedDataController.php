<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\Storage;
use App\Models\CalculatedData;
use App\Models\ManualData;
use App\Services\PoseAnalysisRunner;

class CalculatedDataController extends Controller
{
    private $calculated;

    public function __construct(CalculatedData $calculated){
        
        $this->calculated = $calculated;
    }

    public function analysis($id, PoseAnalysisRunner $analysisRunner){
        $manual = ManualData::query()
            ->where('user_id', Auth::id())
            ->findOrFail($id);

        $payload = [
            'movie_path' => Storage::disk('local')->path($manual->movie),
            'ffprobe_binary' => config('services.ffprobe.binary', 'ffprobe'),
            'calibration_point' => $manual->calibration_point ? json_decode($manual->calibration_point, true): null,
            'calibration_distance' => $manual->calibration_distance,
        ];

        try {
            $result = $analysisRunner->run($payload);
        } catch (\RuntimeException $exception) {
            return back()->with('error', $exception->getMessage());
        }

        if(isset($result['error'])){
            if (
                ($result['analysis_status'] ?? null) === 'detection_quality_insufficient'
                && isset($result['frame_diagnostics'])
                && is_array($result['frame_diagnostics'])
            ) {
                return view('data.manual.analysis_diagnostics', [
                    'manual' => $manual,
                    'error' => $result['error'],
                    'result' => $result,
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
        ] as $key) {
            if (!array_key_exists($key, $result)) {
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

        $calculated = $this->calculated;

        return view('data.manual.analysis_result', [ 'manual' => $manual, 
                                                     'result' => $result,
                                                     'calculated' => $calculated]);
    }
}
