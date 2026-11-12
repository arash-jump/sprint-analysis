@extends('layouts.app')

@section('title', 'Input Calibration Point')

@section('content')
    <h1 class="h3 mx-auto my-3" style="width:960px;">Calibration</h1>
    <div class="wrapper">
            <video id="video" class="mx-auto" controls playsinline preload="metadata">
                <source src="{{route('manual.video', $manual->id)}}">
            </video>
            <canvas id="canvas" class="mx-auto" aria-hidden="true"></canvas>
            <script src="{{asset('js/calibration.js')}}"></script>
            <button type="button" class="btn btn-danger btn-sm " onclick="clearPoints()" id="clear">
                Clear All Points
            </button>
            <form action="{{route('manual.add_point', $manual->id)}}" method="post">
                @csrf
                <input type="hidden" name="calibration_point" id="calibration_point">
                <button type="submit" class="btn btn-primary btn-sm" onclick="submitPoints()" id="submit_point">
                Save All Points
            </button>
            </form>
    </div>
@endsection