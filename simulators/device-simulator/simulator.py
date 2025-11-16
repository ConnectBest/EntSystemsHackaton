import paho.mqtt.client as mqtt
import json
import time
import random
import os
from datetime import datetime
from typing import List, Dict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
MQTT_HOST = os.getenv("MQTT_HOST", "mqtt-broker")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
NUM_DEVICES = int(os.getenv("NUM_DEVICES", "100000"))
NUM_SITES = int(os.getenv("NUM_SITES", "10"))
PUBLISH_INTERVAL = int(os.getenv("PUBLISH_INTERVAL", "5"))

# Site configurations
SITES = [
    {"id": "WY-ALPHA", "name": "Wyoming Alpha", "lat": 43.4231, "lon": -106.3148},
    {"id": "TX-EAGLE", "name": "Texas Eagle", "lat": 31.2319, "lon": -101.8752},
    {"id": "ND-RAVEN", "name": "North Dakota Raven", "lat": 48.3992, "lon": -102.7810},
    {"id": "CA-DELTA", "name": "California Delta", "lat": 35.3733, "lon": -119.0187},
    {"id": "OK-BRAVO", "name": "Oklahoma Bravo", "lat": 35.5376, "lon": -97.4206},
    {"id": "CO-SIERRA", "name": "Colorado Sierra", "lat": 39.5501, "lon": -105.7821},
    {"id": "LA-GULF", "name": "Louisiana Gulf", "lat": 29.9511, "lon": -90.0715},
    {"id": "NM-MESA", "name": "New Mexico Mesa", "lat": 34.5199, "lon": -105.8701},
    {"id": "AK-NORTH", "name": "Alaska North", "lat": 70.2008, "lon": -148.4597},
    {"id": "MT-PEAK", "name": "Montana Peak", "lat": 47.5089, "lon": -109.4532}
]

# Device types
DEVICE_TYPES = {
    "turbine": {
        "count_per_site": 2500,
        "metrics": ["rpm", "inlet_temp_c", "exhaust_temp_c", "vibration_mm_s",
                   "pressure_bar", "power_kw", "fuel_flow_kg_h", "no_x_ppm"]
    },
    "thermal_engine": {
        "count_per_site": 2500,
        "metrics": ["rpm", "coolant_temp_c", "oil_temp_c", "oil_pressure_bar",
                   "load_pct", "fuel_rate_l_h", "soot_pct"]
    },
    "electrical_rotor": {
        "count_per_site": 2500,
        "metrics": ["rpm", "voltage_v", "current_a", "frequency_hz",
                   "power_factor", "bearing_temp_c", "winding_temp_c"]
    },
    "connected_device": {
        "count_per_site": 2500,
        "metrics": ["wellhead_pressure_bar", "wellhead_temp_c", "flow_rate_m3_h",
                   "methane_leak_ppm", "battery_soc_pct", "rssi_dbm"]
    }
}

