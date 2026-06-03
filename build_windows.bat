@echo off
setlocal
cd /d "%~dp0"
if not exist .venv (
    py -3 -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
python -m compileall -q .
python -m pytest -q
pyinstaller --clean --noconfirm gow_save_lab.spec
echo.
echo Build complete: dist\GoWSaveLab.exe
