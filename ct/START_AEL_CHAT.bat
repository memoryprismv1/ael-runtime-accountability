@echo off
cd /d "%~dp0"
python "%~dp0ael_chat.py" %*
if errorlevel 1 pause
