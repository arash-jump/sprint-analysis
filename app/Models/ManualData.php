<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use App\Models\CalcuratedData;
use App\Models\CalculatedData;
use App\Services\PoseOverlayVideo;

class ManualData extends Model
{
    protected $casts = [
        'analysis_roi' => 'array',
    ];

    protected static function booted(): void
    {
        static::deleting(function (self $manual): void {
            $previewVideo = app(PoseOverlayVideo::class);
            $results = CalculatedData::query()
                ->where('manual_id', $manual->id)
                ->get(['raw_result']);
            foreach ($results as $result) {
                $previewVideo->deleteFromResult($result->raw_result);
            }
            if ($manual->pose_preview_path !== null) {
                $previewVideo->delete($manual->pose_preview_path);
            }
        });
    }

    public function calcuratedData(){
        return $this->hasMany(CalcuratedData::class);
    }
}
