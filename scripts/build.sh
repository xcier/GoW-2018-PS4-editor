#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
python -m compileall -q .
python -m pytest -q
pyinstaller --clean --noconfirm gow_save_lab.spec
echo "Build complete: dist/GoWSaveLab"
