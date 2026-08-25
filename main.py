from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from core.app_controller import AppController
from ui.bridge import Bridge
from ui.main_window import MainWindow

ROOT = Path(__file__).resolve().parent


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    app = QApplication(sys.argv)
    controller = AppController(ROOT)
    bridge = Bridge(controller)
    window = MainWindow(controller, bridge, ROOT / "ui" / "web")
    app.aboutToQuit.connect(controller.shutdown)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
