#!/usr/bin/env bash
# Build experimental de la GUI de YAAS para Linux (dist/yaas-gui,
# ejecutable efimero, no publicado).
#
# Igual que scripts/build_linux.sh, no exige un entorno virtual
# activado: esta pensado para un job de CI donde actions/setup-python ya
# deja "python" en el PATH. Si exige el extra opcional "gui"
# (PySide6-Essentials) instalado. En Linux, --windowed de PyInstaller no
# tiene efecto: el ejecutable conserva su salida de texto.
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

# Sin pantalla: igual en una maquina local y en CI.
export QT_QPA_PLATFORM=offscreen

echo "Comprobando el extra opcional gui (PySide6-Essentials)..."
if ! python3 -c "import PySide6.QtWidgets"; then
    echo "PySide6 no esta instalado. Instalar el extra con:" >&2
    echo '  python -m pip install -e ".[dev,gui]"' >&2
    exit 1
fi

echo "Ejecutando las pruebas de la GUI..."
python3 -m pytest tests/gui tests/test_gui_entry_point.py

expected_version="$(python3 -c "import yaas; print('yaas-gui ' + yaas.__version__)")"

echo "Comprobando el modulo sin congelar..."
module_version="$(python3 -m yaas.gui.main --version)"
if [[ "$module_version" != "$expected_version" ]]; then
    echo "yaas-gui --version informo '$module_version' en vez de '$expected_version'." >&2
    exit 1
fi
echo "$module_version"
python3 -m yaas.gui.main --smoke-test

echo "Limpiando resultados anteriores del build de la GUI..."
# Borrado puntual, sin globs: solo lo que este build genera.
rm -f "$project_root/dist/yaas-gui"
rm -rf "$project_root/build/yaas-gui"
rm -f "$project_root/yaas-gui.spec"

echo "Generando el ejecutable yaas-gui..."
# QtNetwork se excluye: la ventana no usa red, y su plugin TLS podia
# arrastrar bibliotecas OpenSSL ajenas. numpy, PyNEC y Matplotlib se
# excluyen para que el ejecutable no pueda cargarlos.
python3 -m PyInstaller \
    --name yaas-gui \
    --onefile \
    --clean \
    --noconfirm \
    --paths ./src \
    --exclude-module PySide6.QtNetwork \
    --exclude-module numpy \
    --exclude-module PyNEC \
    --exclude-module matplotlib \
    ./src/yaas/gui/main.py

exe="$project_root/dist/yaas-gui"

if [[ ! -x "$exe" ]]; then
    echo "La generacion del ejecutable fallo: no se encontro $exe" >&2
    exit 1
fi

echo "Comprobando yaas-gui --version..."
frozen_version="$("$exe" --version)"
echo "$frozen_version"
if [[ "$frozen_version" != "$expected_version" ]]; then
    echo "El ejecutable informo '$frozen_version' en vez de '$expected_version'." >&2
    exit 1
fi

echo "Comprobando yaas-gui --smoke-test (offscreen)..."
"$exe" --smoke-test

size_mb="$(du -m "$exe" | cut -f1)"
echo ""
echo "Build experimental de la GUI para Linux completado correctamente (~${size_mb} MB)."
echo "Ejecutable: $exe"
