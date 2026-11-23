@if (!empty($posePreviewUrl))
    <div class="bg-white shadow rounded p-4 mb-5">
        <h2 class="h5 text-secondary mb-2">Pose review video</h2>
        <p class="text-muted">
            Visual review only. The overlay uses landmarks from this analysis and does not guarantee measurement accuracy.
        </p>
        <video class="w-100" src="{{ $posePreviewUrl }}" controls playsinline preload="metadata"></video>
    </div>
@elseif (!empty($posePreviewError))
    <div class="alert alert-warning" role="status">{{ $posePreviewError }}</div>
@endif
