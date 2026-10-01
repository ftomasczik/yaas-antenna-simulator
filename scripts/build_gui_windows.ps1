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
    # QtNetwork se excluye: la ventana no usa red, y su plugin TLS
    # arrastraba bibliotecas OpenSSL ajenas encontradas en el PATH.
    # numpy, PyNEC y Matplotlib se excluyen para que el ejecutable no
    # pueda cargarlos: la GUI minima no usa el motor ni graficos.
    python -m PyInstaller `
        --name yaas-gui `
        --onefile `
        --windowed `
        --clean `
        --noconfirm `
        --paths .\src `
        --exclude-module PySide6.QtNetwork `
        --exclude-module numpy `
        --exclude-module PyNEC `
        --exclude-module matplotlib `
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

    $sizeMb = (Get-Item $guiExe).Length / 1MB
    Write-Host ""
    Write-Host ("Compilacion de la GUI completada correctamente ({0:N1} MB)." -f $sizeMb)
    Write-Host "Ejecutable: $guiExe"
}
finally {
    $env:QT_QPA_PLATFORM = $previousQtPlatform
}
