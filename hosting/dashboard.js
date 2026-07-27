// Initialize charts
const ctxLatency = document.getElementById('latencyChart').getContext('2d');
const ctxError = document.getElementById('errorChart').getContext('2d');

const latencyChart = new Chart(ctxLatency, {
    type: 'line',
    data: {
        labels: [],
        datasets: [{
            label: 'Latency (s)',
            data: [],
            borderColor: '#3b82f6',
            tension: 0.4
        }]
    },
    options: {
        responsive: true,
        scales: {
            y: { beginAtZero: true }
        }
    }
});

const errorChart = new Chart(ctxError, {
    type: 'doughnut',
    data: {
        labels: [],
        datasets: [{
            data: [],
            backgroundColor: ['#ef4444', '#f59e0b', '#3b82f6', '#10b981']
        }]
    }
});

// Wait for Firebase to initialize
setTimeout(() => {
    if (!window.db) {
        console.error("Firebase not initialized");
        return;
    }

    const q = window.query(
        window.collection(window.db, "METRICS"), 
        window.orderBy("timestamp", "desc"), 
        window.limit(50)
    );

    window.onSnapshot(q, (snapshot) => {
        let totalTime = 0;
        let successCount = 0;
        const rows = [];
        
        // Reset chart data
        latencyChart.data.labels = [];
        latencyChart.data.datasets[0].data = [];
        
        const errors = {};

        snapshot.forEach((doc) => {
            const data = doc.data();
            const time = data.timestamp ? data.timestamp.toDate().toLocaleTimeString() : 'N/A';
            
            // Add to table
            rows.push(`
                <tr>
                    <td>${time}</td>
                    <td>${data.module}</td>
                    <td>${data.function}</td>
                    <td class="${data.success ? 'status-ok' : 'status-fail'}">${data.success ? 'Success' : 'Failed'}</td>
                    <td>${data.duration_sec.toFixed(2)}s</td>
                </tr>
            `);

            // Stats
            totalTime += data.duration_sec;
            if(data.success) successCount++;
            else {
                errors[data.module] = (errors[data.module] || 0) + 1;
            }

            // Charts (populate in reverse so oldest is first on x-axis)
            latencyChart.data.labels.unshift(time);
            latencyChart.data.datasets[0].data.unshift(data.duration_sec);
        });

        // Update DOM
        const tbody = document.getElementById('metrics-table-body');
        tbody.innerHTML = rows.join('');
        
        const count = snapshot.size || 1;
        document.getElementById('avg-latency').textContent = (totalTime / count).toFixed(2) + 's';
        document.getElementById('success-rate').textContent = Math.round((successCount / count) * 100) + '%';
        
        if (successCount < count) {
            document.getElementById('system-status').className = 'badge error';
            document.getElementById('system-status').textContent = 'Degraded';
        } else {
            document.getElementById('system-status').className = 'badge ok';
            document.getElementById('system-status').textContent = 'Operational';
        }

        // Update Error Chart
        errorChart.data.labels = Object.keys(errors);
        errorChart.data.datasets[0].data = Object.values(errors);
        
        latencyChart.update();
        errorChart.update();
    });
}, 1000);
