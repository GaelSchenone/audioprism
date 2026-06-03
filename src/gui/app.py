"""QApplication factory with the GL surface format the engine needs."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QSurfaceFormat
from PySide6.QtWidgets import QApplication


def create_app() -> QApplication:
    fmt = QSurfaceFormat()
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.CoreProfile)
    fmt.setSwapInterval(1)            # vsync
    QSurfaceFormat.setDefaultFormat(fmt)

    # Lets GL resources be shared across windows (preview + fullscreen).
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("audioprism")
    return app
