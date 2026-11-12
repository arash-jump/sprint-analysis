import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const script = readFileSync(
    fileURLToPath(new URL('../../public/js/calibration.js', import.meta.url)),
    'utf8',
);

function createCalibrationPage({ videoWidth = 1280, videoHeight = 720, readyState = 1 } = {}) {
    const listeners = {};
    const drawnPoints = [];
    const video = {
        videoWidth,
        videoHeight,
        readyState,
        addEventListener: (event, handler) => {
            listeners[event] = handler;
        },
        getBoundingClientRect: () => video.rect,
        rect: { left: 100, top: 50, width: 960, height: 540 },
    };
    const canvas = {
        width: 960,
        height: 540,
        getContext: () => ({
            beginPath() {},
            arc: (x, y) => drawnPoints.push({ x, y }),
            fill() {},
            clearRect() {
                drawnPoints.length = 0;
            },
        }),
    };
    const hiddenInput = { value: '' };
    const wrapper = { style: {} };
    const window = {};
    const document = {
        getElementById: (id) => ({
            video,
            canvas,
            calibration_point: hiddenInput,
        }[id]),
        querySelector: () => wrapper,
    };

    runInNewContext(script, {
        document,
        window,
        HTMLMediaElement: { HAVE_METADATA: 1 },
    });

    return { video, canvas, hiddenInput, listeners, drawnPoints, wrapper, window };
}

test('maps clicks to video coordinates across display sizes', () => {
    const page = createCalibrationPage();

    page.listeners.click({ clientX: 580, clientY: 320 });
    page.video.rect = { left: 100, top: 50, width: 480, height: 270 };
    page.listeners.click({ clientX: 340, clientY: 185 });
    page.window.submitPoints();

    assert.deepEqual(JSON.parse(page.hiddenInput.value), [
        { x: 640, y: 360 },
        { x: 640, y: 360 },
    ]);
    assert.deepEqual(page.drawnPoints, [
        { x: 640, y: 360 },
        { x: 640, y: 360 },
    ]);
});

test('sets canvas resolution and display aspect ratio from video metadata', () => {
    const page = createCalibrationPage({ videoWidth: 0, videoHeight: 0, readyState: 0 });

    page.video.videoWidth = 3840;
    page.video.videoHeight = 2160;
    page.video.readyState = 1;
    page.listeners.loadedmetadata();

    assert.equal(page.canvas.width, 3840);
    assert.equal(page.canvas.height, 2160);
    assert.equal(page.wrapper.style.aspectRatio, '3840 / 2160');
});

test('ignores clicks outside the video and clears recorded points', () => {
    const page = createCalibrationPage();

    page.listeners.click({ clientX: 99, clientY: 320 });
    page.listeners.click({ clientX: 580, clientY: 320 });
    page.window.clearPoints();
    page.window.submitPoints();

    assert.deepEqual(page.drawnPoints, []);
    assert.deepEqual(JSON.parse(page.hiddenInput.value), []);
});
