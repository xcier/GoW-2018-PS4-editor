GoW 2018 Save Editor

Created by ProtoBuffers
A modern PyQt6-based save editor for God of War (2018) (PS4).
Built for research, modding, and personal experimentation.

⚠️ Important Warning

This tool modifies save data directly.
Always back up your save files before using the editor.

⭐ Features
🔹 Inventory Editor

View all items found in your save.

Edit quantity directly (double-click Qty cell).

Add/remove/clear items using a full database of known item IDs.

Automatically maps and writes changes back to the correct memory offsets.

Uses correct slot base offsets + 16-byte inventory entries.

🔹 Stats Editor

Edit Kratos stats pulled directly from the save (if implemented in your build).

🔹 Dark Mode / Light Mode

Full UI theme switcher.

🔹 About Tab

Includes credits and links to the original Google Sheets data source.

🔹 Settings Tab

Central configuration for theme and UI behavior.

📁 Project Structure
GoW 2018/
│ main.py
│ gow2018_editor.spec
│ README.md
│
├── app/
│   ├── core/
│   │   ├── file_context.py
│   │   ├── save_file.py
│   │   └── gow2018_data.py
│   │
│   ├── resources/
│   │   └── database/
│   │       ├── items.json
│   │       ├── categories.json
│   │       └── (other DB files)
│   │
│   └── ui/
│       ├── main_window.py
│       └── tabs/
│           ├── inventory_tab.py
│           ├── stats_tab.py
│           ├── settings_tab.py
│           └── about_tab.py

📦 Installation
Requirements

Python 3.10 – 3.13

PyQt6

PyInstaller (optional, for building EXE)

Install dependencies:

pip install PyQt6

🚀 Running the Editor

From the project root:

python main.py

🛠 Building an EXE (Windows)

A PyInstaller spec file is included:

gow2018_editor.spec

Bundles all resources under app/resources/database

Produces a clean EXE with no console window

Build it:

pyinstaller gow2018_editor.spec


Output will appear in:

dist/GoW2018Editor.exe

📚 Data Sources

Item data and inventory offsets originate from community reverse-engineering work and this spreadsheet:

God of War 2018 Item / Inventory Spreadsheet
https://docs.google.com/spreadsheets/d/1lFtR-dUWNXwvk6YgqFYlqoyNGR0Zf2uEhlNcajmiuI8/edit#gid=1625401531

🧩 Save File Notes

Inventory entries are 16 bytes each:

[0..7] → Item ID

[8..11] → Quantity (LE u32)

[12..15] → Flags/unknown

Slot base offsets are resolved dynamically.

The editor updates:

Used slots

Free slots

Removed item cleanup

Editing quantities in the UI only changes internal state.
Actual save modification happens when you Save / Save As:

self.inventory_tab.apply_to_save()
self.file_ctx.save_to_disk()


(Already integrated in your MainWindow.)

🎨 Credits

ProtoBuffers — Development, UI, save research

GoW reverse-engineering community

Google Sheets contributors

PyQt6 project

📬 Support / Suggestions

If you want, I can add:

Binary icon embedding

Portable ZIP build

Logging window

Auto-detect save slots

Weapon / armor sub-editors

Just ask — happy to extend this project anytime.