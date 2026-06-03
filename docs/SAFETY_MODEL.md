# Safety Model

GoW Save Lab uses staged editing. UI actions mutate the in-memory save buffer first. Save and Save As then show a change preview and write through an atomic replace path with rollback backups.

## Inventory safety

- Inventory/resource writes require the XP table anchor to be present.
- Unknown/system rows are locked by default.
- Advanced Unlock allows quantity edits on locked rows but does not allow removal.
- Max All skips locked/system rows.
- Existing record metadata/flag bytes are preserved.
- New records are zero-initialized before item ID and quantity are written.

## Slot safety

- Slot transfers replace only the selected physical slot block.
- Empty/all-zero slot packages are refused.
- `.gow2018slot` packages include metadata and the raw slot block.
- Same-save slot copies are staged until normal Save/Save As.
- Other-save slot copies create rollback backups before writing.

## Core values

XP and Hacksilver are resolved through inventory/resource item IDs where possible, so Dashboard and Inventory stay synchronized across saves where row positions differ.
