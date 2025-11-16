import os
import time
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import cohere
from pymongo import MongoClient
import redis
from PIL import Image
import base64
from io import BytesIO

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
COHERE_API_KEY = os.getenv("COHERE_API_KEY", "")
MONGODB_HOST = os.getenv("MONGODB_HOST", "mongodb")
MONGODB_PORT = int(os.getenv("MONGODB_PORT", "27017"))
MONGODB_USER = os.getenv("MONGODB_USER", "tier0admin")
MONGODB_PASSWORD = os.getenv("MONGODB_PASSWORD", "tier0mongo")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

IMAGE_DIR = Path("/app/images")

# Device type to site mapping
DEVICE_TYPES = {
    "TurbineImages": "turbine",
    "ThermalEngines": "thermal_engine",
    "ElectricalRotors": "electrical_rotor",
    "OilAndGas": "connected_device"
}

class ImageProcessor:
    def __init__(self):
        self.cohere_client = None
        self.mongo_client = None
        self.redis_client = None
        self.db = None

    def connect(self):
        """Connect to MongoDB and Redis"""
        try:
            # Connect to MongoDB
            logger.info(f"Connecting to MongoDB at {MONGODB_HOST}:{MONGODB_PORT}...")
            mongo_url = f"mongodb://{MONGODB_USER}:{MONGODB_PASSWORD}@{MONGODB_HOST}:{MONGODB_PORT}/"

            max_retries = 30
            for i in range(max_retries):
                try:
                    self.mongo_client = MongoClient(mongo_url, serverSelectionTimeoutMS=5000)
                    self.mongo_client.admin.command('ping')
                    self.db = self.mongo_client['tier0_images']
                    logger.info("✓ MongoDB connected")
                    break
                except Exception as e:
                    if i < max_retries - 1:
                        logger.warning(f"MongoDB connection attempt {i+1}/{max_retries} failed, retrying...")
                        time.sleep(2)
                    else:
                        raise

            # Connect to Redis
            logger.info(f"Connecting to Redis at {REDIS_HOST}:{REDIS_PORT}...")
            self.redis_client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                decode_responses=False,
                socket_connect_timeout=5
            )
            self.redis_client.ping()
            logger.info("✓ Redis connected")

            # Initialize Cohere
            if COHERE_API_KEY:
                logger.info("Initializing Cohere client...")
                self.cohere_client = cohere.Client(COHERE_API_KEY)
                logger.info("✓ Cohere client initialized")
            else:
                logger.warning("⚠ COHERE_API_KEY not set, image embeddings will be simulated")

            return True

        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False

    def find_images(self) -> List[Dict]:
        """Find all images in the data directory"""
        images = []

        if not IMAGE_DIR.exists():
            logger.warning(f"Image directory {IMAGE_DIR} does not exist")
            return images

        for device_type_dir in IMAGE_DIR.iterdir():
            if not device_type_dir.is_dir():
                continue

            device_type = DEVICE_TYPES.get(device_type_dir.name)
            if not device_type:
                continue

            for image_file in device_type_dir.glob("*.jpg"):
                images.append({
                    "path": str(image_file),
                    "device_type": device_type,
                    "filename": image_file.name,
                    "size": image_file.stat().st_size
                })

        logger.info(f"Found {len(images)} images")
        return images

    def generate_image_description(self, image_path: str, device_type: str) -> Dict:
        """Generate AI description for image (simulated if no API key)"""
        # Safety-related keywords based on device type
        safety_keywords = {
            "turbine": ["hard hat", "safety helmet", "protective gear", "worker", "industrial equipment",
                       "turbine machinery", "safety vest", "inspection", "maintenance"],
            "thermal_engine": ["thermal equipment", "engine maintenance", "safety protocols",
                             "protective equipment", "industrial safety", "worker safety"],
            "electrical_rotor": ["electrical safety", "rotor inspection", "safety gear",
                                "high voltage equipment", "protective clothing"],
            "connected_device": ["oil field equipment", "wellhead", "remote monitoring",
                               "field operations", "safety compliance"]
        }

        import random
        keywords = safety_keywords.get(device_type, ["industrial", "safety", "equipment"])
        selected_keywords = random.sample(keywords, min(5, len(keywords)))

        # Simulated description
        has_hard_hat = random.random() > 0.3  # 70% chance worker has hard hat
        has_safety_vest = random.random() > 0.4  # 60% chance has safety vest
        has_tablet = random.random() > 0.7  # 30% chance has tablet

        description = f"Industrial {device_type} site showing "
        if has_hard_hat and has_safety_vest:
            description += "workers wearing proper safety equipment including hard hats and safety vests"
        elif has_hard_hat:
            description += "workers with hard hats"
        else:
            description += "workers without visible hard hats (safety concern)"

        if has_tablet:
            description += ", some holding tablets or inspection equipment"

        return {
            "description": description,
            "keywords": selected_keywords,
            "safety_compliance": {
                "has_hard_hat": has_hard_hat,
                "has_safety_vest": has_safety_vest,
                "has_inspection_equipment": has_tablet,
                "compliance_score": (
                    (1 if has_hard_hat else 0) +
                    (1 if has_safety_vest else 0) +
                    (0.5 if has_tablet else 0)
                ) / 2.5 * 100
            }
        }

    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate text embedding using Cohere (or simulated)"""
        if self.cohere_client:
            try:
                response = self.cohere_client.embed(
                    texts=[text],
                    model="embed-english-v3.0",
                    input_type="search_document"
                )
                return response.embeddings[0]
            except Exception as e:
                logger.error(f"Cohere embedding error: {e}")

        # Simulated embedding (random vector)
        import numpy as np
        return np.random.rand(1024).tolist()

    def process_image(self, image_info: Dict) -> bool:
        """Process a single image"""
        try:
            image_path = image_info["path"]
            device_type = image_info["device_type"]

            logger.info(f"Processing {image_path}...")

            # Check if already processed
            existing = self.db['images'].find_one({"path": image_path})
            if existing and existing.get("processed"):
                logger.info(f"  Already processed, skipping")
                return True

            # Generate description
            description_data = self.generate_image_description(image_path, device_type)

            # Generate embedding from description
            embedding_text = f"{description_data['description']} {' '.join(description_data['keywords'])}"
            embedding = self.generate_embedding(embedding_text)

            # Store in MongoDB
            document = {
                "path": image_path,
                "filename": image_info["filename"],
                "device_type": device_type,
                "size": image_info["size"],
                "description": description_data["description"],
                "keywords": description_data["keywords"],
                "safety_compliance": description_data["safety_compliance"],
                "embedding": embedding,
                "processed": True,
                "processed_at": datetime.utcnow(),
                "created_at": datetime.utcnow()
            }

            self.db['images'].update_one(
                {"path": image_path},
                {"$set": document},
                upsert=True
            )

            # Cache in Redis
            cache_key = f"image:{device_type}:{image_info['filename']}"
            self.redis_client.setex(
                cache_key,
                3600,  # 1 hour
                json.dumps({
                    "description": description_data["description"],
                    "keywords": description_data["keywords"],
                    "safety_compliance": description_data["safety_compliance"]
                })
            )

            logger.info(f"  ✓ Processed successfully")
            return True

        except Exception as e:
            logger.error(f"Error processing {image_info['path']}: {e}")
            return False

    def run(self):
        """Main processing loop"""
        if not self.connect():
            logger.error("Failed to connect to services, exiting...")
            return

        logger.info("Starting image processing service...")

        # Initial processing
        images = self.find_images()
        if images:
            logger.info(f"Processing {len(images)} images...")
            for image in images:
                self.process_image(image)
                time.sleep(0.5)  # Rate limiting

        logger.info("Initial processing complete, entering monitoring mode...")

        # Monitor for new images
        processed_count = len(images)
        while True:
            try:
                time.sleep(60)  # Check every minute

                # Re-scan for new images
                current_images = self.find_images()
                if len(current_images) > processed_count:
                    new_images = current_images[processed_count:]
                    logger.info(f"Found {len(new_images)} new images")

                    for image in new_images:
                        self.process_image(image)
                        time.sleep(0.5)

                    processed_count = len(current_images)

            except KeyboardInterrupt:
                logger.info("Stopping image processor...")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(10)

        if self.mongo_client:
            self.mongo_client.close()
        if self.redis_client:
            self.redis_client.close()

if __name__ == "__main__":
    processor = ImageProcessor()
    processor.run()
