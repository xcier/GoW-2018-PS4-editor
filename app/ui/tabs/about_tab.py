# app/ui/tabs/about_tab.py
from __future__ import annotations

from typing import Optional

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextBrowser


class AboutTab(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)

        self.view = QTextBrowser(self)
        self.view.setOpenExternalLinks(True)
        self.view.setReadOnly(True)

        font = QFont()
        font.setPointSize(10)
        self.view.setFont(font)

        html = """
        <h2>GoW 2018 Save Editor</h2>
        <p>Created by <b>ProtoBuffers</b> in Python + PyQt6.</p>
        <p>This is a fan-made save editor for <i>God of War (2018)</i>.</p>

        <p><b>Always back up your saves before editing.</b></p>

        <h3>Data Sources</h3>
        <p>
            Item and inventory data in this editor is largely based on community research
            and the following spreadsheet:
        </p>
        <ul>
          <li>
            <a href="https://docs.google.com/spreadsheets/d/1lFtR-dUWNXwvk6YgqFYlqoyNGR0Zf2uEhlNcajmiuI8/edit?gid=1625401531#gid=1625401531">
              God of War 2018 Item / Inventory Spreadsheet
            </a>
          </li>
        </ul>

        <h3>Credits</h3>
        <p>
            Huge thanks to the GoW modding and reverse-engineering community for
            documenting item IDs, inventory layouts, and save structures.
        </p>
        """

        self.view.setHtml(html)
        layout.addWidget(self.view)
