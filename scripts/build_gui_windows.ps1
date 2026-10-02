$ErrorActionPreference = "Stop"
$utf8Encoding = [System.Text.UTF8Encoding]::new(
    $false
)

[Console]::InputEncoding = $utf8Encoding
[Console]::OutputEncoding = $utf8Encoding
$OutputEncoding = $utf8Encoding
$env:PYTHONIOENCODING = "utf-8"

# Build experimental del ejecutable de la GUI (dist\yaas-gui.exe).
#
# A diferencia de scripts\build_windows.ps1 (CLI), no exige un entorno
# virtual activado: tambien corre en el job de CI, donde
# actions/setup-python deja "python" en el PATH. Si exige el extra
# opcional "gui" (PySide6-Essentials) instalado.
#
# El ejecutable final es "--windowed" (sin consola): sus mensajes no
# son visibles, asi que las comprobaciones del ejecutable congelado se
# hacen por codigo de salida; --version y la salida de texto se
# verifican antes, ejecutando el modulo sin congelar.

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$guiExe = Join-Path $projectRoot "dist\yaas-gui.exe"
$guiWorkDirectory = Join-Path $projectRoot "build\yaas-gui"
$guiSpec = Join-Path $projectRoot "yaas-gui.spec"
$previousQtPlatform = $env:QT_QPA_PLATFORM

# Imagenes temporales del smoke test de graficos (PNG, SVG y PDF),
# fuera del repositorio; se eliminan siempre en el bloque finally.
$smokeImageDirectory = Join-Path ([System.IO.Path]::GetTempPath()) (
    "yaas-gui-smoke-" + [System.Guid]::NewGuid().ToString("N")
)
$smokeImages = @(
    (Join-Path $smokeImageDirectory "smoke.png"),
    (Join-Path $smokeImageDirectory "smoke.svg"),
    (Join-Path $smokeImageDirectory "smoke.pdf")
)

# Proyectos de ejemplo de cada version de esquema (1 a 4): el smoke test
# los abre realmente, sin simular. Uno inexistente y uno danado deben
# hacer fallar el smoke test.
$exampleProjects = @(
    (Join-Path $projectRoot "examples\dipole-20m.yaas"),
    (Join-Path $projectRoot "examples\monopole-20m-perfect-ground.yaas"),
    (Join-Path $projectRoot "examples\dipole-20m-real-ground.yaas"),
    (Join-Path $projectRoot "examples\dipole-20m-radiation-pattern.yaas")
)
$invalidProjects = @(
    (Join-Path $smokeImageDirectory "missing.yaas"),
    (Join-Path $smokeImageDirectory "damaged.yaas")
)

# --smoke-calculate calcula de verdad el patron (PyNEC dentro del
# worker): debe funcionar con el ejemplo de esquema 4 y fallar con un
# proyecto sin patron.
$patternProject = $exampleProjects[3]
$noPatternProject = $exampleProjects[0]
# Grilla completa, generada en el directorio temporal (ver mas abajo).
$fullGridProject = Join-Path $smokeImageDirectory "full-grid.yaas"

function Get-SmokeCalculateArgs {
    # Calcula el patron de $patternProject y exporta el corte dibujado.
    $arguments = @("--smoke-test", "--smoke-calculate")
    foreach ($image in $smokeImages) {
        $arguments += @("--smoke-export", $image)
    }
    $arguments += $patternProject
    return $arguments
}

function Get-SmokeExportArgs {
    # --smoke-test con un --smoke-export por cada imagen temporal.
    $arguments = @("--smoke-test")
    foreach ($image in $smokeImages) {
        $arguments += @("--smoke-export", $image)
    }
    return $arguments
}

function Assert-SmokeImages {
    param(
        [Parameter(Mandatory)][string]$Context
    )
    foreach ($image in $smokeImages) {
        if (-not (Test-Path $image)) {
            throw "${Context}: no se genero $image."
        }
        if ((Get-Item $image).Length -le 0) {
            throw "${Context}: $image esta vacio."
        }
        Remove-Item $image
    }
}

