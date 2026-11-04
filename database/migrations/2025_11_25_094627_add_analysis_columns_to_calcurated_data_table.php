<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    /**
     * Run the migrations.
     */
    public function up(): void
    {
        Schema::table('calcurated_data', function (Blueprint $t) {
            $t->decimal('scale_m_per_px', 10, 6)->nullable()->after('user_id');
            $t->decimal('pixel_distance', 10, 3)->nullable()->after('scale_m_per_px');
            $t->dropColumn('velocity');
            $t->decimal('velocity_max', 10, 3)->nullable()->after('pixel_distance');
            $t->decimal('velocity_avg', 10, 3)->nullable()->after('velocity_max');

            $t->json('raw_result')->nullable()->after('velocity_avg');
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::table('calcurated_data', function (Blueprint $t) {
            $t->dropColumn(['scale_m_per_px', 'pixel_distance', 'velocity_avg', 'raw_result']);
        });
    }
};
