@echo off
REM Launch funeng_sync with the local Python 3.12 environment.
REM Why 3.12: ddddocr needs opencv-python, which has no Windows wheel for 3.13.
REM
REM funeng_sync.main was removed during the teaching-trim phase, so this runs
REM the modules that actually exist today:
REM   (no arg)  login      - captcha -> OCR -> exchange token
REM   data      meter_data - login + fetch meter readings and print them
REM   excel     meter_data --excel - the same, plus an .xlsx export
REM
REM Usage:  run.bat [login|data|excel]
set "PY=E:\workBuddy\pythonStudy\.py312\python.exe"
cd /d "%~dp0"

if "%~1"=="data" (
    "%PY%" -m funeng_sync.meter_data
) else if "%~1"=="excel" (
    "%PY%" -m funeng_sync.meter_data --excel
) else (
    "%PY%" -m funeng_sync.login
)
pause
