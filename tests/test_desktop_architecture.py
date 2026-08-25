from __future__ import annotations

import inspect

from core import app_controller


def test_core_app_controller_does_not_import_qt_runtime():
    source = inspect.getsource(app_controller)
    assert "PySide6" not in source
    assert "QThread" not in source
    assert "QObject" not in source
