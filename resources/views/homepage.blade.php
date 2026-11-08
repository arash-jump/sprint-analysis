@extends('layouts.app')

@section('content')
    <section class="container py-5">
        <div class="row justify-content-center">
            <div class="col-lg-8 text-center py-5">
                <h1 class="display-4 fw-bold">Sprint Video Analysis</h1>
                <p class="lead text-secondary mt-3">
                    Upload a sprint video, set calibration points, and review estimated running speed.
                </p>
                <a class="btn btn-primary btn-lg mt-3" href="{{ route('manual.input') }}">
                    Start a video analysis
                </a>
                @guest
                    <p class="text-secondary mt-3 mb-0">Sign in or create an account to upload a video.</p>
                @endguest
            </div>
        </div>
    </section>
@endsection
