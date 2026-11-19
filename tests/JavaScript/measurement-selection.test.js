import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const script = readFileSync(
    fileURLToPath(new URL('../../public/js/measurement-selection.js', import.meta.url)),
    'utf8',
);

function createPage() {
    const listeners = new Map();
    const elements = new Map();
    const canvasListeners = {};
    const context = {
        clearRect() {},
        fillRect() {},
        strokeRect() {},
    };

    function element(id, extra = {}) {
        const eventListeners = {};
        const value = {
            id,
            value: '',
            textContent: '',
            checked: false,
            disabled: false,
            classList: {
                toggle() {},
                add() {},
                remove() {},
            },
            addEventListener(event, callback) {
                eventListeners[event] = callback;
            },
            getBoundingClientRect() {
                return { left: 0, top: 0, width: 320, height: 180 };
            },
            ...extra,
        };
        value.listeners = eventListeners;
        elements.set(id, value);
        return value;
    }

    const form = element('analysis-settings-form', {
        dataset: { timelineUrl: '/manual/1/frame-timestamps' },
    });
    const video = element('measurement-video', {
        currentTime: 0,
        readyState: 1,
        videoWidth: 640,
        videoHeight: 360,
    });
    const canvas = element('roi-canvas', {
        width: 0,
        height: 0,
        getContext: () => context,
        setPointerCapture() {},
    });
    canvas.addEventListener = (event, callback) => {
        canvasListeners[event] = callback;
    };
    [
        'timeline-status', 'current-frame', 'measurement_start_frame',
        'measurement_end_frame', 'roi_enabled', 'roi-coordinates',
        'roi_x', 'roi_y', 'roi_width', 'roi_height', 'start-frame-time',
        'end-frame-time', 'use-current-start', 'use-current-end', 'clear-roi',
        'submit-analysis',
    ].forEach((id) => element(id));
    elements.get('measurement_start_frame').value = '1';

    runInNewContext(script, {
        document: {
            getElementById: (id) => elements.get(id),
        },
        fetch: async () => ({
            ok: true,
            json: async () => ({
                timestamps_seconds: [0, 0.041, 0.133, 0.209],
                frame_count: 4,
            }),
        }),
        Number,
        Math,
        Array,
        Promise,
    });

    return { elements, video, canvas, canvasListeners, context };
}

test('maps current video time to 1-based VFR frame and its exact PTS', async () => {
    const page = createPage();
    await new Promise((resolve) => setImmediate(resolve));

    page.video.currentTime = 0.12;
    page.video.listeners.timeupdate();
    assert.equal(page.elements.get('current-frame').textContent, 'Frame 3 — 0.133000 s');

    page.elements.get('use-current-start').listeners.click();
    assert.equal(page.elements.get('measurement_start_frame').value, 3);
    assert.equal(page.elements.get('start-frame-time').textContent, 'PTS time: 0.133000 s');
    assert.equal(page.elements.get('measurement_end_frame').value, 4);
    assert.equal(page.elements.get('end-frame-time').textContent, 'PTS time: 0.209000 s');
    assert.equal(page.elements.get('submit-analysis').disabled, false);
});

test('draws an ROI in intrinsic video pixels and clears it when disabled', async () => {
    const page = createPage();
    await new Promise((resolve) => setImmediate(resolve));

    const roiEnabled = page.elements.get('roi_enabled');
    roiEnabled.checked = true;
    roiEnabled.listeners.change();
    page.canvasListeners.pointerdown({
        clientX: 10,
        clientY: 20,
        pointerId: 1,
    });
    page.canvasListeners.pointerup({
        clientX: 110,
        clientY: 80,
        pointerId: 1,
    });

    assert.equal(page.elements.get('roi_x').value, 20);
    assert.equal(page.elements.get('roi_y').value, 40);
    assert.equal(page.elements.get('roi_width').value, 200);
    assert.equal(page.elements.get('roi_height').value, 120);
    assert.match(page.elements.get('roi-coordinates').textContent, /x=20, y=40/);

    page.elements.get('clear-roi').listeners.click();
    assert.equal(page.elements.get('roi_x').value, '');
    assert.equal(page.elements.get('roi_enabled').checked, false);
});
