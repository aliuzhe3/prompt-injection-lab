@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
title Upload to GitHub
echo ============================================
echo    Upload project to GitHub
echo ============================================
echo.
D:\Anaconda3\python.exe "%~dp0upload_github.py" --interactive
echo.
echo --------------------------------------------
pause
