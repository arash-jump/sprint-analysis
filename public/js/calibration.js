const video = document.getElementById('video');
const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');

let points = [];

canvas.addEventListener('click', function(e){
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const scaleX = 1920/canvas.width;
    const scaleY = 1080/canvas.height;

    const originalX = x * scaleX;
    const originalY = y * scaleY;
    points.push({x:originalX, y:originalY});

    ctx.beginPath();
    ctx.arc(x,y,5,0,Math.PI * 2);
    ctx.fillStyle = "red";
    ctx.fill();
});

function clearPoints() {
    points = [];
    ctx.clearRect(0,0, canvas.width,canvas.height);
}
function submitPoints(){
    document.getElementById('calibration_point').value = JSON.stringify(points);
}