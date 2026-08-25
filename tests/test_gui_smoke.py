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


def _wait_for_load(view, timeout_ms: int = 5000) -> bool:
    if not view.url().isEmpty() and view.page().isLoading() is False:
        return True
    loop = QEventLoop()
    result: list[bool] = []
    view.loadFinished.connect(lambda ok: (result.append(bool(ok)), loop.quit()))
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()
    return bool(result and result[-1])


def _javascript(view, expression: str, timeout_ms: int = 3000):
    loop = QEventLoop()
    result: list[object] = []
    view.page().runJavaScript(expression, lambda value: (result.append(value), loop.quit()))
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()
    return result[-1] if result else None


def test_desktop_shell_constructs_with_loaded_local_web_content():
    app = QApplication.instance() or QApplication([])
    controller = AppController(ROOT)
    runtime = DesktopRuntime(controller)
    bridge = Bridge(controller, runtime)
    window = MainWindow(runtime, bridge, ROOT / "ui" / "web")
    view = window.centralWidget()
    window.show()

    assert window.minimumWidth() == 1200
    assert window.minimumHeight() == 800
    assert view.url().isLocalFile()
    assert _wait_for_load(view) is True

    # Give the QWebChannel callback and initial catalog/Doctor requests a short
    # event-loop window, then assert that the real module frontend initialized.
    QTest.qWait(300)
    assert _javascript(view, "document.documentElement.dataset.appReady || ''") == "true"
    assert _javascript(view, "document.querySelectorAll('[data-harness]').length") > 0
    assert _javascript(view, "document.querySelectorAll('[data-task]').length") > 0

    catalog = json.loads(bridge.getCatalog("frontier_v3"))
    assert catalog["suite"] == "frontier_v3"
    assert catalog["harnesses"]
    assert catalog["tasks"]
    doctor = json.loads(bridge.getDoctor())
    assert doctor["report"]["harnesses"]
    assert "profile" in doctor

    window.close()
    app.processEvents()
