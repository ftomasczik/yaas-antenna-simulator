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

$staleAntsimExe = Join-Path $projectRoot "dist\antsim.exe"
if (Test-Path $staleAntsimExe) {
    Write-Host "Eliminando residuo de la build anterior (antsim.exe)..."
    Remove-Item $staleAntsimExe -Force
}

Write-Host "Generando yaas.exe..."
python -m PyInstaller `
    --name yaas `
    --onefile `
    --console `
    --clean `
    --noconfirm `
    --paths .\src `
    --hidden-import numpy `
    --add-data "src\yaas\locales;yaas\locales" `
    .\src\yaas\cli\main.py

if ($LASTEXITCODE -ne 0) {
    throw "La generación del ejecutable falló."
}

# Helpers para los smoke tests que siguen. Comparaciones ASCII-seguras
# a proposito (ver el resto de este script): un literal con tilde en
# una comparacion .Contains() puede no coincidir con la salida
# capturada del ejecutable bajo PowerShell 5.1.
function Invoke-YaasCli {
    param(
        [Parameter(Mandatory)][string[]]$CliArgs,
        [Parameter(Mandatory)][string]$FailureMessage
    )
    $output = (& .\dist\yaas.exe @CliArgs | Out-String)
    if ($LASTEXITCODE -ne 0) {
        throw $FailureMessage
    }
    return $output
}

function Assert-TextContains {
    param(
        [Parameter(Mandatory)][string]$Text,
        [Parameter(Mandatory)][string]$Substring,
        [Parameter(Mandatory)][string]$FailureMessage
    )
    if (-not $Text.Contains($Substring)) {
        throw $FailureMessage
    }
}

function Assert-TextExcludes {
    param(
        [Parameter(Mandatory)][string]$Text,
        [Parameter(Mandatory)][string]$Substring,
        [Parameter(Mandatory)][string]$FailureMessage
    )
    if ($Text.Contains($Substring)) {
        throw $FailureMessage
    }
}

function Assert-NoLineStartsWith {
    param(
        [Parameter(Mandatory)][string[]]$Lines,
        [Parameter(Mandatory)][string]$Prefix,
        [Parameter(Mandatory)][string]$FailureMessage
    )
    if ($Lines | Where-Object { $_.StartsWith($Prefix) }) {
        throw $FailureMessage
    }
}

function Assert-NecCardOrder {
    # Verifica que cada tarjeta en $OrderedCards exista en $Lines y
    # aparezca estrictamente despues de la anterior de la lista.
    param(
        [Parameter(Mandatory)][string[]]$Lines,
        [Parameter(Mandatory)][string[]]$OrderedCards,
        [Parameter(Mandatory)][string]$Context
    )
    $previousIndex = -1
    foreach ($card in $OrderedCards) {
        $index = [array]::IndexOf($Lines, $card)
        if ($index -lt 0) {
            throw "$Context no contiene la tarjeta esperada: $card"
        }
        if ($index -le $previousIndex) {
            throw "$Context no respeta el orden esperado en: $card"
        }
        $previousIndex = $index
    }
}

function Assert-GnCardFields {
    # Encuentra la unica tarjeta GN, la separa por espacios y compara
    # sus campos posicion por posicion contra $ExpectedFields (por
    # ejemplo, I1-I4 seguidos de F1-F6): no se limita a comprobar que
    # ciertos valores aparezcan en algun lado del archivo. Reutilizable
    # para futuros perfiles de suelo pasando un -ExpectedFields
    # distinto, sin generalizar mas alla de eso.
    param(
        [Parameter(Mandatory)][string[]]$Lines,
        [Parameter(Mandatory)][string[]]$ExpectedFields,
        [Parameter(Mandatory)][string]$Context
    )
    $gnLines = @($Lines | Where-Object { $_.StartsWith("GN ") })
    if ($gnLines.Count -ne 1) {
        throw (
            "$Context deberia contener exactamente una tarjeta GN " +
            "y contiene $($gnLines.Count)."
        )
    }

    $tokens = $gnLines[0] -split "\s+"
    if ($tokens[0] -ne "GN") {
        throw "${Context}: el primer token de la tarjeta GN no es 'GN'."
    }

    $actualFields = $tokens[1..($tokens.Count - 1)]
    if ($actualFields.Count -ne $ExpectedFields.Count) {
        throw (
            "${Context}: la tarjeta GN deberia tener " +
            "$($ExpectedFields.Count) campos despues de 'GN' " +
            "y tiene $($actualFields.Count)."
        )
    }

    for ($index = 0; $index -lt $ExpectedFields.Count; $index++) {
        if ($actualFields[$index] -ne $ExpectedFields[$index]) {
            throw (
                "${Context}: el campo $($index + 1) de la tarjeta GN " +
                "deberia ser '$($ExpectedFields[$index])' y es " +
                "'$($actualFields[$index])'."
            )
        }
    }
}

Write-Host "Comprobando el diagnóstico en español..."

$spanishDoctor = (
    & .\dist\yaas.exe `
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
    & .\dist\yaas.exe `
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

& .\dist\yaas.exe `
    --language es `
    simulate-dipole

if ($LASTEXITCODE -ne 0) {
    throw "La simulación simple falló."
}

$smokeCsv = Join-Path `
    $projectRoot `
    "dist\yaas-smoke-sweep.csv"

try {
    Write-Host "Comprobando el barrido en español..."

    $spanishSweep = (
        & .\dist\yaas.exe `
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
        & .\dist\yaas.exe `
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
    "examples\dipole-20m.yaas"

$projectSmokeCsv = Join-Path `
    $projectRoot `
    "dist\yaas-project-smoke-sweep.csv"

if (-not (Test-Path $exampleProject)) {
    throw "No se encontró el proyecto de ejemplo."
}

try {
    Write-Host "Validando un proyecto en español..."

    $spanishValidation = (
        & .\dist\yaas.exe `
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

    Assert-TextContains -Text $spanishValidation -Substring "esquema: 1" `
        -FailureMessage (
            "El proyecto de ejemplo v1 dejo de leerse como " +
            "schema_version 1."
        )

    Write-Host "Validando un proyecto en inglés..."

    $englishValidation = (
        & .\dist\yaas.exe `
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
        & .\dist\yaas.exe `
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
        & .\dist\yaas.exe `
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

