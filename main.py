from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from app import __about__
from app.core.file_context import FileContext
from app.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setOrganizationName(__about__.__organization__)
    app.setApplicationName(__about__.__app_name__)
    app.setApplicationDisplayName(__about__.__display_name__)
    app.setApplicationVersion(__about__.__version__)

    ctx = FileContext()
    win = MainWindow(ctx)
    win.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())