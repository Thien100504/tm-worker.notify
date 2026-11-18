"""
In-App Notification Sender

Saves notifications to the notification service's own database
and publishes to Redis pub/sub for real-time WebSocket delivery.
"""

import hashlib
import json
import logging
from typing import Any

import redis

from config import settings
from database import SyncSessionLocal
from models.notification import Notification

logger = logging.getLogger(__name__)


class InAppSender:
    """Handles in-app notifications: DB persistence + Redis pub/sub."""

    def __init__(self):
        self._redis = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
        )
        logger.info("InAppSender initialized.")

    def _generate_dedup_key(self, message: dict[str, Any]) -> str:
        data = message.get("data", message)
        entity_id = data.get("task_id") or data.get("project_id") or data.get("id", "")
        dedup_data = f"{message.get('event')}:{message.get('user_id')}:{entity_id}"
        hash_value = hashlib.md5(dedup_data.encode()).hexdigest()
        return f"notif:dedup:{hash_value}"

    def send(self, message: dict[str, Any]) -> None:
        event = message.get("event", "unknown")
        user_id = message.get("user_id")

        data = message.get("data")
        if not data:
            data = {
                k: v
                for k, v in message.items()
                if k
                not in (
                    "event",
                    "user_id",
                    "channels",
                    "telegram_chat_id",
                    "email",
                    "correlation_id",
                )
            }

        if not user_id:
            logger.warning("No user_id in message, skipping in-app notification.")
            return

        dedup_key = self._generate_dedup_key(message)
        is_new = self._redis.set(
            dedup_key, "1", ex=settings.NOTIFICATION_DEDUP_TTL, nx=True
        )
        if not is_new:
            logger.info(
                "Duplicate notification detected for event=%s user=%s, skipping.",
                event,
                user_id,
            )
            return

        try:
            with SyncSessionLocal() as session:
                # Prefer explicit title; fall back to title_key (i18n), then event type
                title = data.get("title") or data.get("title_key") or event
                notification = Notification(
                    user_id=user_id,
                    event_type=event,
                    event_data=data,
                    title=title,
                    message=str(data.get("message", ""))
                    if data.get("message")
                    else None,
                    type=data.get("type", "info"),
                    entity_type=data.get("entity_type"),
                    entity_id=data.get("entity_id")
                    or data.get("task_id")
                    or data.get("project_id"),
                    project_id=data.get("project_id"),
                )
                session.add(notification)
                session.commit()
                notification_id = str(notification.id)

                logger.info(
                    "Saved in-app notification %s for user %s", notification_id, user_id
                )
        except Exception as e:
            logger.error("Failed to save notification to DB: %s", e)
            raise

        try:
            channel = f"notifications:{user_id}"
            payload = json.dumps(
                {
                    "id": notification_id,
                    "event": event,
                    "title": title,
                    "title_key": data.get("title_key"),
                    "title_params": data.get("title_params"),
                    "message": data.get("message"),
                    "message_key": data.get("message_key"),
                    "message_params": data.get("message_params"),
                    "type": data.get("type", "info"),
                    "entity_type": data.get("entity_type"),
                    "data": data,
                    "read": False,
                }
            )
            self._redis.publish(channel, payload)
        except Exception as e:
            logger.error("Failed to publish to Redis pub/sub: %s", e)
