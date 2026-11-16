"""
Notification Consumer

Consumes messages from RabbitMQ notification_queue and routes them
to the appropriate senders based on the event type.

Message format:
{
    "event": "task.assigned",
    "user_id": "uuid",
    "data": { ... },
    "channels": ["inapp", "email", "telegram"],  // optional override
    "telegram_chat_id": "123456",                 // if telegram channel
    "email": "user@example.com"                   // if email channel
}
"""

import json
import logging
import threading
from typing import Any

import pika
import pika.exceptions
from pika.adapters.blocking_connection import BlockingChannel
from pika.spec import Basic, BasicProperties

from config import settings
from logging_config import correlation_id_var
from senders.inapp_sender import InAppSender
from senders.email_sender import EmailSender
from senders.telegram_sender import TelegramSender

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Event → Channel Mapping
# Defines which channels each event type uses by default
# ─────────────────────────────────────────────
NOTIFICATION_EVENTS: dict[str, list[str]] = {
    # Task events
    "task.assigned": ["inapp", "email", "telegram"],
    "task.updated": ["inapp", "telegram"],
    "task.completed": ["inapp", "email", "telegram"],
    "task.overdue": ["inapp", "email", "telegram"],
    "task.commented": ["inapp", "telegram"],
    "task.due_soon": ["inapp", "telegram"],
    # Sprint events (General channel — no user_id, telegram only)
    "sprint.started": ["telegram"],
    "sprint.completed": ["telegram"],
    "sprint.reopened": ["telegram"],
    # Project events
    "project.member_added": ["inapp", "email"],
    "project.member_removed": ["inapp", "email"],
    # AI events
    "ai.suggestion_ready": ["inapp"],
    "ai.analysis_complete": ["inapp"],
    # Automation events
    "automation.rule_triggered": ["inapp"],
    "automation.rule_failed": ["inapp", "email"],
    # Direct notifications (from portal-api via RabbitMQ)
    "notification.direct": ["inapp"],
    # System events
    "system.announcement": ["inapp", "email", "telegram"],
    "system.maintenance": ["inapp", "email"],
}


def with_display_fields(message: dict[str, Any]) -> dict[str, Any]:
    """
    portal-api publishes i18n keys and params (title_params, message_params), while the
    Telegram and email senders need plain title/message/url fields. Fill them in.
    """
    out = dict(message)
    title_params = out.get("title_params") or {}
    message_params = out.get("message_params") or {}
    out.setdefault(
        "title",
        title_params.get("title") or title_params.get("name") or out.get("event", ""),
    )
    actor = message_params.get("actor") or title_params.get("actor")
    if "message" not in out and actor:
        out["message"] = f"By {actor}"
    if "url" not in out and out.get("project_id"):
        url = f"{settings.FRONTEND_URL.rstrip('/')}/projects/{out['project_id']}"
        if out.get("task_id"):
            url += f"/kanban?taskId={out['task_id']}"
        out["url"] = url
    return out


