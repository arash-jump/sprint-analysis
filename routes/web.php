<?php

use Illuminate\Support\Facades\Route;
use App\Http\Controllers\HomeController;
use App\Http\Controllers\ManualDataController;
use App\Http\Controllers\CalculatedDataController;
use Laravel\Socialite\Facades\Socialite;


Auth::routes();
        Route::get('/',[HomeController::class, 'homepage'])->name('homepage');
            Route::group(['middleware' => 'auth'], function(){
                Route::get('/dashboard', [App\Http\Controllers\HomeController::class, 'index'])->name('home');
            
                //Manual
                Route::group(['prefix' => 'manual', 'as' => 'manual.'], function(){
                    Route::get('/input', [ManualDataController::class, 'input'])->name('input');
                    Route::post('/save', [ManualDataController::class, 'save'])->name('save');
                    Route::get('/{id}/calibration', [ManualDataController::class, 'calibration'])->name('calibration');
                    Route::get('/{id}/video', [ManualDataController::class, 'video'])->name('video');
                    Route::post('/{id}/add/point',[ManualDataController::class, 'add_point'])->name('add_point');
                    Route::get('/{id}/detail', [ManualDataController::class, 'detail'])->name('detail');
                    Route::post('/{id}/input/detail', [ManualDataController::class, 'input_detail'])->name('input_detail');
                });
            
                //Calcurated
                Route::group(['prefix' => 'calculated', 'as' => 'calculated.'], function(){
                    Route::get('/{id}/analysis', [CalculatedDataController::class, 'analysis'])->name('analysis');
                });
            });
