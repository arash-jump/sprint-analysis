@extends('layouts.app')

@section('title', 'Input Detailed Data')

@section('content')
    <div class="container">
        <div class="row w-75 bg-white shadow mx-auto my-5 rounded">
            <form action="{{route('manual.input_detail', $id)}}" class="w-75 mx-auto" enctype="multipart/form-data" method="post">
                @csrf
            <h1 class="h2 my-5 text-primary"><i class="fa-solid fa-database"></i> Input Detailed Data</h1>
                @if (session('error'))
                    <div class="alert alert-danger" role="alert">{{ session('error') }}</div>
                @endif
                <div class="mb-3">
                    <label for="calibration_distance">Calibration Distance (m)</label>
                    <input type="number" class="form-control" name="calibration_distance" id="calinration_distance" step="0.01">
                    @error('calibration_distance')
                        <p class="text-danger">{{$message}}</p>
                    @enderror
                </div>
                <div class="">
                    <label for="run_distance">Reference Run Distance (m)</label>
                    <input type="number" class="form-control" name="run_distance" id="run_distance" step="0.01">
                    <small class="form-text text-muted">For reference only; it does not change or limit the video-based estimate.</small>
                    @error('run_distance')
                        <p class="text-danger">{{$message}}</p>
                    @enderror
                </div>
                    <button type="submit" class="btn btn-primary w-50 my-5 mx-auto">Save</button>
            </form>
        </div>
    </div>
@endsection