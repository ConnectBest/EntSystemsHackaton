// API Configuration
const API_BASE = 'http://localhost:8000/api';
const BACKEND_BASE = 'http://localhost:8000';

// Initialize dashboard on page load
document.addEventListener('DOMContentLoaded', () => {
    loadSystemStats();
    loadSites();
    loadFailoverStatus();
    setInterval(loadSystemStats, 30000); // Refresh every 30 seconds
    setInterval(loadFailoverStatus, 60000); // Refresh failover status every 60 seconds
});

// Tab Management
function openTab(tabName) {
    // Hide all tabs
    const tabs = document.getElementsByClassName('tab-content');
    for (let tab of tabs) {
        tab.classList.remove('active');
    }

    // Deactivate all buttons
    const buttons = document.getElementsByClassName('tab-button');
    for (let button of buttons) {
        button.classList.remove('active');
    }

    // Show selected tab
    document.getElementById(tabName).classList.add('active');
    event.target.classList.add('active');

    // Load tab-specific data
    switch(tabName) {
        case 'devices':
            loadDevices();
            break;
        case 'users':
            loadUsers();
            break;
        case 'logs':
            loadErrorLogs();
            break;
        case 'images':
            loadImages();
            break;
    }
}

// System Statistics
async function loadSystemStats() {
    try {
        const response = await fetch(`${BACKEND_BASE}/api/stats`);
        const data = await response.json();

        document.getElementById('system-status').textContent = `${data.current_availability}%`;
        document.getElementById('device-count').textContent = formatNumber(data.total_devices);
        document.getElementById('user-count').textContent = formatNumber(data.active_users);
        document.getElementById('site-count').textContent = data.total_sites;

    } catch (error) {
        console.error('Error loading system stats:', error);
        document.getElementById('system-status').textContent = 'Error';
    }
}

// Load Sites
async function loadSites() {
    try {
        const response = await fetch(`${API_BASE}/sites`);
        const sites = await response.json();

        const siteFilter = document.getElementById('device-site-filter');
        sites.forEach(site => {
            const option = document.createElement('option');
            option.value = site.site_id;
            option.textContent = `${site.site_id} - ${site.site_name}`;
            siteFilter.appendChild(option);
        });

    } catch (error) {
        console.error('Error loading sites:', error);
    }
}

// Device Telemetry
async function loadDevices() {
    const siteId = document.getElementById('device-site-filter').value;
    const deviceType = document.getElementById('device-type-filter').value;

    const deviceList = document.getElementById('device-list');
    const deviceStats = document.getElementById('device-stats');

    deviceList.innerHTML = '<div class="loading">Loading device data...</div>';

    try {
        // Load device count
        const countResponse = await fetch(`${API_BASE}/devices/count`);
        const counts = await countResponse.json();

        // Display stats
        deviceStats.innerHTML = '';
        const totalDevices = counts.reduce((sum, c) => sum + c.count, 0);

        const statBox = document.createElement('div');
        statBox.className = 'stat-box';
        statBox.innerHTML = `
            <h4>Total Devices</h4>
            <div class="value">${formatNumber(totalDevices)}</div>
        `;
        deviceStats.appendChild(statBox);

        // Count by type
        const typeCounts = {};
        counts.forEach(c => {
            typeCounts[c.device_type] = (typeCounts[c.device_type] || 0) + c.count;
        });

        for (const [type, count] of Object.entries(typeCounts)) {
            const box = document.createElement('div');
            box.className = 'stat-box';
            box.innerHTML = `
                <h4>${formatDeviceType(type)}</h4>
                <div class="value">${formatNumber(count)}</div>
            `;
            deviceStats.appendChild(box);
        }

        // Load device details
        let url = `${API_BASE}/devices?limit=50`;
        if (siteId) url += `&site_id=${siteId}`;
        if (deviceType) url += `&device_type=${deviceType}`;

        const response = await fetch(url);
        const devices = await response.json();

        if (devices.length === 0) {
            deviceList.innerHTML = '<p>No devices found. Make sure the device simulator is running.</p>';
            return;
        }

        // Display device table
        let html = `
            <table>
                <thead>
                    <tr>
                        <th>Device ID</th>
                        <th>Type</th>
                        <th>Site</th>
                        <th>Status</th>
                        <th>Timestamp</th>
                        <th>Key Metrics</th>
                    </tr>
                </thead>
                <tbody>
        `;

        devices.forEach(device => {
            const metrics = device.metrics || {};
            const status = device.status || {};

            let keyMetrics = '';
            if (device.device_type === 'turbine') {
                keyMetrics = `RPM: ${metrics.rpm || 'N/A'}, Power: ${metrics.power_kw || 'N/A'}kW`;
            } else if (device.device_type === 'thermal_engine') {
                keyMetrics = `RPM: ${metrics.rpm || 'N/A'}, Load: ${metrics.load_pct || 'N/A'}%`;
            } else {
                keyMetrics = Object.keys(metrics).slice(0, 2).map(k => `${k}: ${metrics[k]}`).join(', ');
            }

            const statusBadge = getStatusBadge(status.state || 'UNKNOWN');

            html += `
                <tr>
                    <td><strong>${device.device_id}</strong></td>
                    <td>${formatDeviceType(device.device_type)}</td>
                    <td>${device.site_id}</td>
                    <td>${statusBadge}</td>
                    <td>${formatTimestamp(device.timestamp_utc)}</td>
                    <td>${keyMetrics}</td>
                </tr>
            `;
        });

        html += '</tbody></table>';
        deviceList.innerHTML = html;

    } catch (error) {
        console.error('Error loading devices:', error);
        deviceList.innerHTML = '<p style="color: red;">Error loading device data. Check console for details.</p>';
    }
}

