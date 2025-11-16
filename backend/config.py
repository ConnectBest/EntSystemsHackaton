import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Tier-0 Enterprise SRE System"
    VERSION: str = "1.0.0"
    SLA_TARGET: float = 99.99999

    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))

    # PostgreSQL
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "postgres")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "tier0_db")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "tier0user")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "tier0pass")

    # MongoDB
    MONGODB_HOST: str = os.getenv("MONGODB_HOST", "mongodb")
    MONGODB_PORT: int = int(os.getenv("MONGODB_PORT", "27017"))
    MONGODB_USER: str = os.getenv("MONGODB_USER", "tier0admin")
    MONGODB_PASSWORD: str = os.getenv("MONGODB_PASSWORD", "tier0mongo")

    # RabbitMQ
    RABBITMQ_HOST: str = os.getenv("RABBITMQ_HOST", "rabbitmq")
    RABBITMQ_PORT: int = int(os.getenv("RABBITMQ_PORT", "5672"))
    RABBITMQ_USER: str = os.getenv("RABBITMQ_USER", "tier0admin")
    RABBITMQ_PASS: str = os.getenv("RABBITMQ_PASS", "tier0secure")

    # MQTT
    MQTT_HOST: str = os.getenv("MQTT_HOST", "mqtt-broker")
    MQTT_PORT: int = int(os.getenv("MQTT_PORT", "1883"))

    # Cohere API
    COHERE_API_KEY: str = os.getenv("COHERE_API_KEY", "")

    @property
    def postgres_url(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def mongodb_url(self) -> str:
        return f"mongodb://{self.MONGODB_USER}:{self.MONGODB_PASSWORD}@{self.MONGODB_HOST}:{self.MONGODB_PORT}/"

    @property
    def rabbitmq_url(self) -> str:
        return f"amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASS}@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}/"

settings = Settings()
