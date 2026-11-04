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
        Schema::create('feedback', function (Blueprint $t) {
            $t->id();
            $t->unsignedBigInteger('coach_id');
            $t->unsignedBigInteger('player_id');
            $t->unsignedBigInteger('manual_id')->nullable();
            $t->text('comment');
            $t->timestamps();

            $t->foreign('coach_id')->references('id')->on('users')->cascadeOnDelete();
            $t->foreign('player_id')->references('id')->on('users')->cascadeOnDelete();
            $t->foreign('manual_id')->references('id')->on('manual_data')->cascadeOnDelete();
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('feedback');
    }
};
