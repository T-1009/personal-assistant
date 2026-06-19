"""Application-wide logging configuration.

Configured at import time (before uvicorn sets up its loggers).
Uvicorn's LOGGING_CONFIG has disable_existing_loggers=False and only
touches uvicorn/uvicorn.error/uvicorn.access — our "app" hierarchy
is left untouched.
"""

import logging
import logging.config

from app.settings import Settings, get_settings


def configure(settings: Settings | None = None) -> None:
    """Apply logging configuration. Idempotent — safe for --reload."""
    log_level = (settings or get_settings()).log_level

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": ("%(asctime)s [%(levelname)s] %(name)s: %(message)s"),
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                    "formatter": "default",
                },
            },
            "loggers": {
                "app": {
                    "handlers": ["console"],
                    "level": log_level,
                    "propagate": False,
                },
            },
        }
    )
