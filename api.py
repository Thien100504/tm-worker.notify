"""
Notification Service HTTP API.

Exposes notification queries as REST endpoints, called by portal-api.
This makes worker.notify the single owner of notification data.

Endpoints:
  GET  /notifications?user_id=...&limit=50&offset=0
  GET  /notifications/unread-count?user_id=...
  PATCH /notifications/{id}/read?user_id=...
  PATCH /notifications/read-all?user_id=...
"""

import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, model_validator
from sqlalchemy import select, func, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.notification import Notification

app = FastAPI(title="Notification Service API", version="1.0.0")


class NotificationResponse(BaseModel):
    id: uuid.UUID
    event_type: Optional[str] = None
    title: str
    title_key: Optional[str] = None
    title_params: Optional[dict] = None
    message: Optional[str] = None
    message_key: Optional[str] = None
    message_params: Optional[dict] = None
    event_data: Optional[dict] = None
    type: str
    entity_type: Optional[str] = None
    entity_id: Optional[uuid.UUID] = None
    project_id: Optional[uuid.UUID] = None
    is_read: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def extract_i18n_from_event_data(self):
        """Pull title_key/message_key from event_data JSON for older records."""
        if self.event_data:
            if not self.title_key:
                self.title_key = self.event_data.get("title_key")
            if not self.title_params:
                self.title_params = self.event_data.get("title_params")
            if not self.message_key:
                self.message_key = self.event_data.get("message_key")
            if not self.message_params:
                self.message_params = self.event_data.get("message_params")
        return self


class UnreadCountResponse(BaseModel):
    count: int


@app.get("/health")
async def health():
    return {"status": "ok", "service": "notification"}


@app.get("/notifications", response_model=List[NotificationResponse])
async def list_notifications(
    user_id: uuid.UUID = Query(...),
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == str(user_id))
        .order_by(Notification.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


@app.get("/notifications/unread-count", response_model=UnreadCountResponse)
async def unread_count(
    user_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
):
    count = (
        await db.scalar(
            select(func.count(Notification.id)).where(
                Notification.user_id == str(user_id),
                Notification.is_read.is_(False),
            )
        )
        or 0
    )
    return UnreadCountResponse(count=count)


@app.patch("/notifications/{notif_id}/read", response_model=NotificationResponse)
async def mark_read(
    notif_id: uuid.UUID,
    user_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        sa_update(Notification)
        .where(Notification.id == str(notif_id), Notification.user_id == str(user_id))
        .values(is_read=True)
        .returning(Notification.id)
    )
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="notification.not_found")
    await db.flush()

    notif = await db.execute(
        select(Notification).where(Notification.id == str(notif_id))
    )
    return notif.scalar_one()


@app.patch("/notifications/read-all")
async def mark_all_read(
    user_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        sa_update(Notification)
        .where(Notification.user_id == str(user_id), Notification.is_read.is_(False))
        .values(is_read=True)
        .returning(Notification.id)
    )
    return {"marked_read": len(result.fetchall())}