// User Sessions
async function loadUsers() {
    const userList = document.getElementById('user-list');
    const userStats = document.getElementById('user-stats');

    userList.innerHTML = '<div class="loading">Loading user data...</div>';

    try {
        const response = await fetch(`${API_BASE}/users`);
        const data = await response.json();

        // Display stats
        userStats.innerHTML = `
            <div class="stat-box">
                <h4>Active Users</h4>
                <div class="value">${data.active_users || 0}</div>
            </div>
        `;

        const users = data.users || [];

        if (users.length === 0) {
            userList.innerHTML = '<p>No active users found. Make sure the user simulator is running.</p>';
            return;
        }

        // Display user table
        let html = `
            <table>
                <thead>
                    <tr>
                        <th>User ID</th>
                        <th>Username</th>
                        <th>Session ID</th>
                        <th>Region</th>
                        <th>IP Address</th>
                        <th>Login Time</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
        `;

        users.slice(0, 100).forEach(user => {
            const statusBadge = user.connection_status === 'active' ?
                '<span class="badge badge-active">Active</span>' :
                '<span class="badge">Idle</span>';

            html += `
                <tr>
                    <td>${user.user_id}</td>
                    <td><strong>${user.username}</strong></td>
                    <td>${user.session_id}</td>
                    <td>${user.region}</td>
                    <td>${user.ip_address}</td>
                    <td>${formatTimestamp(user.login_time)}</td>
                    <td>${statusBadge}</td>
                </tr>
            `;
        });

        html += '</tbody></table>';
        userList.innerHTML = html;

    } catch (error) {
        console.error('Error loading users:', error);
        userList.innerHTML = '<p style="color: red;">Error loading user data. Check console for details.</p>';
    }
}

// Error Logs
async function loadErrorLogs() {
    const logData = document.getElementById('log-data');
    const logStats = document.getElementById('log-stats');

    logData.innerHTML = '<div class="loading">Loading error logs...</div>';

    try {
        const response = await fetch(`${API_BASE}/logs/errors`);
        const data = await response.json();

        // Display stats
        logStats.innerHTML = `
            <div class="stat-box">
                <h4>Total Errors</h4>
                <div class="value">${data.total_errors || 0}</div>
            </div>
        `;

        const errors = data.errors || [];

        if (errors.length === 0) {
            logData.innerHTML = '<p>No error logs found. System logs are being processed.</p>';
            return;
        }

        // Display error table
        let html = `
            <table>
                <thead>
                    <tr>
                        <th>IP Address</th>
                        <th>Method</th>
                        <th>Endpoint</th>
                        <th>Status Code</th>
                        <th>Error Count</th>
                    </tr>
                </thead>
                <tbody>
        `;

        errors.forEach(error => {
            const statusClass = error.status_code >= 500 ? 'badge-critical' : 'badge-warn';

            html += `
                <tr>
                    <td><strong>${error.ip_address}</strong></td>
                    <td>${error.method}</td>
                    <td>${error.endpoint}</td>
                    <td><span class="badge ${statusClass}">${error.status_code}</span></td>
                    <td>${error.error_count}</td>
                </tr>
            `;
        });

        html += '</tbody></table>';
        logData.innerHTML = html;

    } catch (error) {
        console.error('Error loading error logs:', error);
        logData.innerHTML = '<p style="color: red;">Error loading log data. Check console for details.</p>';
    }
}

