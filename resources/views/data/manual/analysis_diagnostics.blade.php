@extends('layouts.app')

@section('title', 'Pose Detection Diagnostics')

@section('content')
    <div class="container my-5">
        <h1 class="h2 text-primary mb-4">Pose Detection Diagnostics</h1>
        <div class="alert alert-warning" role="alert">
            {{ $error }} No velocity result was saved.
        </div>

        @include('data.manual.partials.frame_diagnostics')

        <div class="bg-white shadow rounded p-4">
            <h2 class="h5 text-secondary mb-3">Sprint Video</h2>
            <video class="w-100" src="{{ route('manual.video', $manual->id) }}" controls playsinline></video>
        </div>
    </div>
@endsection
