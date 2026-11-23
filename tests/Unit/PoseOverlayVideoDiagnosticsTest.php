<?php

namespace Tests\Unit;

use App\Services\PoseOverlayVideo;
use PHPUnit\Framework\TestCase;
use ReflectionMethod;

class PoseOverlayVideoDiagnosticsTest extends TestCase
{
    public function test_stderr_is_reduced_to_a_safe_category(): void
    {
        $classify = new ReflectionMethod(PoseOverlayVideo::class, 'stderrCategory');
        $this->assertSame('unsupported_option', $classify->invoke(null, "Unrecognized option 'private-value'"));
        $this->assertSame('permission_denied', $classify->invoke(null, 'Permission denied: /private/path'));
        $this->assertSame('ffmpeg_failure', $classify->invoke(null, 'FFmpeg could not create the pose review video'));
        $this->assertSame('ffprobe_start', $classify->invoke(null, 'FFprobe could not be started. Install FFmpeg/FFprobe and try again.'));
        $this->assertSame('ffmpeg_missing', $classify->invoke(null, 'FFmpeg executable could not be found.'));
        $this->assertSame('ffmpeg_permission', $classify->invoke(null, 'FFmpeg executable permission denied.'));
        $this->assertSame('render_io_error', $classify->invoke(null, 'The pose review video could not be generated.'));
        $this->assertSame('python_module_missing', $classify->invoke(null, "ModuleNotFoundError: No module named 'private-value'"));
        $this->assertSame('python_traceback', $classify->invoke(null, 'Traceback (most recent call last): sensitive text'));
        $this->assertSame('other', $classify->invoke(null, 'unrecognized sensitive text'));
        $this->assertSame('empty', $classify->invoke(null, ''));
    }
}
