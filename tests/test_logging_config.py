from __future__ import annotations

import logging
from pathlib import Path

from config import logging as logging_config


def test_log_path_uses_xdg_state_home(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    assert logging_config.log_path() == tmp_path / "aios-bench" / "app.log"


def test_configure_logging_creates_rotating_file(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    root = logging.getLogger()
    previous_handlers = list(root.handlers)
    previous_level = root.level
    try:
        path = logging_config.configure_logging()
        logging.getLogger("aios-test").warning("persistent-test-line")
        for handler in root.handlers:
            handler.flush()

        assert path == tmp_path / "aios-bench" / "app.log"
        assert path.is_file()
        assert "persistent-test-line" in path.read_text(encoding="utf-8")
    finally:
        for handler in root.handlers:
            if handler not in previous_handlers:
                handler.close()
        root.handlers[:] = previous_handlers
        root.setLevel(previous_level)