class NotificationConsumer:
    """RabbitMQ consumer for notification events."""

    def __init__(self, queue_name: str, allowed_channels: list[str]):
        self._connection: pika.BlockingConnection | None = None
        self._channel: BlockingChannel | None = None

        self.queue_name = queue_name
        self._stopping = False
        self._wake = threading.Event()  # interrupts the reconnect wait on stop()
        self.allowed_channels = allowed_channels

        # Lazy initialize senders
        self._sender_map = {}
        if "inapp" in allowed_channels:
            self._sender_map["inapp"] = InAppSender()
        if "email" in allowed_channels:
            self._sender_map["email"] = EmailSender()
        if "telegram" in allowed_channels:
            self._sender_map["telegram"] = TelegramSender()

    def _connect(self) -> None:
        """Establish connection to RabbitMQ."""
        # Never log the URL itself: it contains the password
        logger.info(
            "Connecting to RabbitMQ at %s", settings.RABBITMQ_URL.split("@")[-1]
        )

        parameters = pika.URLParameters(settings.RABBITMQ_URL)
        parameters.heartbeat = 600
        parameters.blocked_connection_timeout = 300

        self._connection = pika.BlockingConnection(parameters)
        self._channel = self._connection.channel()

        # Declare exchange and queue
        self._channel.exchange_declare(
            exchange=settings.NOTIFICATION_EXCHANGE,
            exchange_type="topic",
            durable=True,
        )
        self._channel.queue_declare(
            queue=self.queue_name,
            durable=True,
        )
        # Bind queue to multiple topics
        routing_keys = [
            "task.#",
            "sprint.#",
            "project.#",
            "ai.#",
            "automation.#",
            "system.#",
            "notification.#",
        ]
        for rk in routing_keys:
            self._channel.queue_bind(
                queue=self.queue_name,
                exchange=settings.NOTIFICATION_EXCHANGE,
                routing_key=rk,
            )

        # Fair dispatch - prefetch 1 message at a time
        self._channel.basic_qos(prefetch_count=1)

        logger.info("Connected to RabbitMQ successfully.")

    def _on_message(
        self,
        channel: BlockingChannel,
        method: Basic.Deliver,
        properties: BasicProperties,
        body: bytes,
    ) -> None:
        """Handle incoming notification message."""
        try:
            message: dict[str, Any] = json.loads(body)
            cid = message.pop("correlation_id", properties.correlation_id or "-")
            correlation_id_var.set(cid)

            event_type = message.get("event", method.routing_key)
            user_id = message.get("user_id")

            logger.info(
                "Received event: %s for user: %s cid=%s",
                event_type,
                user_id,
                cid,
            )

            # Determine channels: use message override or event mapping
            channels = message.get(
                "channels",
                NOTIFICATION_EVENTS.get(event_type, ["inapp"]),
            )

            # Filter channels based on what this consumer is allowed to process
            channels_to_process = [c for c in channels if c in self.allowed_channels]

            if not channels_to_process:
                # If this consumer doesn't handle any of the channels for this event, just ack and skip
                logger.debug(
                    "Skipping event %s (no channels match %s)",
                    event_type,
                    self.allowed_channels,
                )
                self._channel.basic_ack(delivery_tag=method.delivery_tag)
                return

            # Route to appropriate senders
            for channel_name in channels_to_process:
                sender = self._sender_map.get(channel_name)
                if sender is None:
                    logger.warning(
                        "Unknown channel '%s' for event '%s'",
                        channel_name,
                        event_type,
                    )
                    continue

                try:
                    external = channel_name in ("email", "telegram")
                    sender.send(with_display_fields(message) if external else message)
                    logger.info(
                        "Sent %s notification for event: %s",
                        channel_name,
                        event_type,
                    )
                except Exception as e:
                    logger.error(
                        "Failed to send %s notification for event %s: %s",
                        channel_name,
                        event_type,
                        e,
                    )

            # Acknowledge message
            self._channel.basic_ack(delivery_tag=method.delivery_tag)

        except json.JSONDecodeError:
            logger.error("Invalid JSON in message body: %s", body[:200])
            # Reject and don't requeue malformed messages
            self._channel.basic_nack(
                delivery_tag=method.delivery_tag,
                requeue=False,
            )
        except Exception as e:
            logger.exception("Error processing message: %s", e)
            # Reject and don't requeue to avoid infinite loops with poison messages
            self._channel.basic_nack(
                delivery_tag=method.delivery_tag,
                requeue=False,
            )

    def start(self) -> None:
        """Consume messages; reconnect with backoff when RabbitMQ is down or the connection drops."""
        delay = 5
        while not self._stopping:
            try:
                self._connect()
                self._channel.basic_consume(
                    queue=self.queue_name,
                    on_message_callback=self._on_message,
                    auto_ack=False,
                )
                logger.info(
                    "Waiting for messages on queue: %s (channels: %s)",
                    self.queue_name,
                    self.allowed_channels,
                )
                delay = 5
                self._channel.start_consuming()
                if self._stopping:
                    break
            except pika.exceptions.AMQPError as e:
                if self._stopping:
                    break
                logger.warning(
                    "RabbitMQ connection lost (%s). Reconnecting in %ds...",
                    type(e).__name__,
                    delay,
                )
                self._wake.wait(delay)
                delay = min(delay * 2, 60)

    def stop(self) -> None:
        """Stop consuming and close connection."""
        logger.info("Stopping notification consumer...")
        self._stopping = True
        self._wake.set()

        try:
            if self._channel and self._channel.is_open:
                self._channel.stop_consuming()
            if self._connection and self._connection.is_open:
                self._connection.close()
        except Exception as e:
            logger.error("Error during consumer shutdown: %s", e)

        logger.info("Notification consumer stopped.")
