"""
Telegram Notification Sender

Sends notifications via Telegram Bot API with retry logic.
Retry strategy: 3 retries with exponential backoff (5s, 15s, 45s).
"""

import logging
import time
import pathlib
import html
from typing import Any

import requests
from jinja2 import Environment, FileSystemLoader
from jinja2.exceptions import TemplateNotFound

from config import settings

logger = logging.getLogger(__name__)


class TelegramSender:
    """Sends notifications via Telegram Bot API."""

    def __init__(self):
        self._bot_token = settings.TELEGRAM_BOT_TOKEN
        self._max_retries = settings.TELEGRAM_MAX_RETRIES
        self._backoff_base = settings.TELEGRAM_RETRY_BACKOFF_BASE
        self._api_base = f"https://api.telegram.org/bot{self._bot_token}"

        if self._bot_token:
            logger.info("TelegramSender initialized (token configured).")
        else:
            logger.warning(
                "TelegramSender initialized WITHOUT token. "
                "Telegram notifications will be skipped."
            )
        # Load templates from directory
        self.env = None
        template_dir = pathlib.Path(__file__).parent.parent / "templates" / "telegram"
        if template_dir.exists():
            self.env = Environment(loader=FileSystemLoader(str(template_dir)))
            logger.info("Loaded Telegram templates from %s", template_dir)
        else:
            logger.warning("Telegram template directory not found: %s", template_dir)

    def _format_message(self, message: dict[str, Any]) -> str:
        """Format notification data into a Telegram message."""
        event = message.get("event", "unknown")

        # Determine template name (e.g. task.updated -> task_updated.j2)
        template_key = event.replace(".", "_") + ".j2"

        if self.env:
            try:
                # Render using Jinja2
                template = self.env.get_template(template_key)
                return template.render(**message, FRONTEND_URL=settings.FRONTEND_URL)
            except TemplateNotFound:
                pass  # Use fallback
            except Exception as e:
                logger.error("Template rendering failed for %s: %s", template_key, e)

        # Fallback to default
        data = message.get("data", message)
        title = data.get("title", event)
        body = data.get("message", "")

        # Use Telegram HTML formatting
        lines = [
            f"🔔 <b>{html.escape(str(title))}</b>",
            "",
            html.escape(str(body)) if body else "",
        ]

        # Add task link if available
        task_url = data.get("url")
        if task_url:
            lines.append("")
            lines.append(f'<a href="{task_url}">View details</a>')

        return "\n".join(line for line in lines if line is not None)

    def _send_with_retry(self, chat_id: str, text: str, thread_id: str = None) -> bool:
        """
        Send message to Telegram with exponential backoff retry.
        Supports message_thread_id for Topics.
        """
        for attempt in range(self._max_retries + 1):
            try:
                payload = {
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                }
                if thread_id:
                    payload["message_thread_id"] = thread_id

                response = requests.post(
                    f"{self._api_base}/sendMessage",
                    json=payload,
                    timeout=10,
                )

                if response.status_code == 200:
                    logger.info(
                        "Telegram message sent to chat_id=%s (attempt %d)",
                        chat_id,
                        attempt + 1,
                    )
                    return True

                # Rate limited
                if response.status_code == 429:
                    retry_after = (
                        response.json().get("parameters", {}).get("retry_after", 30)
                    )
                    logger.warning(
                        "Telegram rate limited. Waiting %ds...",
                        retry_after,
                    )
                    time.sleep(retry_after)
                    continue

                logger.warning(
                    "Telegram API error (attempt %d/%d): %s %s",
                    attempt + 1,
                    self._max_retries + 1,
                    response.status_code,
                    response.text[:200],
                )

            except requests.RequestException as e:
                logger.warning(
                    "Telegram request failed (attempt %d/%d): %s",
                    attempt + 1,
                    self._max_retries + 1,
                    e,
                )

            # Exponential backoff: 5s → 15s → 45s
            if attempt < self._max_retries:
                backoff = self._backoff_base * (3**attempt)
                logger.info("Retrying in %ds...", backoff)
                time.sleep(backoff)

        logger.error(
            "Failed to send Telegram message to chat_id=%s after %d attempts.",
            chat_id,
            self._max_retries + 1,
        )
        return False

    def send(self, message: dict[str, Any]) -> None:
        """Send a notification via Telegram."""
        if not self._bot_token:
            logger.debug("Telegram bot token not configured, skipping.")
            return

        chat_id = message.get("telegram_chat_id")
        if not chat_id:
            logger.debug(
                "No telegram_chat_id in message for event=%s, skipping.",
                message.get("event"),
            )
            return

        thread_id = message.get("telegram_thread_id")
        text = self._format_message(message)
        self._send_with_retry(
            str(chat_id), text, thread_id=str(thread_id) if thread_id else None
        )
