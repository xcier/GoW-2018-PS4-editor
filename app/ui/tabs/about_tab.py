# app/ui/tabs/about_tab.py
from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextBrowser


class AboutTab(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        self.view = QTextBrowser(self)
        self.view.setObjectName("Card")
        self.view.setOpenExternalLinks(True)
        self.view.setReadOnly(True)

        html = """
        <style>
          body { font-family: Segoe UI, Arial, sans-serif; background: transparent; }
          .wrap { padding: 22px; }
          .hero { border-radius: 22px; padding: 22px; border: 1px solid rgba(148, 163, 184, 0.35); }
          h1 { margin: 0 0 6px 0; font-size: 30px; }
          h2 { margin-top: 24px; font-size: 20px; }
          p, li { line-height: 1.55; }
          code { padding: 2px 5px; border-radius: 5px; }
          .pill { display: inline-block; padding: 6px 10px; margin: 3px 4px 3px 0; border-radius: 999px; border: 1px solid rgba(148, 163, 184, 0.35); }
        </style>
        <div class="wrap">
          <div class="hero">
            <div class="pill">God of War 2018</div>
            <div class="pill">PS4 memory.dat</div>
            <div class="pill">Live-save verified</div>
            <h1>GoW Save Lab</h1>
            <p><b>Created by ProtoBuffers.</b> A PyQt6 editor for decrypted
            <i>God of War (2018)</i> PS4 <code>memory.dat</code> files.</p>
          </div>

          <h2>Safety model</h2>
          <ul>
            <li>Always edit a decrypted <code>memory.dat</code>, not a sealed/encrypted PS4 save.</li>
            <li>The newest active slot is selected automatically using slot timestamps.</li>
            <li>Inventory edits only write after the active slot inventory table validates.</li>
            <li>Existing item flag bytes are preserved; new entries are zero-initialized before writing.</li>
            <li>Overwrites are atomic and create timestamped <code>.bak</code> rollback files.</li>
          </ul>

          <h2>Data Sources</h2>
          <p>Item IDs, slot bases, and Save Wizard code references come from the community sheet:</p>
          <ul>
            <li><a href="https://docs.google.com/spreadsheets/d/1lFtR-dUWNXwvk6YgqFYlqoyNGR0Zf2uEhlNcajmiuI8/edit?gid=0#gid=0">Item IDs</a></li>
            <li><a href="https://docs.google.com/spreadsheets/d/1lFtR-dUWNXwvk6YgqFYlqoyNGR0Zf2uEhlNcajmiuI8/edit?gid=1156985750#gid=1156985750">Save Slot Starting Points</a></li>
            <li><a href="https://docs.google.com/spreadsheets/d/1lFtR-dUWNXwvk6YgqFYlqoyNGR0Zf2uEhlNcajmiuI8/edit?gid=309267710#gid=309267710">Save Wizard Codes</a></li>
          </ul>

          <h2>Credits</h2>
          <p>Thanks to the God of War save-modding and reverse-engineering community for documenting item IDs,
          inventory layouts, and save structures.</p>
        </div>
        """

        self.view.setHtml(html)
        layout.addWidget(self.view)
