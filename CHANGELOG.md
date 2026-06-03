# Changelog

## 0.9.9 - Single-exe repo cleanup

- Removed extra run/verify helper scripts and the standalone build markdown file.
- Kept a single Windows build helper plus the PyInstaller spec.
- Documented that `gow_save_lab.spec` is configured for one-file output: `dist\GoWSaveLab.exe`.


## 0.9.8 - Git-ready cleanup

- Removed local validation/sample-save references from repository docs and scripts.
- Converted the value-search helper into a CLI tool with no hardcoded local paths.
- Expanded `.gitignore` for save files, backups, release zips, patches, logs, and build artifacts.
- Kept the experimental inventory append feature unchanged.
- Verified the clean source tree with `compileall`, resource rebuild, and the test suite.

## 0.9.7 - Experimental inventory append

- Added an Experimental append mode in Add Items for testing saves with no free inventory records.
- Added Add All Visible so filtered database rows can be staged in bulk.
- Core inventory writes can now preserve/read known item rows beyond the original 256-row scan window.
- Normal mode still refuses full-slot allocations; experimental mode writes after the detected item table and can corrupt saves.

## 0.9.6 - Add Items owned quantity clarity

- Renamed the Add Items ownership column to **You Have** and moved it next to the item name so existing quantities are visible before pressing Add.
- Added an Add Action column that explains whether an item will stack, use a new row, or cannot fit because the slot table is full.
- Added a persistent Open item slots chip in the Add Items action row.
- Updated selected-item detail text to show current owned quantity, duplicate row count, add behavior, and remaining open item slots.

## 0.9.5 - Add Items ownership/capacity display

- Added an Open Slots chip to the Add Items page so the active slot capacity is visible before adding a new row.
- Added an Owned column to the item database so each addable item shows the active slot's current quantity.
- Owned quantities aggregate duplicate records and update from staged inventory edits.
- Updated selected-item detail text to explain whether Add Selected will stack onto an existing row or require a new open slot.

## 0.9.4 - Inventory database metadata repair

- Normalized ItemIDs resources so rows missing Clean Name/Type display readable resources.dcb fallback names instead of blank/Unknown.
- Added inferred categories for armor, perks, weapon upgrades, bestiary/progression, lore, tutorials, and technical rows.
- Kept inferred rows locked by default; Advanced Unlock is still required for manual edits on risky/system rows.
- Hid truly unknown/system save rows by default so the Inventory tab opens on useful known rows instead of a wall of Unknown values.
- Added regression checks so known resources/armor resolve through the database.


## 0.9.3 - Slot Tools clarity and package labels

- Added package display labels for `.gow2018slot` backups/exports so source-slot provenance is not confused with the destination slot.
- Added a Rename Package action for saved slot packages.
- Made Other Save -> Loaded Save transfers show their own loaded target-slot selector.
- Copying/restoring into another save now asks for the target slot after choosing the target `memory.dat`, instead of silently using the loaded-save target combo.
- Added clearer confirmation/status text that the save-menu slot is the selected physical target slot, not the original source slot stored in package metadata.

## 0.9.2 - Consolidated Slot Tools

- Replaced the separate Slot Transfer and Slot Backups pages with one Slot Tools workspace.
- Added loaded-save slot backup, same-save slot copy, and copy-to-other-save actions in one place.
- Added source-save loading so a slot from another `memory.dat` can be copied directly into the loaded save.
- Added arbitrary `.gow2018slot` import into the loaded save from the same Slot Tools page.
- Removed the unused Slot Transfer UI tab while keeping the tested core slot-transfer package format and safety logic.
- Fixed the slot-tool restore callback so it no longer references an undefined path after a staged restore.

## 0.9.1 - Inventory responsiveness/search fix

- Moved Item Database search into the Add Items page so it is no longer confused with the Current Slot filter.
- Fixed database search to use indexed multi-term matching across name, type, file name, slot code, and technical ID.
- Stopped database search refreshes from rebuilding the Current Slot table.
- Split pending filter flushing so current-slot edit buttons no longer process database search timers.
- Replaced expensive automatic content-width table sizing with fixed interactive widths.
- Disabled QTableWidget sorting during normal inventory editing to avoid row-index churn and click lag.
- Added source regression tests for the inventory search/performance wiring.

## 0.9.0 - Build polish pass

- Added central app metadata in `app/__about__.py`.
- Added persistent theme, window layout, current page, last folder, and recent-save menu support.
- Added source-level regression tests for settings/recent-file wiring.
- Kept save offsets, inventory writes, slot transfer, and slot backup behavior unchanged.


## Clean build package

- Consolidated the working tree into a clean project root: `GoW-Save-Lab`.
- Removed one-off pass notes and old validation scratch files from the root.
- Added `requirements.txt`, `requirements-dev.txt`, `.gitignore`, build scripts, and a clean PyInstaller spec.
- Added package `__init__.py` files for cleaner imports/build behavior.
- Updated README and build documentation.
- Preserved the current feature set: modern UI, inventory editor, Advanced Unlock, slot backups, slot transfer, hex editor, save preview, atomic backups, and performance fixes.
