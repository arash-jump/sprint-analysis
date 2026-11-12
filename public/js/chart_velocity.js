document.addEventListener('DOMContentLoaded', function() {
    const canvas = document.getElementById('velocityChart');
    if(!canvas) {
        return;
    }

    //const maxVelocity = parseFloat(canvas.dataset.max || 0);
    //const avgVelocity = parseFloat(canvas.dataset.avg || 0);

    const labels = JSON.parse(canvas.dataset.labels || '[]');
    const values = JSON.parse(canvas.dataset.values || '[]');
    

    const ctx = canvas.getContext('2d');

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Estimated horizontal speed by distance section (m/s)',
                data: values,
                borderColor: 'rgba(255, 99, 132, 0.6)',
            }]
        },
        options: {
            //plugins: {
            //    legend: {
            //        labels: {
            //            color: '#33333',
            //            font: {
            //                size: 14
            //            },
            //            boxWidth: 20,
            //            boxHeight: 20
            //        }
            //    },
            //    tooltip: {
            //        backgroundColor: 'rgba(225, 33, 33, 0.8)',
            //        titleColor: '#ffffff',
            //        bodyColor: '#ffffff',
            //        borderWidth: 1,
            //        padding: 10,
            //    }
            //},
            scales: {
                y: {
                    beginAtZero: true,
                    grid: {
                        display: false
                    }
                },
                x: {
                    grid: {
                        display: false
                    }
                }
            }
        }
    });
});