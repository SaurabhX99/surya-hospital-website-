"""
Production-ready logging configuration for AWS deployment.

Outputs structured JSON logs to stdout — compatible with:
  - AWS CloudWatch Logs (ECS, EC2, Lambda)
  - AWS CloudWatch Log Insights (query by level, request_id, path, etc.)
  - Any log aggregator that ingests JSON (Datadog, Splunk, ELK)

Usage:
    from logging_config import get_logger
    logger = get_logger(__name__)
    logger.info("Appointment created", extra={"appointment_id": "abc123"})

Log format (one JSON object per line):
    {"timestamp":"2024-01-15T10:30:00.123Z","level":"INFO","logger":"routes.appointments",
     "message":"Appointment created","appointment_id":"abc123"}
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """Format log records as single-line JSON for structured log ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level":     record.levelname,
            "logger":    record.name,
            "message":   record.getMessage(),
        }
        # Merge any extra fields passed via logger.info(..., extra={...})
        for key in ("request_id", "method", "path", "status_code",
                     "duration_ms", "client_ip", "user_email",
                     "appointment_id", "error", "error_type"):
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val

        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


def setup_logging() -> None:
    """
    Configure the root logger for production.

    - LOG_LEVEL env var controls verbosity (default: INFO).
    - All output goes to stdout as JSON (one object per line).
    - Suppresses noisy third-party loggers (uvicorn access, pymongo).
    """
    level = os.getenv("LOG_LEVEL", "INFO").upper()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    root = logging.getLogger()
    root.setLevel(level)
    # Remove any pre-existing handlers (uvicorn adds its own)
    root.handlers.clear()
    root.addHandler(handler)

    # Quieten noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("pymongo").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger. Call setup_logging() once at app startup first."""
    return logging.getLogger(name)
