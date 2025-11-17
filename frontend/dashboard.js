// API Configuration
const API_BASE = 'http://localhost:8000/api';
const BACKEND_BASE = 'http://localhost:8000';
const FAILOVER_ORCHESTRATOR = 'http://localhost:8003';

// Check authentication
if (!localStorage.getItem('sreUser')) {
    window.location.href = 'login.html';
}

// Set logged in user
document.getElementById('logged-in-user').textContent = localStorage.getItem('sreUser') || 'ADMIN1';

// Initialize dashboard
document.addEventListener('DOMContentLoaded', () => {
    loadQuickStats();
    setInterval(loadQuickStats, 30000); // Refresh every 30 seconds
});

// Logout handler
function handleLogout() {
    localStorage.removeItem('sreUser');
    localStorage.removeItem('loginTime');
    window.location.href = 'login.html';
}

// Load quick stats for welcome screen
async function loadQuickStats() {
    try {
        const response = await fetch(`${BACKEND_BASE}/api/stats`);
        const data = await response.json();

        document.getElementById('quick-devices').textContent = formatNumber(data.total_devices || 0);
        document.getElementById('quick-users').textContent = data.active_users || 0;
        document.getElementById('quick-availability').textContent = (data.current_availability || 99.99999).toFixed(5) + '%';
    } catch (error) {
        console.error('Error loading quick stats:', error);
    }
}

// Show/Hide content sections
function showSection(sectionId) {
    // Hide all sections
    document.querySelectorAll('.content-section').forEach(section => {
        section.classList.remove('active');
    });

    // Deactivate all buttons
    document.querySelectorAll('.action-btn').forEach(btn => {
        btn.classList.remove('active');
    });

    // Show selected section
    document.getElementById(sectionId).classList.add('active');
}

// 1. Deployment Version
async function showDeploymentVersion() {
    showSection('content-version');
    document.getElementById('btn-version').classList.add('active');

    try {
        // Fetch real version from failover orchestrator
        const response = await fetch(`${FAILOVER_ORCHESTRATOR}/status`);
        const data = await response.json();

        const version = data.version || 'v1.0.0057_region1';
        document.getElementById('version-info').textContent = version;
    } catch (error) {
        console.error('Error loading version:', error);
        document.getElementById('version-info').textContent = 'Error loading version';
    }
}

// 2. Site Active Users
async function showActiveUsers() {
    showSection('content-users');
    document.getElementById('btn-users').classList.add('active');

    try {
        const response = await fetch(`${API_BASE}/users`);
        const data = await response.json();

        document.getElementById('concurrent-users').textContent = data.active_users || 0;
        document.getElementById('active-sessions').textContent = data.active_users || 0;
        document.getElementById('backend-connections').textContent = data.active_users || 0;

        // Show user list
        const userListDiv = document.getElementById('user-list');
        if (data.users && data.users.length > 0) {
            const listHTML = `
                <h3>Active User Sessions</h3>
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Username</th>
                            <th>Session ID</th>
                            <th>IP Address</th>
                            <th>Region</th>
                            <th>Login Time</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${data.users.slice(0, 10).map(user => `
                            <tr>
                                <td>${user.username}</td>
                                <td>${user.session_id || 'N/A'}</td>
                                <td>${user.ip_address || 'N/A'}</td>
                                <td>${user.region || 'N/A'}</td>
                                <td>${formatTimestamp(user.login_time)}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
            userListDiv.innerHTML = listHTML;
        } else {
            userListDiv.innerHTML = '<p>No active users</p>';
        }
    } catch (error) {
        console.error('Error loading users:', error);
        document.getElementById('concurrent-users').textContent = 'Error';
    }
}

// 3. Active Connected Devices
async function showActiveDevices() {
    showSection('content-devices');
    document.getElementById('btn-devices').classList.add('active');

    try {
        // Get total stats first
        const statsResponse = await fetch(`${BACKEND_BASE}/api/stats`);
        const stats = await statsResponse.json();

        // Get device list (show more devices)
        const response = await fetch(`${API_BASE}/devices?limit=100`);
        const devices = await response.json();

        document.getElementById('concurrent-devices').textContent = formatNumber(stats.total_devices || 0);
        document.getElementById('active-sensors').textContent = formatNumber(stats.total_devices || 0);
        document.getElementById('mqtt-rate').textContent = Math.floor((stats.total_devices || 0) / 100) || 0;

        // Show device list
        const deviceListDiv = document.getElementById('device-list');
        if (devices && devices.length > 0) {
            const listHTML = `
                <h3>Connected Devices (MQTT)</h3>
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Device ID</th>
                            <th>Type</th>
                            <th>Site</th>
                            <th>Status</th>
                            <th>Last Update</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${devices.map(device => `
                            <tr>
                                <td>${device.device_id}</td>
                                <td>${formatDeviceType(device.device_type)}</td>
                                <td>${device.site_id}</td>
                                <td>${getStatusBadge(device.metrics?.health_status || 'OK')}</td>
                                <td>${formatTimestamp(device.timestamp_utc)}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
            deviceListDiv.innerHTML = listHTML;
        } else {
            deviceListDiv.innerHTML = '<p>No active devices</p>';
        }
    } catch (error) {
        console.error('Error loading devices:', error);
        document.getElementById('concurrent-devices').textContent = 'Error';
    }
}