// Top IPs
async function loadTopIPs() {
    const logData = document.getElementById('log-data');

    logData.innerHTML = '<div class="loading">Loading top IPs...</div>';

    try {
        const response = await fetch(`${API_BASE}/logs/top-ips`);
        const data = await response.json();

        const ips = data.top_ips || [];

        if (ips.length === 0) {
            logData.innerHTML = '<p>No IP data available yet.</p>';
            return;
        }

        // Display IP table
        let html = `
            <table>
                <thead>
                    <tr>
                        <th>IP Address</th>
                        <th>Total Requests</th>
                        <th>Errors</th>
                        <th>Avg Response Time</th>
                    </tr>
                </thead>
                <tbody>
        `;

        ips.forEach(ip => {
            html += `
                <tr>
                    <td><strong>${ip.ip_address}</strong></td>
                    <td>${ip.request_count}</td>
                    <td>${ip.error_count}</td>
                    <td>${Math.round(ip.avg_response_time)}ms</td>
                </tr>
            `;
        });

        html += '</tbody></table>';
        logData.innerHTML = html;

    } catch (error) {
        console.error('Error loading top IPs:', error);
        logData.innerHTML = '<p style="color: red;">Error loading IP data. Check console for details.</p>';
    }
}

// Images
async function loadImages() {
    const deviceType = document.getElementById('image-device-filter').value;
    const imageGrid = document.getElementById('image-grid');

    imageGrid.innerHTML = '<div class="loading">Loading image analysis...</div>';

    try {
        let url = `${API_BASE}/images`;
        if (deviceType) url += `?device_type=${deviceType}`;

        const response = await fetch(url);
        const data = await response.json();

        const images = data.images || [];

        if (images.length === 0) {
            imageGrid.innerHTML = '<p>No images processed yet. The image processor is analyzing site camera feeds...</p>';
            return;
        }

        // Display image cards
        let html = '';

        images.forEach(img => {
            const compliance = img.safety_compliance || {};
            const complianceScore = compliance.compliance_score || 0;
            const complianceClass = complianceScore >= 75 ? 'badge-ok' :
                                   complianceScore >= 50 ? 'badge-warn' : 'badge-critical';

            html += `
                <div class="image-card">
                    <h4>${img.filename}</h4>
                    <p><strong>Device Type:</strong> ${formatDeviceType(img.device_type)}</p>
                    <p><strong>Description:</strong> ${img.description || 'Processing...'}</p>

                    <p><strong>Safety Compliance:</strong>
                        <span class="badge ${complianceClass}">${Math.round(complianceScore)}%</span>
                    </p>

                    <div class="keywords">
                        ${(img.keywords || []).map(kw => `<span class="keyword-tag">${kw}</span>`).join('')}
                    </div>

                    <p style="margin-top: 10px; font-size: 0.85em;">
                        ${compliance.has_hard_hat ? '✓ Hard Hat' : '✗ No Hard Hat'} |
                        ${compliance.has_safety_vest ? '✓ Safety Vest' : '✗ No Vest'}
                    </p>
                </div>
            `;
        });

        imageGrid.innerHTML = html;

    } catch (error) {
        console.error('Error loading images:', error);
        imageGrid.innerHTML = '<p style="color: red;">Error loading image data. Check console for details.</p>';
    }
}

// Describe Images
async function describeImages() {
    const deviceType = document.getElementById('image-device-filter').value || 'turbine';

    try {
        const response = await fetch(`${API_BASE}/images/describe`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ device_type: deviceType })
        });

        const result = await response.json();

        alert(`Image Context Description:\n\n${result.description}\n\nKeywords: ${result.keywords.join(', ')}`);

    } catch (error) {
        console.error('Error describing images:', error);
        alert('Error generating image description. Check console for details.');
    }
}

// Natural Language Query
function setQuery(text) {
    document.getElementById('query-input').value = text;
}

