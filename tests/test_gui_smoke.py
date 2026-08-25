import json
from pathlib import Path

from PySide6.QtWidgets import QApplication

from core.app_controller import AppController
from ui.bridge import Bridge
from ui.main_window import MainWindow

ROOT = Path(__file__).resolve().parents[1]


def test_desktop_shell_constructs_with_local_web_content():
    app = QApplication.instance() or QApplication([])
    controller = AppController(ROOT)
    bridge = Bridge(controller)
    window = MainWindow(controller, bridge, ROOT / "ui" / "web")

    assert window.minimumWidth() == 1200
    assert window.minimumHeight() == 800
    assert window.centralWidget().url().isLocalFile()
    catalog = json.loads(bridge.getCatalog("frontier_v3"))
    assert catalog["suite"] == "frontier_v3"
    assert catalog["harnesses"]
    assert catalog["tasks"]

    window.close()
    app.processEvents()
