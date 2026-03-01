@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

pushd "%~dp0"

echo Installing dependencies for Elixir Macro...
echo.

echo Upgrading pip...
py -3.14 -m pip install --upgrade pip
if !errorlevel! neq 0 (
    echo.
    echo Error: Failed to upgrade pip
    popd
    pause
    exit /b 1
)

echo Installing requirements...
py -3.14 -m pip install -r requirements.txt
if !errorlevel! neq 0 (
    echo.
    echo Error: Failed to install requirements
    popd
    pause
    exit /b 1
)

echo.
echo Successfully installed all dependencies!

popd
pause
