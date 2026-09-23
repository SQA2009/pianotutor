"""Process entry point for the PianoTutor desktop app."""

from __future__ import annotations

import logging
import sys

logger = logging.getLogger(__name__)


def main() -> int:
    from PySide6.QtWidgets import QApplication

    from pianotutor.app import Application
    from pianotutor.ui.main_window import MainWindow
    from pianotutor.ui.theme import APP_STYLESHEET

    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName("PianoTutor")
    qt_app.setStyleSheet(APP_STYLESHEET)

    app = Application()
    window = MainWindow(app)
    window.show()

    return qt_app.exec()


if __name__ == "__main__":
    sys.exit(main())
