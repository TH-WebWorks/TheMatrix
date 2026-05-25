@echo off
cd /d "%~dp0"
python -m pip install -q -r requirements.txt
REM Borderless windowed fullscreen. For 4K TV: --display 1 (see --list-displays)
python main.py %*
