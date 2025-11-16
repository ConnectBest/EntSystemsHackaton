-- Tier-0 Enterprise Database Schema

-- User Sessions Table
CREATE TABLE IF NOT EXISTS user_sessions (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    username VARCHAR(100) NOT NULL,
    session_id VARCHAR(100) UNIQUE NOT NULL,
    login_time TIMESTAMP NOT NULL,
    logout_time TIMESTAMP,
    ip_address VARCHAR(45),
    region VARCHAR(50),
    connection_status VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Device Telemetry Table
CREATE TABLE IF NOT EXISTS device_telemetry (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(50) NOT NULL,
    device_type VARCHAR(50) NOT NULL,
    site_id VARCHAR(50) NOT NULL,
    timestamp_utc TIMESTAMP NOT NULL,
    firmware VARCHAR(20),
    metrics JSONB,
    status JSONB,
    location JSONB,
    tags JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- System Logs Table
CREATE TABLE IF NOT EXISTS system_logs (
    id SERIAL PRIMARY KEY,
    ip_address VARCHAR(45),
    timestamp TIMESTAMP,
    method VARCHAR(10),
    endpoint VARCHAR(255),
    status_code INTEGER,
    response_size INTEGER,
    user_agent TEXT,
    response_time INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Image Metadata Table
CREATE TABLE IF NOT EXISTS image_metadata (
    id SERIAL PRIMARY KEY,
    image_path VARCHAR(500) NOT NULL,
    site_id VARCHAR(50),
    device_type VARCHAR(50),
    captured_at TIMESTAMP,
    processed BOOLEAN DEFAULT FALSE,
    embedding_id VARCHAR(100),
    description TEXT,
    tags JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Site Information Table
CREATE TABLE IF NOT EXISTS sites (
    id SERIAL PRIMARY KEY,
    site_id VARCHAR(50) UNIQUE NOT NULL,
    site_name VARCHAR(200),
    region VARCHAR(100),
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Device Registry Table
CREATE TABLE IF NOT EXISTS device_registry (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(50) UNIQUE NOT NULL,
    device_type VARCHAR(50) NOT NULL,
    site_id VARCHAR(50) REFERENCES sites(site_id),
    firmware VARCHAR(20),
    status VARCHAR(20) DEFAULT 'active',
    last_seen TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create Indexes for Performance
CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_session_id ON user_sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_device_telemetry_device_id ON device_telemetry(device_id);
CREATE INDEX IF NOT EXISTS idx_device_telemetry_site_id ON device_telemetry(site_id);
CREATE INDEX IF NOT EXISTS idx_device_telemetry_timestamp ON device_telemetry(timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_system_logs_ip ON system_logs(ip_address);
CREATE INDEX IF NOT EXISTS idx_system_logs_status ON system_logs(status_code);
CREATE INDEX IF NOT EXISTS idx_system_logs_timestamp ON system_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_image_metadata_site ON image_metadata(site_id);

-- Insert Sample Sites
INSERT INTO sites (site_id, site_name, region, latitude, longitude) VALUES
('WY-ALPHA', 'Wyoming Alpha Site', 'US-WEST', 43.4231, -106.3148),
('TX-EAGLE', 'Texas Eagle Site', 'US-SOUTH', 31.2319, -101.8752),
('ND-RAVEN', 'North Dakota Raven Site', 'US-NORTH', 48.3992, -102.7810),
('CA-DELTA', 'California Delta Site', 'US-WEST', 35.3733, -119.0187),
('OK-BRAVO', 'Oklahoma Bravo Site', 'US-SOUTH', 35.5376, -97.4206),
('CO-SIERRA', 'Colorado Sierra Site', 'US-WEST', 39.5501, -105.7821),
('LA-GULF', 'Louisiana Gulf Site', 'US-SOUTH', 29.9511, -90.0715),
('NM-MESA', 'New Mexico Mesa Site', 'US-SOUTH', 34.5199, -105.8701),
('AK-NORTH', 'Alaska North Site', 'US-ALASKA', 70.2008, -148.4597),
('MT-PEAK', 'Montana Peak Site', 'US-NORTH', 47.5089, -109.4532)
ON CONFLICT (site_id) DO NOTHING;
