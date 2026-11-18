"""
Notification Service - Entry Point

Runs two components in parallel:
  1. RabbitMQ consumer — processes notification events
  2. HTTP API (FastAPI/uvicorn) — serves notification queries for portal-api

Usage:
    python -m main
    python main.py
    python main.py consumer   # consumer only
    python main.py api        # API only
"""

import logging
import signal
import sys
import threading

from config import settings
from consumers.notification_consumer import NotificationConsumer
from database import init_db
from logging_config import setup_logging

setup_logging(service_name="notification-service", level=settings.LOG_LEVEL)
logger = logging.getLogger("notification-service")


def run_consumer(worker_type: str = "all"):
    """Start RabbitMQ consumer (blocking, runs in thread)."""
    if worker_type == "inapp":
        consumer = NotificationConsumer(
            queue_name=settings.INAPP_QUEUE,
            allowed_channels=["inapp"],
        )
    elif worker_type == "external":
        consumer = NotificationConsumer(
            queue_name=settings.EXTERNAL_QUEUE,
            allowed_channels=["telegram", "email"],
        )
    else:
        consumer = NotificationConsumer(
            queue_name=settings.NOTIFICATION_QUEUE,
            allowed_channels=["inapp", "telegram", "email"],
        )

    def signal_handler(sig, frame):
        logger.info("Received shutdown signal (%s). Stopping consumer...", sig)
        consumer.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        logger.info("Starting notification consumer...")
        consumer.start()
    except KeyboardInterrupt:
        logger.info("Interrupted by user. Shutting down consumer...")
        consumer.stop()
    except Exception as e:
        logger.exception("Fatal error in notification consumer: %s", e)
        consumer.stop()
        sys.exit(1)


def run_api():
    """Start HTTP API server (blocking)."""
    import uvicorn

    logger.info(
        "Starting notification API on %s:%s", settings.API_HOST, settings.API_PORT
    )
    uvicorn.run(
        "api:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        log_level="warning",
    )


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"

    logger.info("=" * 60)
    logger.info("  Task Manager AI - Notification Service")
    logger.info("  Environment: %s", settings.ENVIRONMENT)
    logger.info("  Mode: %s", mode.upper())
    logger.info("  Database: %s", settings.DATABASE_URL.split("@")[-1])
    logger.info("=" * 60)

    init_db()

    if mode == "api":
        run_api()
    elif mode == "consumer":
        run_consumer()
    elif mode in ["inapp", "external"]:
        run_consumer(mode)
    else:
        api_thread = threading.Thread(target=run_api, daemon=True)
        api_thread.start()
        logger.info("HTTP API started in background thread")
        run_consumer()


if __name__ == "__main__":
    main()
