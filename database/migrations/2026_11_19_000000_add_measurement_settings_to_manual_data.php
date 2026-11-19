<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('manual_data', function (Blueprint $table) {
            $table->unsignedInteger('measurement_start_frame')->nullable();
            $table->unsignedInteger('measurement_end_frame')->nullable();
            $table->json('analysis_roi')->nullable();
        });
    }

    public function down(): void
    {
        Schema::table('manual_data', function (Blueprint $table) {
            $table->dropColumn([
                'measurement_start_frame',
                'measurement_end_frame',
                'analysis_roi',
            ]);
        });
    }
};
