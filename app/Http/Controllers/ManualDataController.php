<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\Storage;
use RuntimeException;
use Symfony\Component\HttpFoundation\BinaryFileResponse;
use App\Models\ManualData;
use App\Services\VideoTranscoder;
use App\Services\VideoFrameTimeline;
use App\Services\PoseOverlayVideo;

class ManualDataController extends Controller
{
    
    private $manual;
    private const LOCAL_STORAGE_FOLDER = 'movies';

    public function __construct(ManualData $manual){
        $this->manual = $manual;
    }

    public function input(){
        return view('data.manual.input');
    }

    public function save(Request $request, VideoTranscoder $videoTranscoder){
        $request->validate([
            'movie' => 'required|mimes:mp4,mov,avi,wmv,flv,hevc|max:80000',
        ]);
       
        $manual = new ManualData();
        $manual->user_id = Auth::id();

        $manual->movie = $videoTranscoder->transcode($request->file('movie'));

        $manual->save();
        return redirect()->route('manual.calibration', $manual->id);
    }

    public function calibration($id){
        $manual = $this->findOwnedManual($id);

        return view('data.manual.calibration', compact('manual'));
    }

    public function video($id)
    {
        $manual = $this->findOwnedManual($id);
        $disk = Storage::disk('local');

        abort_unless($disk->exists($manual->movie), 404);

        return response()->file($disk->path($manual->movie));
    }

    public function posePreview($id, PoseOverlayVideo $poseOverlayVideo): BinaryFileResponse
    {
        $manual = $this->findOwnedManual($id);
        $path = $manual->pose_preview_path;
        abort_unless(is_string($path), 404);
        $filePath = $poseOverlayVideo->filePath($path);
        abort_unless($filePath !== null, 404);

        return response()->file($filePath, [
            'Content-Type' => 'video/mp4',
            'Cache-Control' => 'private, no-store',
        ]);
    }

    public function add_point(Request $request, $id){
        $request->validate([
            'calibration_point' => 'required|json',
        ]);

        $manual = $this->findOwnedManual($id);

        $manual->calibration_point = $request->calibration_point;
        $manual->save();

        return redirect()->route('manual.detail', $manual->id);
    }

    public function detail($id){
        $manual = $this->findOwnedManual($id);

        return view('data.manual.input_detail', compact('manual'));
    }

    public function frameTimestamps($id, VideoFrameTimeline $timeline)
    {
        $manual = $this->findOwnedManual($id);
        try {
            $timestamps = $timeline->read(
                Storage::disk('local')->path($manual->movie),
                config('services.ffprobe.binary', 'ffprobe')
            );
        } catch (RuntimeException $exception) {
            return response()->json(['error' => $exception->getMessage()], 503);
        }

        return response()->json([
            'timestamps_seconds' => $timestamps,
            'frame_count' => count($timestamps),
        ]);
    }

    public function input_detail(
        Request $request,
        $id,
        VideoFrameTimeline $timeline
    ){
        $validated = $request->validate([
            'calibration_distance' => 'required|numeric|gt:0',
            'run_distance' => 'required|numeric|gt:0',
            'measurement_start_frame' => 'nullable|integer|min:1',
            'measurement_end_frame' => 'nullable|integer|min:1',
            'roi_enabled' => 'nullable|boolean',
            'roi_x' => 'nullable|integer|min:0',
            'roi_y' => 'nullable|integer|min:0',
            'roi_width' => 'nullable|integer|min:1',
            'roi_height' => 'nullable|integer|min:1',
        ]);
        $manual = $this->findOwnedManual($id);
        try {
            $timestamps = $timeline->read(
                Storage::disk('local')->path($manual->movie),
                config('services.ffprobe.binary', 'ffprobe')
            );
        } catch (RuntimeException $exception) {
            return back()->with('error', $exception->getMessage())->withInput();
        }
        $startFrame = (int) ($validated['measurement_start_frame'] ?? 1);
        $endFrame = (int) ($validated['measurement_end_frame'] ?? count($timestamps));

        if (
            $startFrame > $endFrame
            || $endFrame > count($timestamps)
        ) {
            return back()->withErrors([
                'measurement_start_frame' => 'Choose an inclusive frame range within the video.',
                'measurement_end_frame' => 'Choose an inclusive frame range within the video.',
            ])->withInput();
        }

        $roi = null;
        if ($request->boolean('roi_enabled')) {
            foreach (['roi_x', 'roi_y', 'roi_width', 'roi_height'] as $field) {
                if (! array_key_exists($field, $validated)) {
                    return back()->withErrors([
                        $field => 'Draw a valid ROI on the video or turn ROI off.',
                    ])->withInput();
                }
            }
            $roi = [
                'x' => (int) $validated['roi_x'],
                'y' => (int) $validated['roi_y'],
                'width' => (int) $validated['roi_width'],
                'height' => (int) $validated['roi_height'],
            ];
        }

        $manual->calibration_distance = $request->calibration_distance;
        $manual->run_distance = $request->run_distance;
        $manual->measurement_start_frame = $startFrame;
        $manual->measurement_end_frame = $endFrame;
        $manual->analysis_roi = $roi;
        
        $manual->save();

        return redirect()->route('calculated.analysis',compact('id'));
    }

    private function findOwnedManual(string $id): ManualData
    {
        return $this->manual
            ->where('user_id', Auth::id())
            ->findOrFail($id);
    }
}
