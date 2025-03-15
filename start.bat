@echo off
setlocal enabledelayedexpansion

:: Set color codes for output messages
set "RED=[91m"
set "GREEN=[92m"
set "YELLOW=[93m"
set "RESET=[0m"

echo %GREEN%Starting Network Monitor Setup...%RESET%

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo %RED%Error: Python is not installed or not in PATH%RESET%
    echo Please install Python 3.8 or later from https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Check if virtual environment exists, create if not
if not exist venv (
    echo %YELLOW%Creating virtual environment...%RESET%
    python -m venv venv
    if %errorlevel% neq 0 (
        echo %RED%Error: Failed to create virtual environment%RESET%
        pause
        exit /b 1
    )
)

:: Activate virtual environment
call venv\Scripts\activate
if %errorlevel% neq 0 (
    echo %RED%Error: Failed to activate virtual environment%RESET%
    pause
    exit /b 1
)

:: Install/upgrade pip
python -m pip install --upgrade pip
if %errorlevel% neq 0 (
    echo %YELLOW%Warning: Failed to upgrade pip, continuing with existing version%RESET%
)

:: Install requirements
echo %YELLOW%Installing requirements...%RESET%
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo %RED%Error: Failed to install requirements%RESET%
    pause
    exit /b 1
)

:: Create necessary directories
if not exist "%PROGRAMDATA%\NetworkMonitor\logs" (
    mkdir "%PROGRAMDATA%\NetworkMonitor\logs"
)
if not exist "%PROGRAMDATA%\NetworkMonitor\temp" (
    mkdir "%PROGRAMDATA%\NetworkMonitor\temp"
)

:: Check for config file
if not exist config.yml (
    if exist config.example.yml (
        echo %YELLOW%Creating config.yml from example...%RESET%
        copy config.example.yml config.yml
    ) else (
        echo %RED%Error: config.example.yml not found%RESET%
        pause
        exit /b 1
    )
)

:: Check if MongoDB is installed
sc query MongoDB >nul 2>&1
if %errorlevel% neq 0 (
    echo %RED%Error: MongoDB service not found%RESET%
    echo Please install MongoDB Community Edition:
    echo 1. Download MongoDB Community Server from:
    echo    https://www.mongodb.com/try/download/community
    echo 2. Run the installer and select "Complete" installation
    echo 3. Make sure to install MongoDB as a service
    echo 4. After installation, run this script again
    pause
    exit /b 1
)

:: Check MongoDB service
net start MongoDB >nul 2>&1
if %errorlevel% neq 0 (
    echo %YELLOW%Warning: MongoDB service not running. Attempting to start...%RESET%
    net start MongoDB >nul 2>&1
    if %errorlevel% neq 0 (
        echo %RED%Error: Failed to start MongoDB service%RESET%
        echo Please ensure MongoDB service is properly installed:
        echo 1. Open Services (services.msc)
        echo 2. Find "MongoDB" service
        echo 3. Set Startup type to "Automatic"
        echo 4. Start the service manually
        echo 5. Run this script again
        pause
        exit /b 1
    )
)

:: Check if InfluxDB is installed
sc query influxdb >nul 2>&1
if %errorlevel% neq 0 (
    echo %RED%Error: InfluxDB service not found%RESET%
    echo Please install InfluxDB:
    echo 1. Download InfluxDB from:
    echo    https://portal.influxdata.com/downloads/
    echo 2. Run the installer
    echo 3. Make sure to install InfluxDB as a service
    echo 4. After installation, run this script again
    pause
    exit /b 1
)

:: Check InfluxDB service
net start influxdb >nul 2>&1
if %errorlevel% neq 0 (
    echo %YELLOW%Warning: InfluxDB service not running. Attempting to start...%RESET%
    net start influxdb >nul 2>&1
    if %errorlevel% neq 0 (
        echo %RED%Error: Failed to start InfluxDB service%RESET%
        echo Please ensure InfluxDB service is properly installed:
        echo 1. Open Services (services.msc)
        echo 2. Find "influxdb" service
        echo 3. Set Startup type to "Automatic"
        echo 4. Start the service manually
        echo 5. Run this script again
        pause
        exit /b 1
    )
)

:: Start the application
echo %GREEN%Starting Network Monitor...%RESET%
if exist src\main.py (
    python src\main.py
    if %errorlevel% neq 0 (
        echo %RED%Error: Application crashed or failed to start%RESET%
        echo Check the logs in %PROGRAMDATA%\NetworkMonitor\logs for details
        pause
        exit /b 1
    )
) else (
    echo %RED%Error: src\main.py not found%RESET%
    pause
    exit /b 1
)

endlocal 