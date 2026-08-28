from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_MAX_BYTES = 2 * 1024 * 1024
LOG_BACKUP_COUNT = 3
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def log_path() -> Path:
    """Return the per-user persistent application log path."""
    base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return base / "aios-bench" / "app.log"


def configure_logging() -> Path | None:
    """Configure console logging plus a bounded persistent file when available."""
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    persistent_path = log_path()
    try:
        persistent_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(
            RotatingFileHandler(
                persistent_path,
                maxBytes=LOG_MAX_BYTES,
                backupCount=LOG_BACKUP_COUNT,
                encoding="utf-8",
            )
        )
    except OSError:
        persistent_path = None

    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        handlers=handlers,
        force=True,
    )
    if persistent_path is None:
        logging.getLogger(__name__).warning(
            "Persistent logging is unavailable; continuing with console logging only"
        )
    return persistent_path
