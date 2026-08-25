from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QCloseEvent, QDesktopServices
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QMainWindow, QMessageBox

from .bridge import Bridge
from .runtime import DesktopRuntime


class LocalPage(QWebEnginePage):
    def acceptNavigationRequest(self, url: QUrl, navigation_type, is_main_frame: bool) -> bool:
        if url.scheme() in {"file", "qrc", "about"}:
            return True
        if url.scheme() in {"http", "https"}:
            QDesktopServices.openUrl(url)
        return False


class MainWindow(QMainWindow):
    def __init__(self, runtime: DesktopRuntime, bridge: Bridge, web_root: Path) -> None:
        super().__init__()
        self._runtime = runtime
        self.setWindowTitle("AIOS-Bench")
        self.setMinimumSize(1200, 800)
        self.resize(1440, 920)

        view = QWebEngineView(self)
        page = LocalPage(view)
        settings = page.settings()
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls,
            False,
        )
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls,
            True,
        )
        channel = QWebChannel(page)
        channel.registerObject("backend", bridge)
        page.setWebChannel(channel)
        view.setPage(page)
        view.setUrl(QUrl.fromLocalFile(str((web_root / "index.html").resolve())))
        self.setCentralWidget(view)
        self._view = view
        self._channel = channel

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._runtime.is_busy:
            QMessageBox.information(
                self,
                "Operazione in esecuzione",
                "La finestra resterà aperta finché l'operazione corrente non termina.",
            )
            event.ignore()
            return
        event.accept()
