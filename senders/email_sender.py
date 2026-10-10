"""
Email Notification Sender

Sends notifications via SMTP with retry logic.
Retry strategy: 2 retries with simple backoff (5s, 10s).
"""

import logging
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from config import settings

logger = logging.getLogger(__name__)


class EmailSender:
    """Sends notifications via SMTP email."""

    def __init__(self):
        self._host = settings.SMTP_HOST
        self._port = settings.SMTP_PORT
        self._user = settings.SMTP_USER
        self._password = settings.SMTP_PASSWORD
        self._use_tls = settings.SMTP_USE_TLS
        self._from_email = settings.SMTP_FROM_EMAIL
        self._from_name = settings.SMTP_FROM_NAME
        self._max_retries = settings.EMAIL_MAX_RETRIES

        if self._host:
            logger.info(
                "EmailSender initialized (SMTP host: %s:%d).",
                self._host,
                self._port,
            )
        else:
            logger.warning(
                "EmailSender initialized WITHOUT SMTP host. "
                "Email notifications will be skipped."
            )

    def _build_email(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: str,
    ) -> MIMEMultipart:
        """Build a multipart email message."""
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{self._from_name} <{self._from_email}>"
        msg["To"] = to_email
        msg["Subject"] = subject

        # Plain text fallback
        msg.attach(MIMEText(body_text, "plain", "utf-8"))
        # HTML version
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        return msg

    def _format_subject(self, message: dict[str, Any]) -> str:
        """Generate email subject from notification data."""
        event = message.get("event", "unknown")
        data = message.get("data", {})
        title = data.get("title", "")

        event_labels = {
            "task.assigned": "📌 New task assigned",
            "task.completed": "✅ Task completed",
            "task.overdue": "⚠️ Task overdue",
            "project.member_added": "👥 Added to a project",
            "project.member_removed": "👋 Removed from a project",
            "automation.rule_failed": "❌ Automation rule failed",
            "system.announcement": "📢 System announcement",
            "system.maintenance": "🔧 System maintenance",
        }

        prefix = event_labels.get(event, "🔔 Notification")
        if title:
            return f"{prefix}: {title}"
        return prefix

    def _format_html(self, message: dict[str, Any]) -> str:
        """Generate HTML email body."""
        data = message.get("data", {})
        title = data.get("title", message.get("event", ""))
        body = data.get("message", "")
        url = data.get("url", "")

        link_html = ""
        if url:
            link_html = (
                f'<p><a href="{url}" style="color: #2563eb;">View details →</a></p>'
            )

        return f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: #2563eb; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
                <h2 style="margin: 0;">Task Manager AI</h2>
            </div>
            <div style="background: #ffffff; padding: 24px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 8px 8px;">
                <h3 style="color: #1f2937; margin-top: 0;">{title}</h3>
                <p style="color: #4b5563; line-height: 1.6;">{body}</p>
                {link_html}
            </div>
            <p style="color: #9ca3af; font-size: 12px; text-align: center; margin-top: 16px;">
                You received this email because you have a new notification from Task Manager AI.
            </p>
        </div>
        """

    def _format_text(self, message: dict[str, Any]) -> str:
        """Generate plain text email body."""
        data = message.get("data", {})
        title = data.get("title", message.get("event", ""))
        body = data.get("message", "")
        url = data.get("url", "")

        lines = [title, "", body]
        if url:
            lines.extend(["", f"View details: {url}"])
        lines.extend(["", "---", "Task Manager AI"])

        return "\n".join(lines)

    def _send_with_retry(self, msg: MIMEMultipart) -> bool:
        """
        Send email with retry logic.

        Retry schedule: 2 retries with 5s and 10s backoff.
        """
        for attempt in range(self._max_retries + 1):
            try:
                with smtplib.SMTP(self._host, self._port, timeout=30) as server:
                    if self._use_tls:
                        server.starttls()
                    if self._user and self._password:
                        server.login(self._user, self._password)
                    server.send_message(msg)

                logger.info(
                    "Email sent to %s (attempt %d)",
                    msg["To"],
                    attempt + 1,
                )
                return True

            except smtplib.SMTPException as e:
                logger.warning(
                    "SMTP error (attempt %d/%d): %s",
                    attempt + 1,
                    self._max_retries + 1,
                    e,
                )
            except Exception as e:
                logger.warning(
                    "Email send failed (attempt %d/%d): %s",
                    attempt + 1,
                    self._max_retries + 1,
                    e,
                )

            # Backoff: 5s, 10s
            if attempt < self._max_retries:
                backoff = 5 * (attempt + 1)
                logger.info("Retrying email in %ds...", backoff)
                time.sleep(backoff)

        logger.error(
            "Failed to send email to %s after %d attempts.",
            msg["To"],
            self._max_retries + 1,
        )
        return False

    def send(self, message: dict[str, Any]) -> None:
        """Send a notification via email."""
        if not self._host:
            logger.debug("SMTP host not configured, skipping email.")
            return

        to_email = message.get("email")
        if not to_email:
            logger.debug(
                "No email address in message for event=%s, skipping.",
                message.get("event"),
            )
            return

        subject = self._format_subject(message)
        body_html = self._format_html(message)
        body_text = self._format_text(message)

        msg = self._build_email(to_email, subject, body_html, body_text)
        self._send_with_retry(msg)
