const video = document.getElementById('video');
const canvas = document.getElementById('canvas');
const wrapper = document.querySelector('.wrapper');
const ctx = canvas.getContext('2d');

let points = [];

function mapDisplayPointToVideo(clientX, clientY, rect, videoWidth, videoHeight) {
    if (
        ![clientX, clientY, rect.left, rect.top, rect.width, rect.height, videoWidth, videoHeight]
            .every(Number.isFinite)
        || rect.width <= 0
        || rect.height <= 0
        || videoWidth <= 0
        || videoHeight <= 0
    ) {
        return null;
    }

    const displayX = clientX - rect.left;
    const displayY = clientY - rect.top;
    if (displayX < 0 || displayY < 0 || displayX > rect.width || displayY > rect.height) {
        return null;
    }

    return {
        x: displayX * videoWidth / rect.width,
        y: displayY * videoHeight / rect.height,
    };
}

function syncVideoDimensions() {
    if (!video.videoWidth || !video.videoHeight) {
        return;
    }

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    wrapper.style.aspectRatio = `${video.videoWidth} / ${video.videoHeight}`;
}

video.addEventListener('loadedmetadata', syncVideoDimensions);
if (video.readyState >= HTMLMediaElement.HAVE_METADATA) {
    syncVideoDimensions();
}

video.addEventListener('click', function(event) {
    const rect = video.getBoundingClientRect();
    const point = mapDisplayPointToVideo(
        event.clientX,
        event.clientY,
        rect,
        video.videoWidth,
        video.videoHeight,
    );

    if (!point) {
        return;
    }

    points.push(point);

    ctx.beginPath();
    ctx.arc(point.x, point.y, 5 * canvas.width / rect.width, 0, Math.PI * 2);
    ctx.fillStyle = "red";
    ctx.fill();
});

function clearPoints() {
    points = [];
    ctx.clearRect(0, 0, canvas.width, canvas.height);
}

function submitPoints() {
    document.getElementById('calibration_point').value = JSON.stringify(points);
}

window.clearPoints = clearPoints;
window.submitPoints = submitPoints;