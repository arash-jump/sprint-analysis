const form = document.getElementById('analysis-settings-form');
const video = document.getElementById('measurement-video');
const canvas = document.getElementById('roi-canvas');

if (form && video && canvas) {
    const context = canvas.getContext('2d');
    const timelineStatus = document.getElementById('timeline-status');
    const currentFrame = document.getElementById('current-frame');
    const startFrame = document.getElementById('measurement_start_frame');
    const endFrame = document.getElementById('measurement_end_frame');
    const roiEnabled = document.getElementById('roi_enabled');
    const roiCoordinates = document.getElementById('roi-coordinates');
    const roiFields = ['roi_x', 'roi_y', 'roi_width', 'roi_height']
        .map((id) => document.getElementById(id));

    let timestamps = [];
    let currentFrameNumber = null;
    let drawingStart = null;
    let drawingRect = null;

    function findNearestFrame(time) {
        let low = 0;
        let high = timestamps.length - 1;
        while (low < high) {
            const middle = Math.floor((low + high) / 2);
            if (timestamps[middle] < time) {
                low = middle + 1;
            } else {
                high = middle;
            }
        }

        if (low > 0 && Math.abs(timestamps[low - 1] - time) <= Math.abs(timestamps[low] - time)) {
            return low - 1;
        }
        return low;
    }

    function timestampLabel(frameNumber) {
        if (!Number.isInteger(frameNumber) || frameNumber < 1 || frameNumber > timestamps.length) {
            return null;
        }
        return timestamps[frameNumber - 1];
    }

    function updateSelectedFrameLabels() {
        const startTime = timestampLabel(Number(startFrame.value));
        const endTime = timestampLabel(Number(endFrame.value));
        document.getElementById('start-frame-time').textContent =
            startTime === null ? 'Select a frame within the video.' : `PTS time: ${startTime.toFixed(6)} s`;
        document.getElementById('end-frame-time').textContent =
            endTime === null ? 'Select a frame within the video.' : `PTS time: ${endTime.toFixed(6)} s`;
    }

    function videoPoint(event) {
        const rect = canvas.getBoundingClientRect();
        if (!rect.width || !rect.height || !video.videoWidth || !video.videoHeight) {
            return null;
        }
        return {
            x: (event.clientX - rect.left) * canvas.width / rect.width,
            y: (event.clientY - rect.top) * canvas.height / rect.height,
        };
    }

    function drawRoi(rect) {
        context.clearRect(0, 0, canvas.width, canvas.height);
        if (!rect) {
            return;
        }
        context.fillStyle = 'rgba(255, 193, 7, 0.14)';
        context.strokeStyle = '#ffc107';
        context.lineWidth = Math.max(2, canvas.width / 800);
        context.fillRect(rect.x, rect.y, rect.width, rect.height);
        context.strokeRect(rect.x, rect.y, rect.width, rect.height);
    }

    function updateRoiSummary(rect) {
        if (!rect || rect.width < 1 || rect.height < 1) {
            roiCoordinates.textContent = 'No ROI selected (full frame).';
            roiFields.forEach((field) => { field.value = ''; });
            return;
        }
        const bounds = {
            x: Math.floor(rect.x),
            y: Math.floor(rect.y),
            width: Math.ceil(rect.x + rect.width) - Math.floor(rect.x),
            height: Math.ceil(rect.y + rect.height) - Math.floor(rect.y),
        };
        roiFields[0].value = bounds.x;
        roiFields[1].value = bounds.y;
        roiFields[2].value = bounds.width;
        roiFields[3].value = bounds.height;
        roiCoordinates.textContent =
            `Source pixels: x=${bounds.x}, y=${bounds.y}, width=${bounds.width}, height=${bounds.height}`;
    }

    function restoreRoi() {
        const [x, y, width, height] = roiFields.map((field) => Number(field.value));
        if ([x, y, width, height].every(Number.isFinite) && width > 0 && height > 0) {
            drawingRect = { x, y, width, height };
            drawRoi(drawingRect);
            updateRoiSummary(drawingRect);
        } else {
            drawingRect = null;
            drawRoi(null);
            updateRoiSummary(null);
        }
    }

    function syncCanvas() {
        if (!video.videoWidth || !video.videoHeight) {
            return;
        }
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        restoreRoi();
    }

    function updateCurrentFrame() {
        if (!timestamps.length || !Number.isFinite(video.currentTime)) {
            return;
        }
        const index = findNearestFrame(video.currentTime);
        currentFrameNumber = index + 1;
        currentFrame.textContent =
            `Frame ${currentFrameNumber} — ${timestamps[index].toFixed(6)} s`;
    }

    function useCurrentFrame(input) {
        if (currentFrameNumber !== null) {
            input.value = currentFrameNumber;
            updateSelectedFrameLabels();
        }
    }

    document.getElementById('use-current-start').addEventListener('click', () => useCurrentFrame(startFrame));
    document.getElementById('use-current-end').addEventListener('click', () => useCurrentFrame(endFrame));
    startFrame.addEventListener('input', updateSelectedFrameLabels);
    endFrame.addEventListener('input', updateSelectedFrameLabels);

    roiEnabled.addEventListener('change', () => {
        canvas.classList.toggle('drawing', roiEnabled.checked);
        if (!roiEnabled.checked) {
            drawingStart = null;
        } else if (!drawingRect) {
            roiCoordinates.textContent = 'Drag on the video to draw a fixed ROI.';
        }
    });

    canvas.addEventListener('pointerdown', (event) => {
        if (!roiEnabled.checked) {
            return;
        }
        const point = videoPoint(event);
        if (!point) {
            return;
        }
        drawingStart = point;
        drawingRect = { x: point.x, y: point.y, width: 0, height: 0 };
        canvas.setPointerCapture(event.pointerId);
        drawRoi(drawingRect);
    });

    canvas.addEventListener('pointermove', (event) => {
        if (!drawingStart) {
            return;
        }
        const point = videoPoint(event);
        if (!point) {
            return;
        }
        drawingRect = {
            x: Math.min(drawingStart.x, point.x),
            y: Math.min(drawingStart.y, point.y),
            width: Math.abs(point.x - drawingStart.x),
            height: Math.abs(point.y - drawingStart.y),
        };
        drawRoi(drawingRect);
    });

    canvas.addEventListener('pointerup', (event) => {
        if (!drawingStart) {
            return;
        }
        const point = videoPoint(event);
        if (point) {
            drawingRect = {
                x: Math.min(drawingStart.x, point.x),
                y: Math.min(drawingStart.y, point.y),
                width: Math.abs(point.x - drawingStart.x),
                height: Math.abs(point.y - drawingStart.y),
            };
        }
        drawingStart = null;
        if (!drawingRect || drawingRect.width < 1 || drawingRect.height < 1) {
            drawingRect = null;
            drawRoi(null);
            updateRoiSummary(null);
            roiCoordinates.textContent = 'ROI must be a non-empty rectangle. Drag again.';
            return;
        }
        drawRoi(drawingRect);
        updateRoiSummary(drawingRect);
    });

    document.getElementById('clear-roi').addEventListener('click', () => {
        drawingStart = null;
        drawingRect = null;
        drawRoi(null);
        updateRoiSummary(null);
        roiEnabled.checked = false;
        canvas.classList.remove('drawing');
    });

    video.addEventListener('loadedmetadata', syncCanvas);
    video.addEventListener('timeupdate', updateCurrentFrame);
    video.addEventListener('seeked', updateCurrentFrame);
    if (video.readyState >= 1) {
        syncCanvas();
    }

    fetch(form.dataset.timelineUrl, { headers: { Accept: 'application/json' } })
        .then((response) => {
            if (!response.ok) {
                return response.json().then(
                    (result) => {
                        throw new Error(result.error || 'The timestamp timeline could not be loaded.');
                    },
                    () => {
                        throw new Error('The timestamp timeline could not be loaded.');
                    },
                );
            }
            return response.json();
        })
        .then((timeline) => {
            if (
                !Array.isArray(timeline.timestamps_seconds)
                || timeline.timestamps_seconds.length !== timeline.frame_count
                || timeline.timestamps_seconds.length === 0
                || timeline.timestamps_seconds.some((time, index, values) =>
                    !Number.isFinite(time) || (index > 0 && time <= values[index - 1]))
            ) {
                throw new Error('The video returned an invalid timestamp timeline.');
            }
            timestamps = timeline.timestamps_seconds;
            if (!endFrame.value) {
                endFrame.value = timestamps.length;
            }
            startFrame.max = timestamps.length;
            endFrame.max = timestamps.length;
            timelineStatus.textContent =
                `${timestamps.length} decoded frames. Frame numbers are 1-based; range boundaries are inclusive.`;
            document.getElementById('submit-analysis').disabled = false;
            updateCurrentFrame();
            updateSelectedFrameLabels();
        })
        .catch((error) => {
            timelineStatus.textContent = error.message;
            timelineStatus.classList.add('text-danger');
        });

    canvas.classList.toggle('drawing', roiEnabled.checked);
    updateSelectedFrameLabels();
}
