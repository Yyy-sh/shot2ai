@echo off
chcp 65001 >nul
cd /d "%~dp0"
call conda activate offer-screenshot
python main.py
pause
