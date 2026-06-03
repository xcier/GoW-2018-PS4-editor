# Validation

Run the project checks from the repository root:

```text
python -m compileall -q .
python tools/build_gow2018_resources.py
python -m pytest -q
```

Current expected source-tree result:

```text
89 passed
```

To validate a local decrypted save without committing it to Git:

```text
python tools/validate_memory_dat.py path/to/memory.dat
```

The validator checks:

- newest active slot detection
- slot summary parsing
- inventory/resource anchor detection
- inventory row counts and free-row counts
- no-edit core roundtrip stability

Do not commit decrypted saves, slot backups, rollback backups, or test save artifacts.
