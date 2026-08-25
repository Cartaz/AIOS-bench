from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from config.settings import SettingsStore
from core.app_controller import AppController
from ui.bridge import Bridge
from ui.main_window import MainWindow
from ui.runtime import DesktopRuntime

ROOT = Path(__file__).resolve().parent


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    app = QApplication(sys.argv)
    settings = SettingsStore()
    controller = AppController(ROOT, settings)
    runtime = DesktopRuntime(controller)
    bridge = Bridge(controller, runtime)
    window = MainWindow(runtime, bridge, ROOT / "ui" / "web")
    app.aboutToQuit.connect(runtime.shutdown)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
