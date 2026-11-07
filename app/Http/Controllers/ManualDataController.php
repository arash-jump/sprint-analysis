<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\Storage;
use RuntimeException;
use App\Models\ManualData;

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

    public function save(Request $request){
        $request->validate([
            'movie' => 'required|mimes:mp4,mov,avi,wmv,flv,hevc|max:80000',
        ]);
       
        $manual = new ManualData();
        $manual->user_id = Auth::id();

        $manual->movie = $this->saveMovie($request->file('movie'));

        $manual->save();
        return redirect()->route('manual.calibration', $manual->id);
    }

    private function saveMovie(UploadedFile $movie): string
    {
        $path = $movie->store(self::LOCAL_STORAGE_FOLDER, 'local');

        if ($path === false) {
            throw new RuntimeException('Failed to store uploaded video.');
        }

        return $path;
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
        $this->findOwnedManual($id);

        return view('data.manual.input_detail', compact('id'));
    }

    public function input_detail(Request $request, $id){
        $request->validate([
            'fps' => 'required|numeric|gt:0',
            'calibration_distance' => 'required|numeric|gt:0',
            'run_distance' => 'required|numeric|gt:0',
        ]);
        $manual = $this->findOwnedManual($id);

        $manual->fps = $request->fps;
        $manual->calibration_distance = $request->calibration_distance;
        $manual->run_distance = $request->run_distance;
        
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
