<?php

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class HomepageNavigationTest extends TestCase
{
    use RefreshDatabase;

    public function test_homepage_links_to_video_input(): void
    {
        $this->get(route('homepage'))
            ->assertOk()
            ->assertSee('href="' . route('manual.input') . '"', false)
            ->assertSee('Start a video analysis');
    }

    public function test_guest_is_sent_to_login_before_video_input(): void
    {
        $this->get(route('manual.input'))
            ->assertRedirect(route('login'))
            ->assertSessionHas('url.intended', route('manual.input'));
    }

    public function test_dashboard_links_to_video_input(): void
    {
        $this->actingAs(User::factory()->create())
            ->get(route('home'))
            ->assertOk()
            ->assertSee('href="' . route('manual.input') . '"', false)
            ->assertSee('Upload a sprint video');
    }
}
