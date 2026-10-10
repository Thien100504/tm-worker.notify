"""
Structured JSON Logging for Notification Service.

Mirrors portal-api/app/logging_config.py — kept as a separate copy
because worker.notify runs as an independent process with its own
Python path.
"""

import json
import logging
import sys
from contextvars import ContextVar
from typing import Any

correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="-")


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": correlation_id_var.get("-"),
        }

        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        for key in ("service", "event", "channel"):
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val

        return json.dumps(log_entry, default=str, ensure_ascii=False)


def setup_logging(
    service_name: str = "notification-service",
    level: str = "INFO",
    json_output: bool = True,
) -> None:
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    if json_output:
        handler.setFormatter(JSONFormatter(datefmt="%Y-%m-%dT%H:%M:%S"))
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | [%(correlation_id)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
                defaults={"correlation_id": "-"},
            )
        )

    root.addHandler(handler)

    logging.getLogger("pika").setLevel(logging.WARNING)
