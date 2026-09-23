$ErrorActionPreference = "Stop"
$utf8Encoding = [System.Text.UTF8Encoding]::new(
    $false
)

[Console]::InputEncoding = $utf8Encoding
[Console]::OutputEncoding = $utf8Encoding
$OutputEncoding = $utf8Encoding
$env:PYTHONIOENCODING = "utf-8"

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
    --add-data "src\antsim\locales;antsim\locales" `
    .\src\antsim\cli\main.py

if ($LASTEXITCODE -ne 0) {
    throw "La generación del ejecutable falló."
}

Write-Host "Comprobando el diagnóstico en español..."

$spanishDoctor = (
    & .\dist\antsim.exe `
        --language es `
        doctor |
        Out-String
)

if ($LASTEXITCODE -ne 0) {
    throw "El diagnóstico en español falló."
}

Write-Host $spanishDoctor.TrimEnd()

if (-not $spanishDoctor.Contains("Entorno: OK")) {
    throw "El catálogo español no fue incluido correctamente."
}

Write-Host "Comprobando el diagnóstico en inglés..."

$englishDoctor = (
    & .\dist\antsim.exe `
        --language en `
        doctor |
        Out-String
)

if ($LASTEXITCODE -ne 0) {
    throw "El diagnóstico en inglés falló."
}

Write-Host $englishDoctor.TrimEnd()

if (-not $englishDoctor.Contains("Environment: OK")) {
    throw "La salida inglesa no es correcta."
}

Write-Host "Comprobando la simulación simple..."

& .\dist\antsim.exe `
    --language es `
    simulate-dipole

if ($LASTEXITCODE -ne 0) {
    throw "La simulación simple falló."
}

$smokeCsv = Join-Path `
    $projectRoot `
    "dist\antsim-smoke-sweep.csv"

try {
    Write-Host "Comprobando el barrido en español..."

    $spanishSweep = (
        & .\dist\antsim.exe `
            --language es `
            sweep-dipole `
            --start 13.5 `
            --stop 15.5 `
            --points 21 `
            --swr-limit 2 `
            --output $smokeCsv |
            Out-String
    )

    if ($LASTEXITCODE -ne 0) {
        throw "El barrido en español falló."
    }

    Write-Host $spanishSweep.TrimEnd()

    if (-not $spanishSweep.Contains("Barrido:")) {
        throw "El barrido no fue traducido al español."
    }

    if (-not $spanishSweep.Contains("Resonancia aproximada:")) {
        throw "Falta la traducción de resonancia."
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

    Write-Host "Comprobando el barrido en inglés..."

    $englishSweep = (
        & .\dist\antsim.exe `
            --language en `
            sweep-dipole `
            --start 13.5 `
            --stop 15.5 `
            --points 21 `
            --swr-limit 2 |
            Out-String
    )

    if ($LASTEXITCODE -ne 0) {
        throw "El barrido en inglés falló."
    }

    Write-Host $englishSweep.TrimEnd()

    if (-not $englishSweep.Contains("Sweep:")) {
        throw "La salida inglesa del barrido no es correcta."
    }

    if (
        -not $englishSweep.Contains(
            "Approximate resonance:"
        )
    ) {
        throw "Falta el encabezado inglés de resonancia."
    }
}
finally {
    if (Test-Path $smokeCsv) {
        Remove-Item $smokeCsv
    }
}

$exampleProject = Join-Path `
    $projectRoot `
    "examples\dipole-20m.antsim"

$projectSmokeCsv = Join-Path `
    $projectRoot `
    "dist\antsim-project-smoke-sweep.csv"

if (-not (Test-Path $exampleProject)) {
    throw "No se encontró el proyecto de ejemplo."
}

try {
    Write-Host "Validando un proyecto en español..."

    $spanishValidation = (
        & .\dist\antsim.exe `
            --language es `
            validate $exampleProject |
            Out-String
    )

    if ($LASTEXITCODE -ne 0) {
        throw "La validación del proyecto falló."
    }

    Write-Host $spanishValidation.TrimEnd()

    if (
        -not $spanishValidation.Contains(
            "Conductores: 1"
        )
    ) {
        throw "La validación no produjo la salida esperada."
    }

    Write-Host "Validando un proyecto en inglés..."

    $englishValidation = (
        & .\dist\antsim.exe `
            --language en `
            validate $exampleProject |
            Out-String
    )

    if ($LASTEXITCODE -ne 0) {
        throw "La validación inglesa del proyecto falló."
    }

    if (
        -not $englishValidation.Contains(
            "Valid project:"
        )
    ) {
        throw "La validación inglesa no es correcta."
    }

    Write-Host "Simulando un proyecto..."

    $projectSimulation = (
        & .\dist\antsim.exe `
            --language es `
            simulate $exampleProject |
            Out-String
    )

    if ($LASTEXITCODE -ne 0) {
        throw "La simulación del proyecto falló."
    }

    Write-Host $projectSimulation.TrimEnd()

    if (
        -not $projectSimulation.Contains(
            "Simulando proyecto:"
        )
    ) {
        throw "Falta el encabezado de simulación."
    }

    if (
        -not $projectSimulation.Contains(
            "Impedancia:"
        )
    ) {
        throw "Falta la impedancia de la simulación."
    }

    Write-Host "Ejecutando el barrido de un proyecto..."

    $projectSweep = (
        & .\dist\antsim.exe `
            --language es `
            sweep $exampleProject `
            --output $projectSmokeCsv |
            Out-String
    )

    if ($LASTEXITCODE -ne 0) {
        throw "El barrido del proyecto falló."
    }

    Write-Host $projectSweep.TrimEnd()

    if (
        -not $projectSweep.Contains(
            "Ejecutando barrido del proyecto:"
        )
    ) {
        throw "Falta el encabezado del barrido."
    }

    if (-not (Test-Path $projectSmokeCsv)) {
        throw "El barrido no generó el archivo CSV."
    }

    $projectCsvLines = Get-Content $projectSmokeCsv

    if ($projectCsvLines.Count -lt 2) {
        throw "El CSV del proyecto no contiene datos."
    }
}
finally {
    if (Test-Path $projectSmokeCsv) {
        Remove-Item $projectSmokeCsv
    }
}

Write-Host ""
Write-Host "Compilación completada correctamente."
Write-Host "Ejecutable: $projectRoot\dist\antsim.exe"