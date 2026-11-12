<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('calcurated_data', function (Blueprint $table) {
            $table->decimal('stride', 5, 2)->nullable()->change();
            $table->decimal('ptich', 5, 2)->nullable()->change();
        });
    }

    public function down(): void
    {
        Schema::table('calcurated_data', function (Blueprint $table) {
            $table->decimal('stride', 5, 2)->nullable(false)->change();
            $table->decimal('ptich', 5, 2)->nullable(false)->change();
        });
    }
};
