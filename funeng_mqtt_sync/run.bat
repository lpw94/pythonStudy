@echo off
REM Launch funeng_sync with the local Python 3.12 environment.
REM Why 3.12: ddddocr needs opencv-python, which has no Windows wheel for 3.13.
REM
REM funeng_sync.main was removed during the teaching-trim phase, so this now
REM runs the login flow (captcha -> OCR -> exchange token) - the part that
REM actually exists today.
set "PY=E:\workBuddy\pythonStudy\.py312\python.exe"
cd /d "%~dp0"
"%PY%" -m funeng_sync.login
pause
