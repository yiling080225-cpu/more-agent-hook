@echo off
chcp 65001 >nul
cd /d "%~dp0"
python fedcli.py
pause