class DeviceSimulator:
    def __init__(self):
        self.client = mqtt.Client()
        self.devices = []
        self.connected = False

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("✓ Connected to MQTT broker")
            self.connected = True
        else:
            logger.error(f"✗ Failed to connect to MQTT broker (rc={rc})")

    def on_publish(self, client, userdata, mid):
        pass  # Message published successfully

    def connect(self):
        """Connect to MQTT broker"""
        self.client.on_connect = self.on_connect
        self.client.on_publish = self.on_publish

        try:
            logger.info(f"Connecting to MQTT broker at {MQTT_HOST}:{MQTT_PORT}...")
            self.client.connect(MQTT_HOST, MQTT_PORT, 60)
            self.client.loop_start()

            # Wait for connection
            timeout = 30
            while not self.connected and timeout > 0:
                time.sleep(1)
                timeout -= 1

            if not self.connected:
                logger.error("Failed to connect to MQTT broker within timeout")
                return False

            return True
        except Exception as e:
            logger.error(f"MQTT connection error: {e}")
            return False

    def generate_devices(self):
        """Generate virtual device registry"""
        logger.info(f"Generating {NUM_DEVICES} devices across {NUM_SITES} sites...")

        device_id = 0
        for site in SITES[:NUM_SITES]:
            for device_type, config in DEVICE_TYPES.items():
                devices_per_type = config["count_per_site"]

                for i in range(devices_per_type):
                    self.devices.append({
                        "device_id": f"{device_type.upper()[:4]}-{device_id:05d}",
                        "device_type": device_type,
                        "site_id": site["id"],
                        "location": {"lat": site["lat"], "lon": site["lon"]},
                        "metrics": config["metrics"]
                    })
                    device_id += 1

                    if device_id >= NUM_DEVICES:
                        break
                if device_id >= NUM_DEVICES:
                    break
            if device_id >= NUM_DEVICES:
                break

        logger.info(f"✓ Generated {len(self.devices)} devices")

    def generate_turbine_telemetry(self, device):
        """Generate turbine telemetry data"""
        status_states = ["OK", "WARN", "CRITICAL"]
        weights = [0.90, 0.08, 0.02]

        state = random.choices(status_states, weights=weights)[0]

        return {
            "device_id": device["device_id"],
            "device_type": "turbine",
            "site_id": device["site_id"],
            "timestamp_utc": datetime.utcnow().isoformat() + "Z",
            "firmware": f"{random.randint(3,5)}.{random.randint(0,9)}.{random.randint(0,9)}",
            "metrics": {
                "rpm": random.randint(3000, 3600),
                "inlet_temp_c": round(random.uniform(380, 450), 1),
                "exhaust_temp_c": round(random.uniform(500, 580), 1),
                "vibration_mm_s": round(random.uniform(1.5, 4.0), 1),
                "pressure_bar": round(random.uniform(15.0, 20.0), 1),
                "power_kw": round(random.uniform(10000, 15000), 1),
                "fuel_flow_kg_h": round(random.uniform(350, 500), 1),
                "no_x_ppm": round(random.uniform(25, 50), 1)
            },
            "status": {
                "state": state,
                "code": f"TURB-{state}",
                "message": "Nominal" if state == "OK" else f"Alert: {state}"
            },
            "location": device["location"],
            "tags": {
                "vendor": random.choice(["HanTech", "GE", "Siemens"]),
                "loop": random.choice(["A1", "A2", "B1", "B2"])
            }
        }

    def generate_thermal_engine_telemetry(self, device):
        """Generate thermal engine telemetry data"""
        status_states = ["OK", "WARN", "CRITICAL"]
        weights = [0.88, 0.10, 0.02]

        state = random.choices(status_states, weights=weights)[0]

        return {
            "device_id": device["device_id"],
            "device_type": "thermal_engine",
            "site_id": device["site_id"],
            "timestamp_utc": datetime.utcnow().isoformat() + "Z",
            "firmware": f"{random.randint(1,2)}.{random.randint(0,9)}.{random.randint(0,9)}",
            "metrics": {
                "rpm": random.randint(1600, 2000),
                "coolant_temp_c": round(random.uniform(85, 95), 1),
                "oil_temp_c": round(random.uniform(90, 105), 1),
                "oil_pressure_bar": round(random.uniform(4.0, 5.5), 1),
                "load_pct": round(random.uniform(60, 85), 1),
                "fuel_rate_l_h": round(random.uniform(140, 180), 1),
                "soot_pct": round(random.uniform(0.3, 0.8), 1)
            },
            "status": {
                "state": state,
                "code": f"THRM-{state}",
                "message": "Nominal" if state == "OK" else "Oil pressure trending low"
            },
            "location": device["location"],
            "tags": {
                "skid": f"TE-{random.randint(1,20):02d}",
                "phase": random.choice(["commissioned", "testing", "production"])
            }
        }

    def generate_electrical_rotor_telemetry(self, device):
        """Generate electrical rotor telemetry data"""
        return {
            "device_id": device["device_id"],
            "device_type": "electrical_rotor",
            "site_id": device["site_id"],
            "timestamp_utc": datetime.utcnow().isoformat() + "Z",
            "firmware": f"{random.randint(2,4)}.{random.randint(0,9)}.{random.randint(0,9)}",
            "metrics": {
                "rpm": random.randint(1700, 1850),
                "voltage_v": random.randint(10000, 13800),
                "current_a": round(random.uniform(400, 600), 1),
                "frequency_hz": round(random.uniform(59.9, 60.1), 2),
                "power_factor": round(random.uniform(0.85, 0.95), 2),
                "bearing_temp_c": round(random.uniform(55, 75), 1),
                "winding_temp_c": round(random.uniform(70, 90), 1)
            },
            "status": {
                "state": "OK",
                "code": "ELEC-OK",
                "message": "Generator operational"
            },
            "location": device["location"],
            "tags": {
                "manufacturer": random.choice(["ABB", "Westinghouse", "GE"]),
                "grid": "MAIN"
            }
        }

    def generate_connected_device_telemetry(self, device):
        """Generate oil & gas connected device telemetry"""
        return {
            "device_id": device["device_id"],
            "device_type": "connected_device",
            "site_id": device["site_id"],
            "timestamp_utc": datetime.utcnow().isoformat() + "Z",
            "firmware": f"{random.randint(4,6)}.{random.randint(0,9)}.{random.randint(0,9)}",
            "metrics": {
                "wellhead_pressure_bar": round(random.uniform(120, 150), 1),
                "wellhead_temp_c": round(random.uniform(60, 75), 1),
                "flow_rate_m3_h": round(random.uniform(70, 100), 1),
                "methane_leak_ppm": round(random.uniform(0.5, 3.0), 1),
                "battery_soc_pct": round(random.uniform(75, 100), 0),
                "rssi_dbm": random.randint(-85, -60)
            },
            "status": {
                "state": "OK",
                "code": "GW-OK",
                "message": "All sensors online"
            },
            "location": device["location"],
            "tags": {
                "network": random.choice(["LTE", "LoRaWAN", "Satellite"]),
                "ingress": f"MQTT-{random.randint(1,5)}"
            }
        }

    def publish_telemetry(self, device):
        """Publish device telemetry to MQTT"""
        # Generate telemetry based on device type
        generators = {
            "turbine": self.generate_turbine_telemetry,
            "thermal_engine": self.generate_thermal_engine_telemetry,
            "electrical_rotor": self.generate_electrical_rotor_telemetry,
            "connected_device": self.generate_connected_device_telemetry
        }

        generator = generators.get(device["device_type"])
        if not generator:
            return

        telemetry = generator(device)

        # Topic: og/field/{site_id}/{device_type}/{device_id}
        topic = f"og/field/{device['site_id']}/{device['device_type']}/{device['device_id']}"

        # Publish to MQTT
        payload = json.dumps(telemetry)
        self.client.publish(topic, payload, qos=1)

    def run(self):
        """Main simulation loop"""
        if not self.connect():
            logger.error("Failed to connect to MQTT broker, exiting...")
            return

        self.generate_devices()

        logger.info(f"Starting telemetry simulation (publishing every {PUBLISH_INTERVAL}s)...")

        cycle = 0
        while True:
            try:
                # Sample a subset of devices to publish (to avoid overwhelming the broker)
                # Publish 1% of devices each cycle (1000 devices if total is 100k)
                sample_size = max(1000, NUM_DEVICES // 100)
                sample_devices = random.sample(self.devices, min(sample_size, len(self.devices)))

                for device in sample_devices:
                    self.publish_telemetry(device)

                cycle += 1
                if cycle % 10 == 0:
                    logger.info(f"Published {sample_size} telemetry messages (cycle {cycle})")

                time.sleep(PUBLISH_INTERVAL)

            except KeyboardInterrupt:
                logger.info("Stopping simulator...")
                break
            except Exception as e:
                logger.error(f"Error in simulation loop: {e}")
                time.sleep(5)

        self.client.loop_stop()
        self.client.disconnect()

if __name__ == "__main__":
    simulator = DeviceSimulator()
    simulator.run()
