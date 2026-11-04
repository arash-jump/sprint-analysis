<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use App\Models\CalcuratedData;

class ManualData extends Model
{
    public function calcuratedData(){
        return $this->hasMany(CalcuratedData::class);
    }
}
