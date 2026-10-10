# 🔔 Worker Notify - Notification Microservice

This repository contains the Microservice responsible for sending notifications (Telegram, Email, In-App) for the Task Manager AI system.

## 🏗️ Architecture
This microservice runs fully independently and does not expose an API. Instead, it acts as a **Consumer**:
1. Listens for events from **RabbitMQ** (published by `portal-api`).
2. Handles template logic and retries.
3. Calls third-party APIs (Telegram Bot API, SMTP Server) to deliver the notifications to users.

## ⚡ Setup (Local Development)

### 1. Requirements
- Python 3.11
- `portal-api` is running (to provide RabbitMQ and the DB).

### 2. Set up environment variables
Create a `.env` file with the connections to `portal-api`'s RabbitMQ and Postgres. Defaults to `localhost`:
```env
DATABASE_URL=postgresql+asyncpg://taskmanager:taskmanager_dev@localhost:5432/taskmanager
REDIS_URL=redis://localhost:6379/0
RABBITMQ_URL=amqp://taskmanager:taskmanager_dev@localhost:5672/
TELEGRAM_BOT_TOKEN=your_bot_token_here
```

### 3. Install and Run
```bash
make install
make dev
```

## 🚀 Deployment
The repo is configured to automatically build the `tm-notification-service` Docker image and deploy via `.gitlab-ci.yml`.
