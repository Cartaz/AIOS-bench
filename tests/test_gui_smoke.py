import json
from pathlib import Path

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from core.app_controller import AppController
from ui.bridge import Bridge
from ui.main_window import MainWindow
from ui.runtime import DesktopRuntime

ROOT = Path(__file__).resolve().parents[1]


def _javascript(view, expression: str, timeout_ms: int = 3000):
    loop = QEventLoop()
    result: list[object] = []
    view.page().runJavaScript(expression, lambda value: (result.append(value), loop.quit()))
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()
    return result[-1] if result else None


def _wait_for_web_content(view, timeout_ms: int = 8000) -> bool:
    if _javascript(view, "document.readyState") == "complete":
        return True
    loop = QEventLoop()
    loaded: list[bool] = []

    def on_loaded(ok: bool) -> None:
        loaded.append(bool(ok))
        loop.quit()

    view.loadFinished.connect(on_loaded)
    view.reload()
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()
    try:
        view.loadFinished.disconnect(on_loaded)
    except (RuntimeError, TypeError):
        pass
    return bool(loaded and loaded[-1]) and _javascript(view, "document.readyState") == "complete"


def _wait_for_app_ready(view, timeout_ms: int = 12000) -> str:
    waited = 0
    while waited < timeout_ms:
        value = _javascript(view, "document.documentElement.dataset.appReady || ''")
        if value in {"true", "false"}:
            return str(value)
        QTest.qWait(50)
        waited += 50
    return ""


def test_desktop_shell_constructs_with_loaded_local_web_content():
    app = QApplication.instance() or QApplication([])
    controller = AppController(ROOT)
    runtime = DesktopRuntime(controller)
    bridge = Bridge(controller, runtime)
    window = MainWindow(runtime, bridge, ROOT / "ui" / "web")
    view = window.centralWidget()
    window.show()

    assert window.minimumWidth() == 920
    assert window.minimumHeight() == 700
    assert view.url().isLocalFile()

    # Exercise the actual Chromium/QWebChannel path, including the asynchronous
    # Doctor worker used during frontend initialization.
    assert _wait_for_web_content(view)
    assert _wait_for_app_ready(view) == "true"
    assert _javascript(view, "document.querySelectorAll('[data-harness]').length") > 0
    assert _javascript(view, "document.querySelectorAll('[data-task]').length") > 0
    assert _javascript(view, "document.querySelectorAll('.doctor-item').length") > 0

    catalog = json.loads(bridge.getCatalog("frontier_v3"))
    assert catalog["suite"] == "frontier_v3"
    assert catalog["harnesses"]
    assert catalog["tasks"]

    window.close()
    app.processEvents()