$necSmokeFile = Join-Path `
    $projectRoot `
    "dist\yaas-smoke-export.nec"

try {
    Write-Host "Comprobando la exportación NEC..."

    $spanishNecExport = (
        & .\dist\yaas.exe `
            --language es `
            export-nec `
            $exampleProject `
            $necSmokeFile |
            Out-String
    )

    if ($LASTEXITCODE -ne 0) {
        throw "La exportación NEC falló."
    }

    Write-Host $spanishNecExport.TrimEnd()

    if (
        -not $spanishNecExport.Contains(
            "Archivo NEC:"
        )
    ) {
        throw "La salida española de export-nec es incorrecta."
    }

    if (-not (Test-Path $necSmokeFile)) {
        throw "El ejecutable no generó el archivo NEC."
    }

    $necLines = Get-Content $necSmokeFile

    if ($necLines.Count -ne 9) {
        throw (
            "El archivo NEC debería contener 9 líneas " +
            "y contiene $($necLines.Count)."
        )
    }

    if (
        $necLines -notcontains
        "CM Reference impedance: 50 ohm"
    ) {
        throw (
            "El archivo NEC no contiene el comentario de " +
            "impedancia de referencia esperado."
        )
    }

    if (
        $necLines -notcontains
        "GW 1 101 -5.03 0 0 5.03 0 0 0.001"
    ) {
        throw "El archivo NEC no contiene la geometría esperada."
    }

    if ($necLines -notcontains "EX 0 1 51 0 1 0") {
        throw "El archivo NEC no contiene la fuente esperada."
    }

    if (
        $necLines -notcontains
        "FR 0 1 0 0 14.15 0"
    ) {
        throw "El archivo NEC no contiene la frecuencia esperada."
    }

    Assert-NecCardOrder -Lines $necLines -OrderedCards @("GE 0") `
        -Context "El archivo NEC del proyecto v1 (espacio libre)"

    Assert-NoLineStartsWith -Lines $necLines -Prefix "GN " `
        -FailureMessage (
            "El proyecto v1 (espacio libre) no deberia exportar " +
            "ninguna tarjeta GN."
        )

    if ($necLines[-1] -ne "EN") {
        throw "El archivo NEC no termina con la tarjeta EN."
    }

    Write-Host "Comprobando export-nec en inglés..."

    $englishNecExport = (
        & .\dist\yaas.exe `
            --language en `
            export-nec `
            $exampleProject `
            $necSmokeFile |
            Out-String
    )

    if ($LASTEXITCODE -ne 0) {
        throw "La exportación NEC en inglés falló."
    }

    if (
        -not $englishNecExport.Contains(
            "NEC file:"
        )
    ) {
        throw "La salida inglesa de export-nec es incorrecta."
    }
        Write-Host "Comprobando la exportación NEC del barrido..."

    $sweepNecExport = (
        & .\dist\yaas.exe `
            --language es `
            export-nec `
            --sweep `
            $exampleProject `
            $necSmokeFile |
            Out-String
    )

    if ($LASTEXITCODE -ne 0) {
        throw "La exportación NEC del barrido falló."
    }

    Write-Host $sweepNecExport.TrimEnd()

    if (-not (Test-Path $necSmokeFile)) {
        throw "No se generó el archivo NEC del barrido."
    }

    $sweepNecLines = Get-Content $necSmokeFile

    $sweepFrequencyCard = (
        $sweepNecLines |
        Where-Object {
            $_.StartsWith("FR ")
        }
    )

    if ($null -eq $sweepFrequencyCard) {
        throw "El barrido NEC no contiene una tarjeta FR."
    }

    if (
        $sweepFrequencyCard.StartsWith(
            "FR 0 1 "
        )
    ) {
        throw (
            "La tarjeta FR contiene una sola frecuencia " +
            "en lugar de un barrido."
        )
    }

    $frequencyParts = (
        $sweepFrequencyCard -split "\s+"
    )

    if ($frequencyParts.Count -ne 7) {
        throw "La tarjeta FR del barrido no es válida."
    }

    $sweepPointCount = [int]$frequencyParts[2]

    if ($sweepPointCount -le 1) {
        throw (
            "El barrido NEC debe contener más " +
            "de una frecuencia."
        )
    }

    if ($sweepNecLines[-1] -ne "EN") {
        throw "El barrido NEC no termina con EN."
    }
}


finally {
    if (Test-Path $necSmokeFile) {
        Remove-Item $necSmokeFile
    }
}

$perfectGroundProject = Join-Path `
    $projectRoot `
    "examples\monopole-20m-perfect-ground.yaas"

$perfectGroundNecFile = Join-Path `
    $projectRoot `
    "dist\yaas-smoke-perfect-ground.nec"

$perfectGroundSweepNecFile = Join-Path `
    $projectRoot `
    "dist\yaas-smoke-perfect-ground-sweep.nec"

if (-not (Test-Path $perfectGroundProject)) {
    throw "No se encontro el proyecto de ejemplo de tierra perfecta."
}

try {
    Write-Host "Validando el monopolo sobre tierra perfecta (schema v2)..."
    $perfectGroundValidation = Invoke-YaasCli `
        -CliArgs @("--language", "es", "validate", $perfectGroundProject) `
        -FailureMessage "La validacion del monopolo sobre tierra perfecta fallo."
    Write-Host $perfectGroundValidation.TrimEnd()
    Assert-TextContains -Text $perfectGroundValidation -Substring "esquema: 2" `
        -FailureMessage "El monopolo no se valido como schema_version 2."
    Assert-TextContains -Text $perfectGroundValidation -Substring "Conductores: 1" `
        -FailureMessage "El monopolo no reporta un unico conductor."

    Write-Host "Simulando el monopolo sobre tierra perfecta..."
    $perfectGroundSimulation = Invoke-YaasCli `
        -CliArgs @("--language", "es", "simulate", $perfectGroundProject) `
        -FailureMessage "La simulacion del monopolo sobre tierra perfecta fallo."
    Write-Host $perfectGroundSimulation.TrimEnd()
    Assert-TextContains -Text $perfectGroundSimulation -Substring "Frecuencia: 14.150 MHz" `
        -FailureMessage "La frecuencia simulada del monopolo no es la esperada."
    Assert-TextContains -Text $perfectGroundSimulation -Substring "Impedancia: 33.79 -15.62j ohm" `
        -FailureMessage (
            "La impedancia simulada del monopolo no coincide con " +
            "el valor esperado de tierra perfecta."
        )
    Assert-TextContains -Text $perfectGroundSimulation -Substring "ROE respecto de 50 ohm: 1.72" `
        -FailureMessage "La ROE simulada del monopolo no coincide con el valor esperado."

    Write-Host "Ejecutando el barrido del monopolo sobre tierra perfecta..."
    $perfectGroundSweep = Invoke-YaasCli `
        -CliArgs @("--language", "es", "sweep", $perfectGroundProject) `
        -FailureMessage "El barrido del monopolo sobre tierra perfecta fallo."
    Write-Host $perfectGroundSweep.TrimEnd()
    Assert-TextContains -Text $perfectGroundSweep -Substring "Puntos: 81" `
        -FailureMessage "El barrido del monopolo no reporta 81 puntos."
    Assert-TextContains -Text $perfectGroundSweep -Substring "Frecuencia: 14.450 MHz" `
        -FailureMessage (
            "La resonancia aproximada del monopolo no coincide " +
            "con el valor esperado."
        )
    Assert-TextContains -Text $perfectGroundSweep -Substring "ROE: 1.38" `
        -FailureMessage "La ROE minima del monopolo no coincide con el valor esperado."
    Assert-TextContains -Text $perfectGroundSweep -Substring "Frecuencia: 14.500 MHz" `
        -FailureMessage (
            "La frecuencia de ROE minima del monopolo no coincide " +
            "con el valor esperado."
        )
    Assert-TextContains -Text $perfectGroundSweep -Substring "Ancho: 1025.0 kHz" `
        -FailureMessage "El ancho de banda del monopolo no coincide con el valor esperado."
    Assert-TextExcludes -Text $perfectGroundSweep -Substring "truncado" `
        -FailureMessage "El barrido del monopolo reporto un resultado truncado inesperado."

    Write-Host "Exportando NEC puntual del monopolo sobre tierra perfecta..."
    Invoke-YaasCli `
        -CliArgs @(
            "--language", "es", "export-nec",
            $perfectGroundProject, $perfectGroundNecFile
        ) `
        -FailureMessage "La exportacion NEC puntual del monopolo fallo." |
        Out-Null

    if (-not (Test-Path $perfectGroundNecFile)) {
        throw "No se genero el archivo NEC puntual del monopolo."
    }

    $perfectGroundNecLines = Get-Content $perfectGroundNecFile
    Assert-NecCardOrder -Lines $perfectGroundNecLines `
        -Context "El archivo NEC puntual del monopolo" `
        -OrderedCards @(
            "GE 1",
            "GN 1 0 0 0 0 0 0 0",
            "EX 0 1 1 0 1 0",
            "FR 0 1 0 0 14.15 0"
        )

    Write-Host "Exportando NEC de barrido del monopolo sobre tierra perfecta..."
    Invoke-YaasCli `
        -CliArgs @(
            "--language", "es", "export-nec", "--sweep",
            $perfectGroundProject, $perfectGroundSweepNecFile
        ) `
        -FailureMessage "La exportacion NEC de barrido del monopolo fallo." |
        Out-Null

    if (-not (Test-Path $perfectGroundSweepNecFile)) {
        throw "No se genero el archivo NEC de barrido del monopolo."
    }

    $perfectGroundSweepNecLines = Get-Content $perfectGroundSweepNecFile
    Assert-NecCardOrder -Lines $perfectGroundSweepNecLines `
        -Context "El archivo NEC de barrido del monopolo" `
        -OrderedCards @(
            "GE 1",
            "GN 1 0 0 0 0 0 0 0",
            "EX 0 1 1 0 1 0",
            "FR 0 81 0 0 13.5 0.025"
        )
}
finally {
    if (Test-Path $perfectGroundNecFile) {
        Remove-Item $perfectGroundNecFile
    }
    if (Test-Path $perfectGroundSweepNecFile) {
        Remove-Item $perfectGroundSweepNecFile
    }
}

$realGroundProject = Join-Path `
    $projectRoot `
    "examples\dipole-20m-real-ground.yaas"

$realGroundNecFile = Join-Path `
    $projectRoot `
    "dist\yaas-smoke-real-ground.nec"

$realGroundSweepNecFile = Join-Path `
    $projectRoot `
    "dist\yaas-smoke-real-ground-sweep.nec"

if (-not (Test-Path $realGroundProject)) {
    throw "No se encontro el proyecto de ejemplo de tierra real."
}

try {
    Write-Host "Validando el dipolo sobre tierra real (schema v3)..."
    $realGroundValidation = Invoke-YaasCli `
        -CliArgs @("--language", "es", "validate", $realGroundProject) `
        -FailureMessage "La validacion del dipolo sobre tierra real fallo."
    Write-Host $realGroundValidation.TrimEnd()
    Assert-TextContains -Text $realGroundValidation -Substring "esquema: 3" `
        -FailureMessage "El dipolo de tierra real no se valido como schema_version 3."
    Assert-TextContains -Text $realGroundValidation -Substring "Conductores: 1" `
        -FailureMessage "El dipolo de tierra real no reporta un unico conductor."

    Write-Host "Simulando el dipolo sobre tierra real..."
    $realGroundSimulation = Invoke-YaasCli `
        -CliArgs @("--language", "es", "simulate", $realGroundProject) `
        -FailureMessage "La simulacion del dipolo sobre tierra real fallo."
    Write-Host $realGroundSimulation.TrimEnd()
    Assert-TextContains -Text $realGroundSimulation -Substring "Frecuencia: 14.150 MHz" `
        -FailureMessage "La frecuencia simulada del dipolo de tierra real no es la esperada."
    Assert-TextContains -Text $realGroundSimulation -Substring "Impedancia: 66.57 -41.36j ohm" `
        -FailureMessage (
            "La impedancia simulada del dipolo de tierra real no coincide " +
            "con el valor validado externamente con 4nec2 " +
            "(docs/validation/real-ground-dipole-4nec2.md)."
        )
    Assert-TextContains -Text $realGroundSimulation -Substring "ROE respecto de 50 ohm: 2.13" `
        -FailureMessage "La ROE simulada del dipolo de tierra real no coincide con el valor esperado."

    Write-Host "Ejecutando el barrido del dipolo sobre tierra real..."
    $realGroundStopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    $realGroundSweep = Invoke-YaasCli `
        -CliArgs @("--language", "es", "sweep", $realGroundProject) `
        -FailureMessage "El barrido del dipolo sobre tierra real fallo."
    $realGroundStopwatch.Stop()
    Write-Host $realGroundSweep.TrimEnd()
    Write-Host (
        "Duracion del barrido de tierra real (81 puntos, contexto NEC2++ " +
        "nuevo por frecuencia): {0:N2} s" -f $realGroundStopwatch.Elapsed.TotalSeconds
    )
    # Solo se muestra la duracion; no se impone ningun limite temporal.
    Assert-TextContains -Text $realGroundSweep -Substring "13.500-15.500 MHz" `
        -FailureMessage "El rango del barrido de tierra real no es el esperado."
    Assert-TextContains -Text $realGroundSweep -Substring "Puntos: 81" `
        -FailureMessage "El barrido de tierra real no reporta 81 puntos."
    Assert-TextContains -Text $realGroundSweep -Substring "Frecuencia: 14.550 MHz" `
        -FailureMessage (
            "La resonancia aproximada del dipolo de tierra real no " +
            "coincide con el valor esperado."
        )
    Assert-TextContains -Text $realGroundSweep -Substring "Impedancia: 70.40 -1.00j ohm" `
        -FailureMessage (
            "La impedancia en la resonancia del dipolo de tierra real " +
            "no coincide con el valor esperado."
        )
    Assert-TextContains -Text $realGroundSweep -Substring "ROE: 1.41" `
        -FailureMessage "La ROE minima del dipolo de tierra real no coincide con el valor esperado."
    Assert-TextContains -Text $realGroundSweep -Substring "Ancho: 700.0 kHz" `
        -FailureMessage "El ancho de banda del dipolo de tierra real no coincide con el valor esperado."
    Assert-TextContains -Text $realGroundSweep -Substring "Ancho porcentual: 4.81 %" `
        -FailureMessage (
            "El ancho de banda porcentual del dipolo de tierra real " +
            "no coincide con el valor esperado."
        )
    Assert-TextExcludes -Text $realGroundSweep -Substring "truncado" `
        -FailureMessage "El barrido del dipolo de tierra real reporto un resultado truncado inesperado."

    Write-Host "Exportando NEC puntual del dipolo sobre tierra real..."
    Invoke-YaasCli `
        -CliArgs @(
            "--language", "es", "export-nec",
            $realGroundProject, $realGroundNecFile
        ) `
        -FailureMessage "La exportacion NEC puntual del dipolo de tierra real fallo." |
        Out-Null

    if (-not (Test-Path $realGroundNecFile)) {
        throw "No se genero el archivo NEC puntual del dipolo de tierra real."
    }

    $realGroundNecLines = Get-Content $realGroundNecFile
    Assert-NecCardOrder -Lines $realGroundNecLines `
        -Context "El archivo NEC puntual del dipolo de tierra real" `
        -OrderedCards @(
            "GW 1 101 -5.03 0 10 5.03 0 10 0.001",
            "GE 1",
            "GN 2 0 0 0 13 0.005 0 0 0 0",
            "EX 0 1 51 0 1 0",
            "FR 0 1 0 0 14.15 0",
            "EN"
        )
    Assert-GnCardFields -Lines $realGroundNecLines `
        -ExpectedFields @("2", "0", "0", "0", "13", "0.005", "0", "0", "0", "0") `
        -Context "El archivo NEC puntual del dipolo de tierra real"

    Write-Host "Exportando NEC de barrido del dipolo sobre tierra real..."
    Invoke-YaasCli `
        -CliArgs @(
            "--language", "es", "export-nec", "--sweep",
            $realGroundProject, $realGroundSweepNecFile
        ) `
        -FailureMessage "La exportacion NEC de barrido del dipolo de tierra real fallo." |
        Out-Null

    if (-not (Test-Path $realGroundSweepNecFile)) {
        throw "No se genero el archivo NEC de barrido del dipolo de tierra real."
    }

    $realGroundSweepNecLines = Get-Content $realGroundSweepNecFile
    Assert-NecCardOrder -Lines $realGroundSweepNecLines `
        -Context "El archivo NEC de barrido del dipolo de tierra real" `
        -OrderedCards @(
            "GW 1 101 -5.03 0 10 5.03 0 10 0.001",
            "GE 1",
            "GN 2 0 0 0 13 0.005 0 0 0 0",
            "EX 0 1 51 0 1 0",
            "FR 0 81 0 0 13.5 0.025",
            "EN"
        )
    Assert-GnCardFields -Lines $realGroundSweepNecLines `
        -ExpectedFields @("2", "0", "0", "0", "13", "0.005", "0", "0", "0", "0") `
        -Context "El archivo NEC de barrido del dipolo de tierra real"
}
finally {
    if (Test-Path $realGroundNecFile) {
        Remove-Item $realGroundNecFile
    }
    if (Test-Path $realGroundSweepNecFile) {
        Remove-Item $realGroundSweepNecFile
    }
}

$patternProject = Join-Path `
    $projectRoot `
    "examples\dipole-20m-radiation-pattern.yaas"

$patternCsvFile = Join-Path `
    $projectRoot `
    "dist\yaas-smoke-pattern.csv"

$patternNecFile = Join-Path `
    $projectRoot `
    "dist\yaas-smoke-pattern.nec"

if (-not (Test-Path $patternProject)) {
    throw "No se encontro el proyecto de ejemplo con patron de radiacion."
}

try {
    Write-Host "Validando el dipolo con patron de radiacion (schema v4)..."
    $patternValidation = Invoke-YaasCli `
        -CliArgs @("--language", "es", "validate", $patternProject) `
        -FailureMessage "La validacion del dipolo con patron de radiacion fallo."
    Write-Host $patternValidation.TrimEnd()
    Assert-TextContains -Text $patternValidation -Substring "esquema: 4" `
        -FailureMessage "El dipolo con patron no se valido como schema_version 4."

    Write-Host "Calculando el patron de radiacion..."
    $patternSummary = Invoke-YaasCli `
        -CliArgs @("--language", "es", "pattern", $patternProject) `
        -FailureMessage "El calculo del patron de radiacion fallo."
    Write-Host $patternSummary.TrimEnd()
    Assert-TextContains -Text $patternSummary -Substring "Frecuencia: 14.150 MHz" `
        -FailureMessage "La frecuencia del patron no es la esperada."
    Assert-TextContains -Text $patternSummary -Substring "Grilla: 181 x 1 (181 puntos)" `
        -FailureMessage "La grilla del patron no es 181 x 1."
    Assert-TextContains -Text $patternSummary -Substring "Nulos: 1" `
        -FailureMessage "El patron no reporta exactamente un nulo."
    Assert-TextContains -Text $patternSummary -Substring "2.12 dBi" `
        -FailureMessage (
            "La ganancia maxima del patron no coincide con el valor " +
            "validado con 4nec2 (docs/validation/radiation-patterns-4nec2.md)."
        )
    Assert-TextContains -Text $patternSummary -Substring "theta=0.00 grados, phi=0.00 grados" `
        -FailureMessage "La direccion del maximo del patron no es la esperada."

    Write-Host "Exportando el patron de radiacion a CSV..."
    $patternCsvOutput = Invoke-YaasCli `
        -CliArgs @(
            "--language", "es", "pattern", $patternProject,
            "--csv", $patternCsvFile
        ) `
        -FailureMessage "La exportacion CSV del patron de radiacion fallo."
    Assert-TextContains -Text $patternCsvOutput -Substring "Archivo CSV" `
        -FailureMessage "pattern --csv no informo el archivo CSV creado."

    if (-not (Test-Path $patternCsvFile)) {
        throw "No se genero el archivo CSV del patron de radiacion."
    }

    $patternCsvLines = @(Get-Content $patternCsvFile)
    if ($patternCsvLines[0] -ne "frequency_mhz,theta_deg,phi_deg,gain_db") {
        throw "El encabezado del CSV del patron no es el esperado: $($patternCsvLines[0])"
    }
    if ($patternCsvLines.Count -ne 182) {
        throw "El CSV del patron deberia tener 182 lineas y tiene $($patternCsvLines.Count)."
    }
    if (-not $patternCsvLines[1].StartsWith("14.15,0.0,0.0,2.12")) {
        throw "El CSV del patron no contiene el maximo esperado en theta=0: $($patternCsvLines[1])"
    }
    if ($patternCsvLines -notcontains "14.15,90.0,0.0,") {
        throw "El CSV del patron no representa el nulo de theta=90 como campo vacio."
    }

    Write-Host "Exportando NEC con tarjeta RP del patron de radiacion..."
    Invoke-YaasCli `
        -CliArgs @(
            "--language", "es", "export-nec", "--pattern",
            $patternProject, $patternNecFile
        ) `
        -FailureMessage "La exportacion NEC del patron de radiacion fallo." |
        Out-Null

    if (-not (Test-Path $patternNecFile)) {
        throw "No se genero el archivo NEC del patron de radiacion."
    }

    $patternNecLines = @(Get-Content $patternNecFile)
    Assert-NecCardOrder -Lines $patternNecLines `
        -Context "El archivo NEC del patron de radiacion" `
        -OrderedCards @(
            "GW 1 101 -5.03 0 0 5.03 0 0 0.001",
            "GE 0",
            "EX 0 1 51 0 1 0",
            "FR 0 1 0 0 14.15 0",
            "RP 0 181 1 0000 0 0 1 0 0 0",
            "EN"
        )
    Assert-NoLineStartsWith -Lines $patternNecLines -Prefix "GN " `
        -FailureMessage "El archivo NEC del patron en espacio libre no deberia contener GN."
    Assert-NoLineStartsWith -Lines $patternNecLines -Prefix "XQ" `
        -FailureMessage "El archivo NEC del patron no deberia contener XQ."
    if ($patternNecLines[-1] -ne "EN") {
        throw "La ultima tarjeta del archivo NEC del patron no es EN."
    }
}
finally {
    if (Test-Path $patternCsvFile) {
        Remove-Item $patternCsvFile
    }
    if (Test-Path $patternNecFile) {
        Remove-Item $patternNecFile
    }
}

$measurementSmokeFile = Join-Path `
    $projectRoot `
    "dist\yaas-smoke-measurement.s1p"

try {
    Write-Host "Comprobando la importación Touchstone..."

    @(
        "! YAAS executable test"
        "# MHz S RI R 50"
        "14.000 0.20 -0.10"
        "14.100 0.10 -0.05"
        "14.200 0.00 0.00"
        "14.300 0.10 0.05"
    ) | Set-Content `
        -Path $measurementSmokeFile `
        -Encoding UTF8

    $spanishMeasurement = (
        & .\dist\yaas.exe `
            --language es `
            inspect-s1p `
            $measurementSmokeFile |
            Out-String
    )

    if ($LASTEXITCODE -ne 0) {
        throw "La importación Touchstone falló."
    }

    Write-Host $spanishMeasurement.TrimEnd()

    if (
        -not $spanishMeasurement.Contains(
            "Puntos: 4"
        )
    ) {
        throw "La medición no contiene cuatro puntos."
    }

    if (
        -not $spanishMeasurement.Contains(
            "Frecuencia: 14.200 MHz"
        )
    ) {
        throw "La resonancia medida no es correcta."
    }

    Write-Host "Comprobando Touchstone en inglés..."

    $englishMeasurement = (
        & .\dist\yaas.exe `
            --language en `
            inspect-s1p `
            $measurementSmokeFile |
            Out-String
    )

    if ($LASTEXITCODE -ne 0) {
        throw "La importación Touchstone inglesa falló."
    }

    if (
        -not $englishMeasurement.Contains(
            "Points: 4"
        )
    ) {
        throw "La salida inglesa de Touchstone es incorrecta."
    }

    if (
        -not $englishMeasurement.Contains(
            "Approximate resonance:"
        )
    ) {
        throw "Falta el encabezado inglés de resonancia."
    }
}
finally {
    if (Test-Path $measurementSmokeFile) {
        Remove-Item $measurementSmokeFile
    }
}

$comparisonMeasurementFile = Join-Path `
    $projectRoot `
    "dist\yaas-smoke-compare.s1p"

$comparisonSmokeCsv = Join-Path `
    $projectRoot `
    "dist\yaas-smoke-compare.csv"

try {
    Write-Host "Comprobando el comando compare..."

    @(
        "! YAAS executable comparison test"
        "# MHz S RI R 50"
        "13.600 0.10 0.02"
        "14.500 0.05 0.03"
        "15.400 0.10 -0.02"
    ) | Set-Content `
        -Path $comparisonMeasurementFile `
        -Encoding UTF8

    $spanishComparison = (
        & .\dist\yaas.exe `
            --language es `
            compare `
            $exampleProject `
            $comparisonMeasurementFile `
            --reference-impedance 50 `
            --output $comparisonSmokeCsv |
            Out-String
    )

    if ($LASTEXITCODE -ne 0) {
        throw "La comparación en español falló."
    }

    Write-Host $spanishComparison.TrimEnd()

    if (
        -not $spanishComparison.Contains(
            "Puntos comparados: 3"
        )
    ) {
        throw "La comparación no produjo la salida esperada en español."
    }

    if (-not (Test-Path $comparisonSmokeCsv)) {
        throw "El comando compare no generó el archivo CSV."
    }

    $comparisonCsvLines = Get-Content $comparisonSmokeCsv

    if ($comparisonCsvLines.Count -lt 2) {
        throw "El CSV de comparación no contiene cabecera y datos."
    }

    if (
        -not $comparisonCsvLines[0].StartsWith(
            "frequency_mhz,"
        )
    ) {
        throw "El CSV de comparación no contiene la cabecera esperada."
    }

    Write-Host "Comprobando el resumen de compare en inglés..."

    $englishComparison = (
        & .\dist\yaas.exe `
            --language en `
            compare `
            $exampleProject `
            $comparisonMeasurementFile `
            --reference-impedance 50 |
            Out-String
    )

    if ($LASTEXITCODE -ne 0) {
        throw "La comparación en inglés falló."
    }

    Write-Host $englishComparison.TrimEnd()

    if (
        -not $englishComparison.Contains(
            "Compared points: 3"
        )
    ) {
        throw "La salida inglesa de compare es incorrecta."
    }
}
finally {
    if (Test-Path $comparisonMeasurementFile) {
        Remove-Item $comparisonMeasurementFile
    }
    if (Test-Path $comparisonSmokeCsv) {
        Remove-Item $comparisonSmokeCsv
    }
}

$mmanaSmokeSource = Join-Path `
    $projectRoot `
    "dist\yaas-smoke-dipole.maa"

$mmanaSmokeProject = Join-Path `
    $projectRoot `
    "dist\yaas-smoke-mmana.yaas"

try {
    Write-Host "Comprobando el comando import-mmana..."

    # 1. Archivo MMANA-GAL minimo, compatible y solo ASCII (dipolo de
    #    prueba, replica 00-base-dipole.maa de mmana-experiments).
    @(
        "YAAS Smoke Dipole"
        "*"
        "14.15"
        "***Wires***"
        "1"
        "-5.03,0.0,0.0,5.03,0.0,0.0,0.001,-1"
        "***Source***"
        "1,0"
        "w1c,0,1.0"
        "***Load***"
        "0,0"
        "***Segmentation***"
        "800,80,2.0,2"
        "***G/H/M/R/AzEl/X***"
        "0,5.0,0,50.0,0,0,0.0"
    ) | Set-Content `
        -Path $mmanaSmokeSource `
        -Encoding UTF8

    # 2. Importar en español, con las cuatro opciones de barrido
    #    obligatorias (el formato MMANA-GAL no las contiene).
    $spanishImport = (
        & .\dist\yaas.exe `
            --language es `
            import-mmana `
            $mmanaSmokeSource `
            $mmanaSmokeProject `
            --sweep-start 13.5 `
            --sweep-stop 15.5 `
            --sweep-points 81 `
            --swr-limit 2.0 |
            Out-String
    )

    # 3. Verificar el código de salida de la importación.
    if ($LASTEXITCODE -ne 0) {
        throw "La importación MMANA-GAL en español falló."
    }

    Write-Host $spanishImport.TrimEnd()

    # 4. Verificar la frase de éxito esperada en español.
    if (
        -not $spanishImport.Contains(
            "Proyecto MMANA-GAL importado correctamente."
        )
    ) {
        throw "La importación no produjo la salida esperada en español."
    }

    # 5. Verificar que el archivo .yaas se haya creado.
    if (-not (Test-Path $mmanaSmokeProject)) {
        throw "El comando import-mmana no generó el archivo .yaas."
    }

    # 6. Validar el proyecto generado, para confirmar que
    #    import-mmana produjo un .yaas consistente y cargable.
    Write-Host "Validando el proyecto importado..."

    & .\dist\yaas.exe --language es validate $mmanaSmokeProject |
        Out-Null

    if ($LASTEXITCODE -ne 0) {
        throw "El proyecto generado por import-mmana no pasó la validación."
    }

    # 7. Repetir la importación en inglés, sobrescribiendo con
    #    --force, para comprobar esa opción y el idioma inglés.
    Write-Host "Comprobando import-mmana en inglés..."

    $englishImport = (
        & .\dist\yaas.exe `
            --language en `
            import-mmana `
            $mmanaSmokeSource `
            $mmanaSmokeProject `
            --sweep-start 13.5 `
            --sweep-stop 15.5 `
            --sweep-points 81 `
            --swr-limit 2.0 `
            --force |
            Out-String
    )

    # 8. Verificar el código de salida y la frase de éxito en inglés.
    if ($LASTEXITCODE -ne 0) {
        throw "La importación MMANA-GAL en inglés falló."
    }

    Write-Host $englishImport.TrimEnd()

    if (
        -not $englishImport.Contains(
            "MMANA-GAL project imported successfully."
        )
    ) {
        throw "La salida inglesa de import-mmana es incorrecta."
    }
}
finally {
    # 9. Limpieza completa de los archivos temporales, incluso si
    #    alguna comprobación anterior falló.
    if (Test-Path $mmanaSmokeSource) {
        Remove-Item $mmanaSmokeSource
    }
    if (Test-Path $mmanaSmokeProject) {
        Remove-Item $mmanaSmokeProject
    }
}

Write-Host ""
Write-Host "Compilación completada correctamente."
Write-Host "Ejecutable: $projectRoot\dist\yaas.exe"