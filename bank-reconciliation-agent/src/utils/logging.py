"""Structured logging setup."""

import structlog


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structured logger with the given name."""
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    return structlog.get_logger(name)
