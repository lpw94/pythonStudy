@echo off
REM Launch funeng_sync with the local Python 3.12 environment.
REM Why 3.12: ddddocr needs opencv-python, which has no Windows wheel for 3.13.
set "PY=E:\workBuddy\pythonStudy\.py312\python.exe"
cd /d "%~dp0"
"%PY%" -m funeng_sync.main
pause
