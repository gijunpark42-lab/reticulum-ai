@echo off
rem Double-click starter for the local Ask runner (Windows).
rem Keeps the window open so you can read the log; close it to stop the runner.
cd /d "%~dp0"
node server.mjs
pause
