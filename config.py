"""
Notification Service - Configuration
Loads settings from environment variables with sensible defaults.
"""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ─────────────────────────────────────────────
    # RabbitMQ
    # ─────────────────────────────────────────────
    RABBITMQ_URL: str = Field(
        default="amqp://taskmanager:taskmanager_dev@localhost:5672/",
        description="RabbitMQ connection URL",
    )
    NOTIFICATION_QUEUE: str = Field(
        default="notification_queue",
        description="Default queue name for all events",
    )
    INAPP_QUEUE: str = Field(
        default="inapp_notification_queue",
        description="Queue name for in-app notification events",
    )
    EXTERNAL_QUEUE: str = Field(
        default="external_notification_queue",
        description="Queue name for external notification events (Telegram/Email)",
    )
    NOTIFICATION_EXCHANGE: str = Field(
        default="task_manager",
        description="Exchange name for notification routing",
    )

    # ─────────────────────────────────────────────
    # Database (notification-owned, separate from monolith)
    # ─────────────────────────────────────────────
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://taskmanager:taskmanager_dev@localhost:5432/notification_db",
        description="Notification service's own PostgreSQL database URL",
    )

    # ─────────────────────────────────────────────
    # HTTP API
    # ─────────────────────────────────────────────
    API_HOST: str = Field(default="0.0.0.0", description="HTTP API bind host")
    API_PORT: int = Field(default=8001, description="HTTP API port")

    # ─────────────────────────────────────────────
    # Redis
    # ─────────────────────────────────────────────
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for pub/sub and deduplication",
    )
    NOTIFICATION_DEDUP_TTL: int = Field(
        default=60,
        description="Deduplication TTL in seconds",
    )

    # ─────────────────────────────────────────────
    # Telegram
    # ─────────────────────────────────────────────
    TELEGRAM_BOT_TOKEN: str = Field(
        default="",
        description="Telegram Bot API token",
    )
    TELEGRAM_MAX_RETRIES: int = Field(default=3)
    TELEGRAM_RETRY_BACKOFF_BASE: int = Field(
        default=5,
        description="Base backoff in seconds (5s → 15s → 45s)",
    )

    # ─────────────────────────────────────────────
    # SMTP / Email
    # ─────────────────────────────────────────────
    SMTP_HOST: str = Field(default="", description="SMTP server hostname")
    SMTP_PORT: int = Field(default=587, description="SMTP server port")
    SMTP_USER: str = Field(default="", description="SMTP username")
    SMTP_PASSWORD: str = Field(default="", description="SMTP password")
    SMTP_USE_TLS: bool = Field(default=True, description="Use STARTTLS")
    SMTP_FROM_EMAIL: str = Field(
        default="noreply@taskmanager.local",
        description="Sender email address",
    )
    SMTP_FROM_NAME: str = Field(
        default="Task Manager AI",
        description="Sender display name",
    )
    EMAIL_MAX_RETRIES: int = Field(default=2)

    # ─────────────────────────────────────────────
    # General
    # ─────────────────────────────────────────────
    ENVIRONMENT: str = Field(default="development")
    LOG_LEVEL: str = Field(default="INFO")
    FRONTEND_URL: str = Field(
        default="http://localhost:3000",
        description="Base URL of the frontend application",
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Singleton settings instance
settings = Settings()