async function submitQuery() {
    const question = document.getElementById('query-input').value.trim();
    const resultDiv = document.getElementById('query-result');

    if (!question) {
        alert('Please enter a question');
        return;
    }

    resultDiv.innerHTML = '<div class="loading">Processing query...</div>';
    resultDiv.classList.add('show');

    try {
        const response = await fetch(`${API_BASE}/query`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question })
        });

        const data = await response.json();

        resultDiv.innerHTML = `
            <h3>Query Result</h3>
            <p><strong>Question:</strong> ${question}</p>
            <p><strong>Answer:</strong> ${data.answer || 'No answer available'}</p>
            <p><em>Timestamp: ${new Date().toLocaleString()}</em></p>
        `;

    } catch (error) {
        console.error('Error submitting query:', error);
        resultDiv.innerHTML = '<p style="color: red;">Error processing query. Check console for details.</p>';
    }
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

// Failover Test Functions
async function runFailoverTest(testType, duration) {
    const statusDiv = document.getElementById('failover-status');
    statusDiv.innerHTML = `
        <div class="loading">
            <h3>⚙️ Running ${testType} test...</h3>
            <p>Duration: ${duration} seconds</p>
            <p>Please wait while the test completes...</p>
        </div>
    `;

    try {
        const response = await fetch(`${API_BASE}/failover/test?test_type=${testType}&duration_seconds=${duration}`, {
            method: 'POST'
        });

        const result = await response.json();

        const successIcon = result.success ? '✅' : '❌';
        const availabilityColor = result.availability_percentage >= 99.99 ? 'green' : 'red';

        statusDiv.innerHTML = `
            <div class="test-result ${result.success ? 'success' : 'failure'}">
                <h3>${successIcon} Test Complete: ${result.test_type}</h3>
                <div class="result-metrics">
                    <div class="metric">
                        <strong>Availability:</strong>
                        <span style="color: ${availabilityColor}; font-size: 1.5em;">${result.availability_percentage.toFixed(5)}%</span>
                    </div>
                    <div class="metric">
                        <strong>Recovery Time:</strong> ${result.recovery_time_seconds.toFixed(3)}s
                    </div>
                    <div class="metric">
                        <strong>Requests:</strong> ${result.requests_successful}/${result.requests_total} successful
                    </div>
                    <div class="metric">
                        <strong>Duration:</strong> ${result.duration_seconds.toFixed(2)}s
                    </div>
                </div>
                <div class="test-details">
                    <h4>Details:</h4>
                    <pre>${JSON.stringify(result.details, null, 2)}</pre>
                </div>
            </div>
        `;

        // Refresh results and summary
        await loadFailoverResults();
        await loadFailoverSummary();

    } catch (error) {
        console.error('Error running failover test:', error);
        statusDiv.innerHTML = `
            <div class="test-result failure">
                <h3>❌ Test Failed</h3>
                <p>Error: ${error.message}</p>
                <p>Check console for details.</p>
            </div>
        `;
    }
}

async function loadFailoverResults() {
    const resultsDiv = document.getElementById('failover-results');

    try {
        const response = await fetch(`${API_BASE}/failover/results?limit=10`);
        const data = await response.json();

        if (data.count === 0) {
            resultsDiv.innerHTML = '<p>No test results yet. Run a test to see results.</p>';
            return;
        }

        const tableHTML = `
            <table class="results-table">
                <thead>
                    <tr>
                        <th>Test Type</th>
                        <th>Availability</th>
                        <th>Recovery Time</th>
                        <th>Requests</th>
                        <th>Status</th>
                        <th>Timestamp</th>
                    </tr>
                </thead>
                <tbody>
                    ${data.tests.map(test => `
                        <tr class="${test.success ? 'success-row' : 'failure-row'}">
                            <td>${test.test_type}</td>
                            <td>${test.availability_percentage.toFixed(5)}%</td>
                            <td>${test.recovery_time_seconds.toFixed(3)}s</td>
                            <td>${test.requests_successful}/${test.requests_total}</td>
                            <td>${test.success ? '✅ Pass' : '❌ Fail'}</td>
                            <td>${formatTimestamp(test.start_time)}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;

        resultsDiv.innerHTML = tableHTML;

    } catch (error) {
        console.error('Error loading failover results:', error);
        resultsDiv.innerHTML = '<p style="color: red;">Error loading results</p>';
    }
}

