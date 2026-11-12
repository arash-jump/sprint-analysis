<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\Storage;
use App\Models\CalculatedData;
use App\Models\ManualData;

class CalculatedDataController extends Controller
{
    private $calculated;

    public function __construct(CalculatedData $calculated){
        
        $this->calculated = $calculated;
    }

    public function analysis($id){
        $manual = ManualData::query()
            ->where('user_id', Auth::id())
            ->findOrFail($id);

        $payload = [
            'movie_path' => Storage::disk('local')->path($manual->movie),
            'ffprobe_binary' => config('services.ffprobe.binary', 'ffprobe'),
            'calibration_point' => $manual->calibration_point ? json_decode($manual->calibration_point, true): null,
            'calibration_distance' => $manual->calibration_distance,
        ];

        $json = json_encode($payload);

        $pythonScriptPath = base_path('python/calculate.py');

        $pythonBinary = base_path('venv/bin/python3');

        $command = escapeshellarg($pythonBinary) . " " . escapeshellarg($pythonScriptPath) . " " . escapeshellarg($json) . " 2>&1";

        $output = shell_exec($command);

        

        
        if($output === null){
            return back()->with('error', 'Failed to execute Python script.');
        }

        $lines = preg_split("/\r\n|\r|\n/", trim($output));
        $jsonLine = end($lines);   

        $result = json_decode($jsonLine, true);

        if(!is_array($result)){
            return back()->with('error', 'Invalid JSON returned from Python.');
        }

        if(isset($result['error'])){
            if (isset($result['frame_diagnostics']) && is_array($result['frame_diagnostics'])) {
                return view('data.manual.analysis_diagnostics', [
                    'manual' => $manual,
                    'error' => $result['error'],
                    'result' => $result,
                ]);
            }

            return back()->with('error', $result['error']);
        }

        foreach ([
            'pixel_distance',
            'scale_m_per_px',
            'velocity_max',
            'velocity_avg',
            'estimated_distance_m',
            'analysis_duration_seconds',
            'segment_speeds',
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
