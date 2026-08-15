@echo off
chcp 65001 >nul
title 联合测绘PDF报告检查系统
cd /d "%~dp0"
"C:\Program Files\Python312\python.exe" main.py
pause
