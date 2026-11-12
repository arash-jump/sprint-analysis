<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use App\Models\ManualData;

class CalculatedData extends Model
{
    protected $table = 'calcurated_data';

    public function manualData(){
        return $this->belongsTo(ManualData::class);
    }
}
