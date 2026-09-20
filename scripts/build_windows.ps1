$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

if (-not $env:VIRTUAL_ENV) {
    throw "Debe activar el entorno virtual antes de compilar."
}

Write-Host "Ejecutando pruebas..."
python -m pytest

Write-Host "Generando antsim.exe..."
python -m PyInstaller `
    --name antsim `
    --onefile `
    --console `
    --clean `
    --noconfirm `
    --paths .\src `
    --hidden-import numpy `
    .\src\antsim\cli\main.py

Write-Host "Comprobando el ejecutable..."
.\dist\antsim.exe doctor

if ($LASTEXITCODE -ne 0) {
    throw "El diagnóstico del ejecutable falló."
}

.\dist\antsim.exe simulate-dipole

if ($LASTEXITCODE -ne 0) {
    throw "La simulación del ejecutable falló."
}

Write-Host ""
Write-Host "Compilación completada correctamente."
Write-Host "Ejecutable: $projectRoot\dist\antsim.exe"