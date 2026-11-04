<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('manual_data', function (Blueprint $table) {
            $table->decimal('calibration_distance', 5, 2)->nullable()->change();
            $table->decimal('run_distance', 5, 2)->nullable()->change();
        });
    }

    public function down(): void
    {
        Schema::table('manual_data', function (Blueprint $table) {
            $table->decimal('calibration_distance', 5, 2)->nullable(false)->change();
            $table->decimal('run_distance', 5, 2)->nullable(false)->change();
        });
    }
};