// 4. Site Image Intelligence
function showImageIntelligence() {
    showSection('content-intelligence');
    document.getElementById('btn-intelligence').classList.add('active');
}

async function generateWordCloud() {
    const deviceType = document.getElementById('wordcloud-device-filter').value;
    const container = document.getElementById('wordcloud-container');

    container.innerHTML = '<div class="loading">Analyzing images...</div>';

    try {
        const response = await fetch(`${API_BASE}/images/describe`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ device_type: deviceType })
        });

        const data = await response.json();

        if (data.keywords && data.keywords.length > 0) {
            // Create word cloud HTML
            const wordCloudHTML = `
                <div class="wordcloud-result">
                    <div class="wordcloud-summary">
                        <h4>Image Analysis Summary</h4>
                        <p>${data.description}</p>
                        <div class="wordcloud-stats">
                            <span><strong>Images Analyzed:</strong> ${data.image_count}</span>
                            <span><strong>Safety Compliance:</strong> ${data.avg_compliance}%</span>
                        </div>
                    </div>
                    <div class="wordcloud">
                        ${data.keywords.map((keyword, index) => {
                            // Calculate font size based on position (earlier = more frequent)
                            const fontSize = 2.5 - (index * 0.15);
                            const minSize = 0.8;
                            const finalSize = Math.max(fontSize, minSize);

                            // Vary colors for visual distinction
                            const colors = ['#667eea', '#764ba2', '#48bb78', '#4299e1', '#9f7aea', '#ed8936'];
                            const color = colors[index % colors.length];

                            // Add slight random rotation for cloud effect
                            const rotation = (Math.random() - 0.5) * 15; // -7.5 to 7.5 degrees

                            // Vary weight for emphasis
                            const weight = index < 3 ? 700 : 600;

                            return `<span class="word" style="font-size: ${finalSize}em; color: ${color}; transform: rotate(${rotation}deg); font-weight: ${weight};">${keyword}</span>`;
                        }).join('')}
                    </div>
                </div>
            `;
            container.innerHTML = wordCloudHTML;
        } else {
            container.innerHTML = `
                <div class="wordcloud-empty">
                    <p>${data.description}</p>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error generating word cloud:', error);
        container.innerHTML = '<div class="error">Error generating word cloud. Check console for details.</div>';
    }
}


async function runQuery(question) {
    const resultsDiv = document.getElementById('query-results');
    resultsDiv.innerHTML = '<div class="loading">Processing query...</div>';

    try {
        const response = await fetch(`${API_BASE}/query`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question })
        });

        const data = await response.json();

        resultsDiv.innerHTML = `
            <div class="query-result-box">
                <h3>Query Result</h3>
                <p><strong>Question:</strong> ${question}</p>
                <p><strong>Answer:</strong> ${data.answer || 'No answer available'}</p>
                ${data.sites ? `<p><strong>Sites:</strong> ${data.sites.join(', ')}</p>` : ''}
                ${data.count ? `<p><strong>Images Found:</strong> ${data.count}</p>` : ''}
                <p class="timestamp">Timestamp: ${new Date().toLocaleString()}</p>
            </div>
        `;
    } catch (error) {
        console.error('Error running query:', error);
        resultsDiv.innerHTML = '<div class="error">Error processing query. Check console for details.</div>';
    }
}

async function runCustomQuery() {
    const question = document.getElementById('custom-query-input').value.trim();
    if (!question) {
        alert('Please enter a query');
        return;
    }
    runQuery(question);
}

// 5. Simulate Failover
function showSimulateFailover() {
    showSection('content-failover');
    document.getElementById('btn-failover').classList.add('active');
    loadFailoverStatus();
    loadFailoverSummary();
}

async function loadFailoverStatus() {
    try {
        const response = await fetch(`${FAILOVER_ORCHESTRATOR}/status`);
        const data = await response.json();

        document.getElementById('failover-current-region').textContent = data.current_region;
        document.getElementById('failover-version').textContent = data.version;
        document.getElementById('failover-current-status').textContent = 'Live';
        document.getElementById('failover-current-status').className = 'timeline-value status-live';
    } catch (error) {
        console.error('Error loading failover status:', error);
    }
}

async function runFailoverTest(targetRegion) {
    const resultsDiv = document.getElementById('failover-results');
    const statusDiv = document.getElementById('failover-current-status');

    resultsDiv.innerHTML = '<div class="loading">Executing multi-region failover...</div>';
    statusDiv.textContent = 'Switching...';
    statusDiv.className = 'timeline-value status-switching';

    try {
        // Trigger real multi-region failover
        const response = await fetch(`${FAILOVER_ORCHESTRATOR}/failover/${targetRegion}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        const result = await response.json();

        // Refresh status from orchestrator to get updated version
        await loadFailoverStatus();

        // Update status
        setTimeout(() => {
            statusDiv.textContent = 'Live';
            statusDiv.className = 'timeline-value status-live';
        }, 1000);

        // Show detailed results
        const successIcon = result.success ? '✅' : '❌';
        const tier0Icon = result.tier0_compliant ? '✅' : '⚠️';

        resultsDiv.innerHTML = `
            <div class="failover-result ${result.success ? 'success' : 'failure'}">
                <h3>${successIcon} Multi-Region Failover Complete</h3>
                <p><strong>Source:</strong> ${result.source_region} → <strong>Target:</strong> ${result.target_region}</p>

                <div class="result-metrics">
                    <div class="metric">
                        <strong>Total Failover Time:</strong>
                        <span class="${result.tier0_compliant ? 'text-success' : 'text-error'}">
                            ${result.total_duration_seconds.toFixed(3)}s
                        </span>
                    </div>
                    <div class="metric">
                        <strong>Tier-0 Compliant:</strong>
                        ${tier0Icon} ${result.tier0_compliant ? 'YES (<5s)' : 'NO (≥5s)'}
                    </div>
                    <div class="metric">
                        <strong>SLA Target:</strong> ${result.sla_target}
                    </div>
                </div>

                <h4>Failover Steps:</h4>
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Step</th>
                            <th>Action</th>
                            <th>Duration (ms)</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${result.steps.map(step => `
                            <tr>
                                <td>${step.step}</td>
                                <td>${step.action}</td>
                                <td>${step.duration_ms.toFixed(2)}</td>
                                <td><span class="badge badge-ok">${step.status}</span></td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>

                <p class="timestamp">Completed: ${result.end_time}</p>
            </div>
        `;

        loadFailoverSummary();

    } catch (error) {
        console.error('Error running failover:', error);
        resultsDiv.innerHTML = '<div class="error">Failover failed. Check console for details.</div>';
        statusDiv.textContent = 'Live';
        statusDiv.className = 'timeline-value status-live';
    }
}

async function loadFailoverSummary() {
    try {
        const response = await fetch(`${FAILOVER_ORCHESTRATOR}/metrics`);
        const data = await response.json();

        const summaryDiv = document.getElementById('failover-summary-data');

        if (data.total_failovers === 0) {
            summaryDiv.innerHTML = '<p>No failovers executed yet. Click a region button below to test multi-region failover.</p>';
            return;
        }

        summaryDiv.innerHTML = `
            <div class="summary-grid">
                <div class="summary-item">
                    <span class="summary-label">Total Failovers:</span>
                    <span class="summary-value">${data.total_failovers}</span>
                </div>
                <div class="summary-item">
                    <span class="summary-label">Successful:</span>
                    <span class="summary-value text-success">${data.successful_failovers}</span>
                </div>
                <div class="summary-item">
                    <span class="summary-label">Failed:</span>
                    <span class="summary-value text-error">${data.failed_failovers}</span>
                </div>
                <div class="summary-item">
                    <span class="summary-label">Avg Failover Time:</span>
                    <span class="summary-value">${data.avg_failover_time_seconds.toFixed(3)}s</span>
                </div>
                <div class="summary-item">
                    <span class="summary-label">Tier-0 Compliance:</span>
                    <span class="summary-value ${data.tier0_compliance_rate >= 100 ? 'text-success' : 'text-error'}">
                        ${data.tier0_compliance_rate.toFixed(1)}%
                    </span>
                </div>
            </div>
        `;
    } catch (error) {
        console.error('Error loading failover summary:', error);
    }
}

// Simulate High Traffic
function simulateHighTraffic() {
    alert('Simulating high user traffic...\nThis would increase the active user count and test system scalability.');
}

// Utility Functions
function formatNumber(num) {
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toString();
}

function formatDeviceType(type) {
    const types = {
        'turbine': 'Turbine',
        'thermal_engine': 'Thermal Engine',
        'electrical_rotor': 'Electrical Rotor',
        'connected_device': 'O&G Connected Device'
    };
    return types[type] || type;
}

function formatTimestamp(timestamp) {
    if (!timestamp) return 'N/A';
    try {
        const date = new Date(timestamp);
        return date.toLocaleString();
    } catch {
        return timestamp;
    }
}

function getStatusBadge(state) {
    const badges = {
        'OK': '<span class="badge badge-ok">OK</span>',
        'WARN': '<span class="badge badge-warn">WARN</span>',
        'CRITICAL': '<span class="badge badge-critical">CRITICAL</span>'
    };
    return badges[state] || `<span class="badge">${state}</span>`;
}
