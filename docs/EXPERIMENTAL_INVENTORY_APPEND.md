# Experimental Inventory Append

This build includes an intentionally risky inventory test mode.

Normal inventory allocation only uses existing free records inside the known inventory/resource table. When a save reports zero free records, normal mode refuses brand-new items because expanding the table without knowing every game-side count/pointer can corrupt the save.

`Experimental append` changes that behavior for testing:

- `Add Selected` can stage a new row after the detected item table when no free record exists.
- `Add All Visible` stages every currently visible database row, stacking existing rows when `Stack existing` is enabled.
- The normal Save Preview and backup system still run before writing to disk.
- This can overwrite unknown slot data after the detected table. Use only on copies of decrypted saves.

The reader now also detects known database-backed rows that appear after the original 256-row scan window. This is separate from experimental append and helps saves that already have larger item tables display more correctly.
