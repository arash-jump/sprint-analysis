<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use App\Models\ManualData;
use App\Services\PoseOverlayVideo;

class CalculatedData extends Model
{
    protected $table = 'calcurated_data';

    protected static function booted(): void
    {
        static::deleting(function (self $calculated): void {
            app(PoseOverlayVideo::class)->deleteFromResult($calculated->raw_result);
        });
    }

    public function manualData(){
        return $this->belongsTo(ManualData::class);
    }
}
