# GoW Save Lab

Created by **ProtoBuffers**. A PyQt6 desktop save editor for decrypted **God of War (2018) PS4 `memory.dat`** files.

This project edits decrypted save data only. It does **not** decrypt, re-encrypt, resign, or modify PS4 account/security data.

Current app version: **0.9.9**.

## Features

- Auto-detects and opens the newest active save slot.
- Dashboard with active slot, difficulty, XP, Hacksilver, and validation state.
- Slot Manager for viewing all 20 physical save slots.
- Slot Tools for backing up, restoring, importing, and transferring individual `.gow2018slot` packages or whole slot blocks.
- Slot copy workflows for moving a slot within the loaded save, into another decrypted `memory.dat`, or from another decrypted save into the loaded save.
- Inventory editor with type tabs, searchable current-slot view, add/remove/edit quantity, max selected, max all, and Advanced Unlock for manual system-row edits.
- Experimental inventory append mode for test saves where no free item records are available.
- XP and Hacksilver sync between Dashboard and Inventory by locating the actual inventory rows instead of assuming fixed row positions.
- Guarded Hex Editor with read-only default, search/jump tools, known offsets, and explicit staged byte patching.
- Save Preview before writes.
- Atomic save writes with timestamped rollback `.bak` backups.
- Multiple UI themes with persistent theme/recent-save preferences.

## Safety model

The editor is designed to avoid silent save corruption:

- Save writes are staged in memory first.
- Save/Save As show a change review before writing.
- Overwrites use atomic replacement and create rollback backups.
- Inventory writes require a valid XP table anchor.
- No-edit roundtrips are covered by regression tests and can be checked against your own decrypted saves with the validator.
- Locked/system inventory rows are protected by default. Advanced Unlock allows manual quantity edits, but still blocks removal.

Known verified inventory/resource table offset:

```text
slot_base + 0x1041D
```

Inventory/resource records are treated as 16-byte entries:

```text
0x00..0x07  item/resource ID bytes
0x08..0x0B  quantity, little-endian uint32
0x0C..0x0F  metadata/flags, preserved for existing records
```

## Run from source

```bat
py -3 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m app
```

You can also run:

```bat
python main.py
```

## Build single-file Windows EXE

The included PyInstaller spec is configured for a **single-file windowed executable**. It has no `COLLECT` step; bundled code, Qt files, and database resources are attached to `dist\GoWSaveLab.exe`.

```bat
py -3 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
python -m compileall -q .
python -m pytest -q
pyinstaller --clean --noconfirm gow_save_lab.spec
```

Output:

```text
dist\GoWSaveLab.exe
```

Or use the Windows build helper:

```bat
build_windows.bat
```

## Test

```bat
python -m compileall -q .
python -m pytest -q
```

Current expected result for this source package:

```text
89 passed
```

## Validate a decrypted save

```bat
python tools\validate_memory_dat.py path\to\memory.dat
```

The validator checks slot summaries, inventory anchors, row counts, free entries, and no-edit roundtrip behavior.

## Rebuild bundled database JSON

The bundled JSON files are already included. To rebuild them from the raw CSV files:

```bat
python tools\build_gow2018_resources.py
```

Source CSVs live in `data/raw/`. Runtime JSON files live in `app/resources/database/`.

## Project layout

```text
app/core/                 Save parsing, inventory model, slot transfer, backups
app/ui/                   PyQt6 shell, themes, and tabs
app/resources/database/   Runtime item/slot/code JSON resources
data/raw/                 Raw community CSV resources used to rebuild JSON
docs/                     Safety, validation, and feature notes
tests/                    Regression tests
tools/                    Validation/audit/resource-build helpers
```

## Data sources

The bundled item, slot, and code resources were generated from the community God of War IDs spreadsheet tabs used during development:

- Item IDs
- Save Slot Starting Points
- Codes

## Usage notes

Always keep your original PS4 save backup. Work on decrypted `memory.dat`, then re-encrypt/resign using your normal save workflow outside this editor.
