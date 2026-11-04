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
        Schema::create('coaches', function (Blueprint $t) {
            $t->unsignedBigInteger('coach_id');
            $t->unsignedBigInteger('player_id');

            $t->foreign('coach_id')->references('id')->on('users')->cascadeOnDelete();
            $t->foreign('player_id')->references('id')->on('users')->cascadeOnDelete();

            $t->unique(['coach_id','player_id']);
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('coahes');
    }
};
