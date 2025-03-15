@echo off
setlocal enabledelayedexpansion

:: Set console title
title Network Monitor

:: Check if running with administrator privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Please run this script as Administrator
    echo Right-click on the script and select "Run as administrator"
    pause
    exit /b 1
)

:: Set paths
set "BASE_DIR=%~dp0"
set "VENV_DIR=%BASE_DIR%venv"
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
set "PIP_EXE=%VENV_DIR%\Scripts\pip.exe"
set "CONFIG_FILE=%BASE_DIR%config.yml"
set "SETUP_SCRIPT=%BASE_DIR%setup.py"

:: Check if virtual environment exists
if not exist "%VENV_DIR%" (
    echo Virtual environment not found. Running setup script...
    python "%SETUP_SCRIPT%"
    if !errorLevel! neq 0 (
        echo Setup failed. Please check the error messages above.
        pause
        exit /b 1
    )
)

:: Activate virtual environment
call "%VENV_DIR%\Scripts\activate.bat"
if !errorLevel! neq 0 (
    echo Failed to activate virtual environment
    pause
    exit /b 1
)

:: Check if config file exists
if not exist "%CONFIG_FILE%" (
    echo Configuration file not found. Running setup script...
    python "%SETUP_SCRIPT%"
    if !errorLevel! neq 0 (
        echo Setup failed. Please check the error messages above.
        pause
        exit /b 1
    )
)

:: Check services
echo Checking required services...
for %%s in (MongoDB InfluxDB Unbound) do (
    sc query "%%s" >nul 2>&1
    if !errorLevel! neq 0 (
        echo Service %%s is not running. Starting...
        net start "%%s" >nul 2>&1
        if !errorLevel! neq 0 (
            echo Failed to start %%s service. Please start it manually.
        )
    )
)

:: Run the application
echo Starting Network Monitor...
cd "%BASE_DIR%"
python src/main.py

:: Keep the window open if there's an error
if !errorLevel! neq 0 (
    echo Application exited with error code !errorLevel!
    pause
)

deactivate
endlocal 