async function loadFailoverSummary() {
    const summaryDiv = document.getElementById('failover-summary');

    try {
        const response = await fetch(`${API_BASE}/failover/summary`);
        const data = await response.json();

        const complianceIcon = data.tier0_compliant ? '✅' : '❌';
        const complianceColor = data.tier0_compliant ? 'green' : 'red';

        summaryDiv.innerHTML = `
            <div class="summary-grid">
                <div class="summary-card">
                    <h4>Total Tests</h4>
                    <div class="summary-value">${data.total_tests}</div>
                </div>
                <div class="summary-card">
                    <h4>Successful</h4>
                    <div class="summary-value" style="color: green;">${data.successful_tests}</div>
                </div>
                <div class="summary-card">
                    <h4>Failed</h4>
                    <div class="summary-value" style="color: red;">${data.failed_tests}</div>
                </div>
                <div class="summary-card">
                    <h4>Avg Availability</h4>
                    <div class="summary-value">${data.average_availability.toFixed(5)}%</div>
                </div>
                <div class="summary-card">
                    <h4>Target</h4>
                    <div class="summary-value">${data.target_availability.toFixed(5)}%</div>
                </div>
                <div class="summary-card">
                    <h4>Tier-0 Compliant</h4>
                    <div class="summary-value" style="color: ${complianceColor};">${complianceIcon}</div>
                </div>
            </div>
        `;

    } catch (error) {
        console.error('Error loading failover summary:', error);
        summaryDiv.innerHTML = '<p style="color: red;">Error loading summary</p>';
    }
}

// Load failover data when tab is opened
document.addEventListener('DOMContentLoaded', () => {
    loadFailoverSummary();
    loadFailoverResults();
});

// Failover Status Dashboard Card
async function loadFailoverStatus() {
    try {
        const response = await fetch(`${API_BASE}/failover/summary`);
        const data = await response.json();

        const availabilityDiv = document.getElementById('failover-availability');
        const statusLabel = document.getElementById('failover-status-label');

        if (data.total_tests === 0) {
            availabilityDiv.textContent = '-';
            statusLabel.textContent = 'No tests run yet';
            availabilityDiv.style.color = '#666';
        } else {
            const availability = data.average_availability.toFixed(5);
            availabilityDiv.textContent = `${availability}%`;

            // Color based on compliance
            if (data.tier0_compliant) {
                availabilityDiv.style.color = '#2ecc71';
                statusLabel.textContent = '✅ Tier-0 Compliant';
            } else {
                availabilityDiv.style.color = '#e74c3c';
                statusLabel.textContent = '⚠️ Below Target';
            }
        }

    } catch (error) {
        console.error('Error loading failover status:', error);
        document.getElementById('failover-availability').textContent = 'Error';
        document.getElementById('failover-status-label').textContent = 'Service unavailable';
    }
}

// Quick Failover Test (runs service availability test)
async function runQuickFailoverTest() {
    const availabilityDiv = document.getElementById('failover-availability');
    const statusLabel = document.getElementById('failover-status-label');

    availabilityDiv.textContent = '...';
    statusLabel.textContent = '⚙️ Running test...';
    availabilityDiv.style.color = '#f39c12';

    try {
        // Run a quick service availability test
        const response = await fetch(`${API_BASE}/failover/test?test_type=service_availability&duration_seconds=30`, {
            method: 'POST'
        });

        const result = await response.json();

        // Update card with result
        const availability = result.availability_percentage.toFixed(5);
        availabilityDiv.textContent = `${availability}%`;

        if (result.success) {
            availabilityDiv.style.color = '#2ecc71';
            statusLabel.textContent = `✅ Test passed (${result.recovery_time_seconds.toFixed(2)}s)`;
        } else {
            availabilityDiv.style.color = '#e74c3c';
            statusLabel.textContent = '❌ Test failed';
        }

        // Show notification
        alert(`Failover Test Complete!\n\nAvailability: ${availability}%\nRequests: ${result.requests_successful}/${result.requests_total}\nDuration: ${result.duration_seconds.toFixed(2)}s\n\nClick the Failover Test tab for detailed results.`);

        // Refresh full status
        loadFailoverStatus();

    } catch (error) {
        console.error('Error running quick failover test:', error);
        availabilityDiv.textContent = 'Error';
        statusLabel.textContent = 'Test failed';
        availabilityDiv.style.color = '#e74c3c';
        alert('Failover test failed. Check console for details.');
    }
}

