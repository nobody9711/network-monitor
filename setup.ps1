# Network Monitor Setup Script Wrapper

# Check if running as administrator
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "Please run this script as Administrator"
    Write-Host "Right-click the script and select 'Run as Administrator'"
    exit 1
}

# Check Python installation
try {
    $pythonVersion = python --version 2>&1
    if (-not $pythonVersion) {
        Write-Host "Python is not installed. Please install Python 3.8 or higher from:"
        Write-Host "https://www.python.org/downloads/"
        exit 1
    }
} catch {
    Write-Host "Python is not installed. Please install Python 3.8 or higher from:"
    Write-Host "https://www.python.org/downloads/"
    exit 1
}

# Run setup script
try {
    python setup.py
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Setup completed successfully!"
        Write-Host "You can now start the Network Monitor."
    } else {
        Write-Host "Setup failed. Please check the error messages above."
        exit 1
    }
} catch {
    Write-Host "Setup failed: $_"
    exit 1
} 