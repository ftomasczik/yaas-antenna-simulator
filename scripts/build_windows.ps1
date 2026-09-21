$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

if (-not $env:VIRTUAL_ENV) {
    throw "Debe activar el entorno virtual antes de compilar."
}

Write-Host "Ejecutando pruebas..."
python -m pytest

if ($LASTEXITCODE -ne 0) {
    throw "Las pruebas automáticas fallaron."
}

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

if ($LASTEXITCODE -ne 0) {
    throw "La generación del ejecutable falló."
}

Write-Host "Comprobando el diagnóstico..."
& .\dist\antsim.exe doctor

if ($LASTEXITCODE -ne 0) {
    throw "El diagnóstico del ejecutable falló."
}

Write-Host "Comprobando la simulación simple..."
& .\dist\antsim.exe simulate-dipole

if ($LASTEXITCODE -ne 0) {
    throw "La simulación simple del ejecutable falló."
}

$smokeCsv = Join-Path `
    $projectRoot `
    "dist\antsim-smoke-sweep.csv"

try {
    Write-Host "Comprobando el barrido y la exportación CSV..."

    & .\dist\antsim.exe `
        sweep-dipole `
        --start 13.5 `
        --stop 15.5 `
        --points 21 `
        --swr-limit 2 `
        --output $smokeCsv

    if ($LASTEXITCODE -ne 0) {
        throw "El barrido del ejecutable falló."
    }

    if (-not (Test-Path $smokeCsv)) {
        throw "El ejecutable no generó el archivo CSV."
    }

    $csvLines = Get-Content $smokeCsv

    if ($csvLines.Count -ne 22) {
        throw (
            "El CSV debería contener 22 líneas " +
            "y contiene $($csvLines.Count)."
        )
    }
}
finally {
    if (Test-Path $smokeCsv) {
        Remove-Item $smokeCsv
    }
}

Write-Host ""
Write-Host "Compilación completada correctamente."
Write-Host "Ejecutable: $projectRoot\dist\antsim.exe"