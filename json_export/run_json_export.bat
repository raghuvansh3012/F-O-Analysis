@echo off
echo ============================================================
echo    F^&O Analysis - JSON Export Tool
echo ============================================================
echo.

cd /d "%~dp0"
python generate_json_report.py %*

echo.
pause
