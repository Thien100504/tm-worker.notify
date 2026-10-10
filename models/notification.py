"""
Notification Model

SQLAlchemy model for the notifications table in the 'notifications' schema.
Stores all in-app notification records.
"""

import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""

    pass


class Notification(Base):
    """In-app notification record."""

    __tablename__ = "notifications"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    user_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="Target user ID",
    )
    event_type = Column(
        String(100),
        nullable=True,
        index=True,
        comment="Event type, e.g. task.assigned",
    )
    title = Column(
        String(200),
        nullable=False,
        comment="Notification title",
    )
    message = Column(
        Text,
        nullable=True,
        comment="Notification body/message",
    )
    event_data = Column(
        JSON,
        nullable=True,
        comment="Additional event data as JSON",
    )
    type = Column(
        String(50),
        nullable=False,
        default="info",
    )
    entity_type = Column(
        String(50),
        nullable=True,
    )
    entity_id = Column(
        UUID(as_uuid=True),
        nullable=True,
    )
    project_id = Column(
        UUID(as_uuid=True),
        nullable=True,
    )
    is_read = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether the notification has been read",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Timestamp when notification was created",
    )

    def __repr__(self) -> str:
        return (
            f"<Notification(id={self.id}, "
            f"user_id={self.user_id}, "
            f"event={self.event_type}, "
            f"read={self.is_read})>"
        )
