@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%Start-YourNoteAI.ps1"

if errorlevel 1 (
  echo.
  echo YourNoteAI launcher failed.
  pause
)
