# SAMPSON Windows Build Script
# Run from repo root in a Python environment with dependencies installed:
#   pip install -r requirements.txt pyinstaller
#   .\build_windows.ps1

$ErrorActionPreference = "Stop"

$VERSION = Select-String -Path "SAMPSON_win.spec" -Pattern "CFBundleShortVersionString" |
    ForEach-Object { $_ -match "[\d]+\.[\d]+\.[\d]+" | Out-Null; $Matches[0] }

# Fallback: read version from ui/index.html
if (-not $VERSION) {
    $versionLine = Select-String -Path "ui\index.html" -Pattern "v\d+\.\d+\.\d+"
    if ($versionLine -match "v(\d+\.\d+\.\d+)") { $VERSION = $Matches[1] }
}

if (-not $VERSION) { $VERSION = "0.0.0" }

Write-Host "[ 1/3 ] Building SAMPSON v$VERSION for Windows..."
pyinstaller SAMPSON_win.spec --clean -y

Write-Host "[ 2/3 ] Packaging..."
$zipName = "SAMPSON_win_v$VERSION.zip"
Compress-Archive -Path "dist\SAMPSON.exe" -DestinationPath "dist\$zipName" -Force

Write-Host "[ 3/3 ] Done — dist\$zipName"
