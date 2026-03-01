@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

REM Start Elixir Macro using Python 3.14
pushd "%~dp0"

echo Starting Elixir Macro...
echo.

py -3.14 app.pyw
if !errorlevel! neq 0 (
    echo.
    echo Error: Failed to start Elixir Macro
    echo Please make sure Python 3.14 is installed and requirements are installed.
    echo Run install_requirements.bat first if you haven't already.
    popd
    pause
    exit /b 1
)

popd
