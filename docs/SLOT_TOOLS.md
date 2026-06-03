# Slot Tools

Slot Tools replaces the older separate Slot Transfer and Slot Backups pages.

A transferred slot becomes the **physical target slot you choose**. For example, copying a package originally exported from source slot 7 into target slot 12 makes it occupy slot 12 in the target save. The original source slot number is kept only as package provenance.

## Loaded save actions

Use these when the currently opened `memory.dat` is the source or target:

- **Backup Source** exports the selected source slot into `memory.dat.slot_backups/` as a `.gow2018slot` package. You are asked for a package label so backups do not all read like raw slot numbers.
- **Copy Within Save** stages a full slot-block copy from one slot to another inside the loaded save.
- **Copy Loaded → Other Save…** writes the selected source slot into another decrypted `memory.dat`, asks which physical target slot to replace in that other save, and creates a rollback `.bak` first.

## Other save → loaded save

Use these when you want to pull a slot out of another `memory.dat`:

- **Open Source Save** loads another decrypted save only as a source.
- **Copy Other Save Slot → Loaded Slot** stages that source slot into the selected loaded-save target slot shown in the same card.
- **Export Source Package** exports the selected source slot as a portable `.gow2018slot` package and asks for a package label.

## Saved slot packages

Packages listed here are the `.gow2018slot` files beside the loaded save.

- **Restore Selected → Loaded** stages the selected package into the selected target slot.
- **Restore Selected → Other Save…** writes the selected package into another decrypted `memory.dat`, asks which physical target slot to replace, and creates a rollback `.bak` first.
- **Import Package → Loaded** lets you choose any `.gow2018slot` file, even if it is not in the loaded save's backup folder.
- **Rename Package** changes the package display label only. It does not edit the slot bytes.

## Slot labels versus real save slots

The tool does **not** patch an unknown internal slot-number field inside the slot block. In the sample saves, the physical slot index is determined by the target block position in `memory.dat`; no stable internal “slot 7” field was found. That means the safe behavior is:

- target slot number = the physical slot you choose in the tool
- source slot number = provenance shown in package metadata
- package label = user-facing name to prevent confusing backups like “slot 7” copied into “slot 12”

Same-save and package-into-loaded operations are staged in memory. Use normal **Save** or **Save As** to write them after the change preview. Other-save operations write the target file immediately because that file is not open in the editor, so they create a rollback `.bak` first.
