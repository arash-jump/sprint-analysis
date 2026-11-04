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
        Schema::create('calcurated_data', function (Blueprint $t) {
            $t->id();
            $t->unsignedBigInteger('manual_id');
            $t->unsignedBigInteger('user_id');
            $t->decimal('velocity',5,2);
            $t->decimal('stride',5,2);
            $t->decimal('ptich',5,2);
            $t->timestamps();

            $t->foreign('manual_id')->references('id')->on('manual_data')->cascadeOnDelete();
            $t->foreign('user_id')->references('id')->on('users')->cascadeOnDelete();
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('calcurated_data');
    }
};
