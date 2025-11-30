from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from app.core.file_context import FileContext
from app.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("GoW 2018 Save Editor")

    ctx = FileContext()
    win = MainWindow(ctx)
    win.resize(1280, 800)
    win.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())