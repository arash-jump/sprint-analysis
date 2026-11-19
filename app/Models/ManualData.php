<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use App\Models\CalcuratedData;

class ManualData extends Model
{
    protected $casts = [
        'analysis_roi' => 'array',
    ];

    public function calcuratedData(){
        return $this->hasMany(CalcuratedData::class);
    }
}
