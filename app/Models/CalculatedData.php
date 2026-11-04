<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use App\Models\ManualData;

class CalculatedData extends Model
{
    public function manualData(){
        return $this->belongsTo(ManualData::class);
    }
}
