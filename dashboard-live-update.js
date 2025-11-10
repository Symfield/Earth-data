// Add this JavaScript to your earth-dashboard.html file
// This will fetch live data from earth_data.json and update the dashboard

async function loadLiveEarthData() {
    try {
        console.log('Fetching live Earth data...');
        
        // Fetch the live data with cache-busting timestamp
        const response = await fetch('./earth_data.json?' + Date.now());
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const liveData = await response.json();
        console.log('Live Earth data loaded:', liveData);
        
        // Update dashboard with live data
        updateDashboardWithLiveData(liveData);
        
        return liveData;
        
    } catch (error) {
        console.log('Live data not available, using static data:', error);
        // Fallback to existing static data
        return null;
    }
}

function updateDashboardWithLiveData(data) {
    // Update timestamps
    if (data.last_updated) {
        const updateTime = new Date(data.last_updated);
        const elements = document.querySelectorAll('[data-live="timestamp"]');
        elements.forEach(el => {
            el.textContent = updateTime.toLocaleString();
        });
        
        // Update specific timestamp displays
        const lastUpdateEl = document.getElementById('last-update');
        if (lastUpdateEl) {
            lastUpdateEl.textContent = `Last Data Update: ${updateTime.toUTCString()}`;
        }
    }
    
    // Update Field Coherence Index
    if (data.field_coherence_index !== undefined) {
        const fciElements = document.querySelectorAll('[data-live="fci"]');
        fciElements.forEach(el => {
            el.textContent = data.field_coherence_index.toFixed(3);
        });
    }
    
    // Update Metric Tensor values
    if (data.metric_tensor) {
        const aEl = document.querySelector('[data-live="metric-a"]');
        const bEl = document.querySelector('[data-live="metric-b"]');  
        const cEl = document.querySelector('[data-live="metric-c"]');
        
        if (aEl) aEl.textContent = data.metric_tensor.a.toFixed(4);
        if (bEl) bEl.textContent = data.metric_tensor.b.toFixed(4);
        if (cEl) cEl.textContent = data.metric_tensor.c.toFixed(4);
    }
    
    // Update Bias Vector
    if (data.bias_vector && Array.isArray(data.bias_vector)) {
        const biasEl = document.querySelector('[data-live="bias-vector"]');
        if (biasEl) {
            biasEl.textContent = `[${data.bias_vector.map(v => v.toFixed(3)).join(', ')}]`;
        }
    }
    
    // Update Status
    const statusEl = document.querySelector('[data-live="status"]');
    if (statusEl) {
        statusEl.textContent = data.status || 'live';
        statusEl.className = data.status === 'live' ? 'status-live' : 'status-static';
    }
    
    // Update dashboard render time
    const renderEl = document.getElementById('dashboard-render');
    if (renderEl) {
        renderEl.textContent = `Dashboard Render: ${new Date().toLocaleString()}`;
    }
    
    console.log('Dashboard updated with live data');
}

// Auto-refresh function
function startAutoRefresh(intervalMinutes = 30) {
    // Refresh every 30 minutes
    setInterval(() => {
        console.log('Auto-refreshing Earth data...');
        loadLiveEarthData();
    }, intervalMinutes * 60 * 1000);
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', function() {
    console.log('Phase-Coherent Earth Dashboard initializing...');
    
    // Load live data immediately
    loadLiveEarthData();
    
    // Start auto-refresh
    startAutoRefresh(30); // Refresh every 30 minutes
    
    console.log('Live data monitoring activated');
});

// Manual refresh button
function refreshEarthData() {
    loadLiveEarthData();
}

// Add CSS for status indicators
const style = document.createElement('style');
style.textContent = `
    .status-live {
        color: #00ff00;
        font-weight: bold;
    }
    .status-static {
        color: #ff9900;
        font-weight: bold;
    }
    [data-live] {
        transition: color 0.3s ease;
    }
`;
document.head.appendChild(style);
