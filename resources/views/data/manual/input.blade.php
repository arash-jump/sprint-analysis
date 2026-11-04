@extends('layouts.app')

@section('title', 'Input Movie')

@section('content')
    <div class="container">
        <div class="row w-75 bg-white shadow mx-auto my-5 rounded">
            <form action="{{route('manual.save')}}" class="w-75 mx-auto" enctype="multipart/form-data" method="post">
                @csrf
            <h1 class="h2 my-5 text-primary"><i class="fa-solid fa-film"></i> Input Movie</h1>
                <div class="mb-3">
                    <label for="movie">Movie</label>
                    <input type="file" class="form-control" name="movie" id="movie" required autofocus>
                    @error('movie')
                        <p class="text-danger">{{$message}}</p>
                    @enderror
                </div> 
                    <button type="submit" class="btn btn-primary w-50 my-5 mx-auto">Save</button>
            </form>
        </div>
    </div>
@endsection