function Invoke-ModuleGuiExpectingFailure {
    # Ejecuta el modulo sin congelar con un proyecto invalido y devuelve
    # su codigo de salida. El error esperado sale por stderr: con
    # ErrorActionPreference = "Stop", Windows PowerShell 5.1 lo
    # convertiria en un error terminante si la salida esta redirigida,
    # asi que la preferencia se relaja solo durante esta llamada.
    param(
        [Parameter(Mandatory)][string[]]$GuiArgs
    )
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        python -m yaas.gui.main @GuiArgs 2>&1 | ForEach-Object {
            Write-Host "$_"
        }
        return $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }
}

function Invoke-FrozenGui {
    # Ejecuta dist\yaas-gui.exe y devuelve su codigo de salida. Un
    # ejecutable sin consola no escribe en la terminal, pero
    # Start-Process -Wait -PassThru si informa el codigo de salida.
    param(
        [Parameter(Mandatory)][string[]]$GuiArgs
    )
    $process = Start-Process `
        -FilePath $guiExe `
        -ArgumentList $GuiArgs `
        -Wait `
        -PassThru
    return $process.ExitCode
}

try {
    # Sin pantalla: igual en una maquina local y en CI.
    $env:QT_QPA_PLATFORM = "offscreen"

    Write-Host "Comprobando el extra opcional gui (PySide6-Essentials)..."
    python -c "import PySide6.QtWidgets"
    if ($LASTEXITCODE -ne 0) {
        throw (
            "PySide6 no esta instalado. Instalar el extra con: " +
            'python -m pip install -e ".[dev,gui]"'
        )
    }

    Write-Host "Ejecutando las pruebas de la GUI..."
    python -m pytest tests\gui tests\test_gui_entry_point.py
    if ($LASTEXITCODE -ne 0) {
        throw "Las pruebas de la GUI fallaron."
    }

    Write-Host "Comprobando el modulo sin congelar..."
    $moduleVersion = (python -m yaas.gui.main --version | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "yaas-gui --version fallo antes de congelar."
    }
    $expectedVersion = (
        python -c "import yaas; print('yaas-gui ' + yaas.__version__)" |
        Out-String
    ).Trim()
    if ($moduleVersion -ne $expectedVersion) {
        throw "yaas-gui --version informo '$moduleVersion' en vez de '$expectedVersion'."
    }
    Write-Host $moduleVersion

    python -m yaas.gui.main --smoke-test
    if ($LASTEXITCODE -ne 0) {
        throw "yaas-gui --smoke-test fallo antes de congelar."
    }

    New-Item -ItemType Directory -Path $smokeImageDirectory | Out-Null
    $moduleSmokeArgs = Get-SmokeExportArgs
    python -m yaas.gui.main @moduleSmokeArgs
    if ($LASTEXITCODE -ne 0) {
        throw "yaas-gui --smoke-export fallo antes de congelar."
    }
    Assert-SmokeImages -Context "Modulo sin congelar"

    # Proyecto danado: JSON incompleto. "missing.yaas" nunca se crea.
    Set-Content -Path $invalidProjects[1] -Value "{" -Encoding ascii

    foreach ($project in $exampleProjects) {
        python -m yaas.gui.main --smoke-test $project
        if ($LASTEXITCODE -ne 0) {
            throw "yaas-gui --smoke-test no pudo abrir $project antes de congelar."
        }
    }
    foreach ($project in $invalidProjects) {
        Write-Host "Se espera un error al abrir $project..."
        $invalidExit = Invoke-ModuleGuiExpectingFailure -GuiArgs @(
            "--smoke-test", $project
        )
        if ($invalidExit -eq 0) {
            throw "yaas-gui --smoke-test acepto el proyecto invalido $project."
        }
    }

    Write-Host "Calculando el patron de $patternProject antes de congelar..."
    $moduleCalculateArgs = Get-SmokeCalculateArgs
    python -m yaas.gui.main @moduleCalculateArgs
    if ($LASTEXITCODE -ne 0) {
        throw "yaas-gui --smoke-calculate fallo antes de congelar."
    }
    Assert-SmokeImages -Context "Calculo sin congelar"
    Write-Host "Se espera un error al calcular $noPatternProject (sin patron)..."
    $noPatternExit = Invoke-ModuleGuiExpectingFailure -GuiArgs @(
        "--smoke-test", "--smoke-calculate", $noPatternProject
    )
    if ($noPatternExit -eq 0) {
        throw "yaas-gui --smoke-calculate acepto un proyecto sin patron."
    }

    # Proyecto temporal con grilla completa (4 theta x 4 phi), generado
    # con la API de proyectos: --smoke-calculate recorre ahi ambos modos
    # del selector de cortes (vertical y azimut).
    $fullGridCode = "import dataclasses, sys; " +
        "from yaas.domain import AngularSweep; " +
        "from yaas.projects import RadiationPatternSettings, load_project, save_project; " +
        "project = load_project(sys.argv[1]); " +
        "pattern = RadiationPatternSettings(theta=AngularSweep(0.0, 4, 30.0), phi=AngularSweep(0.0, 4, 90.0)); " +
        "save_project(dataclasses.replace(project, radiation_pattern=pattern), sys.argv[2])"
    python -c $fullGridCode $patternProject $fullGridProject
    if ($LASTEXITCODE -ne 0) {
        throw "No se pudo generar el proyecto de grilla completa."
    }
    Write-Host "Calculando y recorriendo los cortes de $fullGridProject..."
    python -m yaas.gui.main --smoke-test --smoke-calculate $fullGridProject
    if ($LASTEXITCODE -ne 0) {
        throw "yaas-gui --smoke-calculate fallo con la grilla completa."
    }

    Write-Host "Limpiando resultados anteriores del build de la GUI..."
    # Borrado puntual: solo lo que este build genera.
    if (Test-Path $guiExe) {
        Remove-Item $guiExe -Force
    }
    if (Test-Path $guiWorkDirectory) {
        Remove-Item $guiWorkDirectory -Recurse -Force
    }
    if (Test-Path $guiSpec) {
        Remove-Item $guiSpec -Force
    }

    Write-Host "Generando yaas-gui.exe..."
    # QtNetwork se excluye: la GUI no usa red, y su plugin TLS
    # arrastraba bibliotecas OpenSSL ajenas encontradas en el PATH.
    # pyqtgraph se excluye para no incorporarlo si estuviera instalado.
    # PyNEC si se incorpora: la GUI calcula patrones (lo importa recien
    # dentro del worker, por eso se declara yaas.engines.pynec).
    # Matplotlib y numpy tambien: los usa el grafico de patrones.
    # El hook de Matplotlib solo recoge los backends que detecta en uso
    # (QtAgg/Agg); savefig carga los de SVG y PDF dinamicamente, asi que
    # se declaran explicitamente (sin ellos, la exportacion SVG/PDF
    # falla solo en el ejecutable congelado).
    python -m PyInstaller `
        --name yaas-gui `
        --onefile `
        --windowed `
        --clean `
        --noconfirm `
        --paths .\src `
        --hidden-import matplotlib.backends.backend_svg `
        --hidden-import matplotlib.backends.backend_pdf `
        --hidden-import yaas.engines.pynec `
        --exclude-module PySide6.QtNetwork `
        --exclude-module pyqtgraph `
        .\src\yaas\gui\main.py

    if ($LASTEXITCODE -ne 0) {
        throw "La generacion de yaas-gui.exe fallo."
    }

    if (-not (Test-Path $guiExe)) {
        throw "No se genero $guiExe."
    }

    Write-Host "Comprobando yaas-gui.exe --version (codigo de salida)..."
    $versionExit = Invoke-FrozenGui -GuiArgs @("--version")
    if ($versionExit -ne 0) {
        throw "yaas-gui.exe --version devolvio $versionExit."
    }

    Write-Host "Comprobando yaas-gui.exe --smoke-test (offscreen)..."
    $smokeExit = Invoke-FrozenGui -GuiArgs @("--smoke-test")
    if ($smokeExit -ne 0) {
        throw "yaas-gui.exe --smoke-test devolvio $smokeExit."
    }

    Write-Host "Comprobando graficos y exportacion PNG/SVG/PDF en yaas-gui.exe..."
    $frozenSmokeArgs = Get-SmokeExportArgs
    $exportExit = Invoke-FrozenGui -GuiArgs $frozenSmokeArgs
    if ($exportExit -ne 0) {
        throw "yaas-gui.exe --smoke-export devolvio $exportExit."
    }
    Assert-SmokeImages -Context "yaas-gui.exe"

    Write-Host "Comprobando la apertura de proyectos v1-v4 en yaas-gui.exe..."
    foreach ($project in $exampleProjects) {
        $projectExit = Invoke-FrozenGui -GuiArgs @("--smoke-test", $project)
        if ($projectExit -ne 0) {
            throw "yaas-gui.exe --smoke-test $project devolvio $projectExit."
        }
    }
    foreach ($project in $invalidProjects) {
        $invalidExit = Invoke-FrozenGui -GuiArgs @("--smoke-test", $project)
        if ($invalidExit -eq 0) {
            throw "yaas-gui.exe --smoke-test acepto el proyecto invalido $project."
        }
    }

    Write-Host "Calculando el patron de radiacion con yaas-gui.exe..."
    $frozenCalculateArgs = Get-SmokeCalculateArgs
    $calculateExit = Invoke-FrozenGui -GuiArgs $frozenCalculateArgs
    if ($calculateExit -ne 0) {
        throw "yaas-gui.exe --smoke-calculate devolvio $calculateExit."
    }
    Assert-SmokeImages -Context "Calculo en yaas-gui.exe"
    $noPatternExit = Invoke-FrozenGui -GuiArgs @(
        "--smoke-test", "--smoke-calculate", $noPatternProject
    )
    if ($noPatternExit -eq 0) {
        throw "yaas-gui.exe --smoke-calculate acepto un proyecto sin patron."
    }
    $fullGridExit = Invoke-FrozenGui -GuiArgs @(
        "--smoke-test", "--smoke-calculate", $fullGridProject
    )
    if ($fullGridExit -ne 0) {
        throw "yaas-gui.exe --smoke-calculate devolvio $fullGridExit con la grilla completa."
    }

    Write-Host "Comprobando las bibliotecas incorporadas..."
    $analysisToc = Join-Path $guiWorkDirectory "Analysis-00.toc"
    $analysis = Get-Content $analysisToc -Raw
    # Las entradas incorporadas empiezan con "('nombre"; la lista de
    # exclusiones tambien menciona esos nombres, pero sin "(".
    if ($analysis -match "(?i)xampp") {
        throw "yaas-gui.exe incorpora bibliotecas de una instalacion ajena (xampp)."
    }
    if ($analysis -match "\('pyqtgraph['.]") {
        throw "yaas-gui.exe incorpora pyqtgraph."
    }
    # El motor si debe estar: modulo Python y extension nativa.
    if (-not ($analysis -match "\('PyNEC'") -or
        -not ($analysis -match "\('_PyNEC\.")) {
        throw "yaas-gui.exe no incorpora PyNEC: no podria calcular patrones."
    }
    if ($analysis.Contains("QtNetwork.pyd")) {
        throw "yaas-gui.exe incorpora el modulo PySide6.QtNetwork."
    }

    $sizeMb = (Get-Item $guiExe).Length / 1MB
    Write-Host ""
    Write-Host ("Compilacion de la GUI completada correctamente ({0:N1} MB)." -f $sizeMb)
    Write-Host "Ejecutable: $guiExe"
}
finally {
    $env:QT_QPA_PLATFORM = $previousQtPlatform
    if (Test-Path $smokeImageDirectory) {
        Remove-Item $smokeImageDirectory -Recurse -Force
    }
}
