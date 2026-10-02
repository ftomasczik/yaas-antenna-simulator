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

# Imagenes temporales del smoke test de graficos, fuera del repositorio;
# el trap las elimina siempre.
smoke_dir="$(mktemp -d)"
cleanup() {
    rm -rf "$smoke_dir"
}
trap cleanup EXIT

smoke_export_args=(--smoke-test)
for extension in png svg pdf; do
    smoke_export_args+=(--smoke-export "$smoke_dir/smoke.$extension")
done

assert_smoke_images() {
    local context="$1"
    local extension
    for extension in png svg pdf; do
        if [[ ! -s "$smoke_dir/smoke.$extension" ]]; then
            echo "$context: no se genero una imagen $extension no vacia." >&2
            exit 1
        fi
        rm -f "$smoke_dir/smoke.$extension"
    done
}

python3 -m yaas.gui.main "${smoke_export_args[@]}"
assert_smoke_images "Modulo sin congelar"

# Proyectos de ejemplo de cada version de esquema (1 a 4): el smoke test
# los abre realmente, sin simular. Uno inexistente y uno danado (JSON
# incompleto) deben hacer fallar el smoke test.
example_projects=(
    "$project_root/examples/dipole-20m.yaas"
    "$project_root/examples/monopole-20m-perfect-ground.yaas"
    "$project_root/examples/dipole-20m-real-ground.yaas"
    "$project_root/examples/dipole-20m-radiation-pattern.yaas"
)
invalid_projects=("$smoke_dir/missing.yaas" "$smoke_dir/damaged.yaas")
printf '{' > "$smoke_dir/damaged.yaas"

check_projects() {
    local context="$1"
    shift
    local project
    for project in "${example_projects[@]}"; do
        if ! "$@" --smoke-test "$project"; then
            echo "$context: --smoke-test no pudo abrir $project." >&2
            exit 1
        fi
    done
    for project in "${invalid_projects[@]}"; do
        echo "Se espera un error al abrir $project..."
        if "$@" --smoke-test "$project"; then
            echo "$context: --smoke-test acepto el proyecto invalido $project." >&2
            exit 1
        fi
    done
}

check_projects "Modulo sin congelar" python3 -m yaas.gui.main

# --smoke-calculate calcula de verdad el patron (PyNEC dentro del
# worker): debe funcionar con el ejemplo de esquema 4, exportando el
# corte dibujado, y fallar con un proyecto sin patron.
pattern_project="${example_projects[3]}"
no_pattern_project="${example_projects[0]}"
smoke_calculate_args=(--smoke-test --smoke-calculate)
for extension in png svg pdf; do
    smoke_calculate_args+=(--smoke-export "$smoke_dir/smoke.$extension")
done
smoke_calculate_args+=("$pattern_project")

check_calculation() {
    local context="$1"
    shift
    echo "$context: calculando el patron de $pattern_project..."
    if ! "$@" "${smoke_calculate_args[@]}"; then
        echo "$context: --smoke-calculate fallo." >&2
        exit 1
    fi
    assert_smoke_images "$context (calculo)"
    echo "Se espera un error al calcular $no_pattern_project (sin patron)..."
    if "$@" --smoke-test --smoke-calculate "$no_pattern_project"; then
        echo "$context: --smoke-calculate acepto un proyecto sin patron." >&2
        exit 1
    fi
}

check_calculation "Modulo sin congelar" python3 -m yaas.gui.main

echo "Limpiando resultados anteriores del build de la GUI..."
# Borrado puntual, sin globs: solo lo que este build genera.
rm -f "$project_root/dist/yaas-gui"
rm -rf "$project_root/build/yaas-gui"
rm -f "$project_root/yaas-gui.spec"

echo "Generando el ejecutable yaas-gui..."
# QtNetwork se excluye: la GUI no usa red, y su plugin TLS podia
# arrastrar bibliotecas OpenSSL ajenas. pyqtgraph se excluye para no
# incorporarlo si estuviera instalado. PyNEC si se incorpora: la GUI
# calcula patrones (lo importa recien dentro del worker, por eso se
# declara yaas.engines.pynec). Matplotlib y numpy tambien. El hook
# de Matplotlib solo recoge los backends que detecta en uso, y savefig
# carga los de SVG y PDF dinamicamente: se declaran explicitamente.
python3 -m PyInstaller \
    --name yaas-gui \
    --onefile \
    --clean \
    --noconfirm \
    --paths ./src \
    --hidden-import matplotlib.backends.backend_svg \
    --hidden-import matplotlib.backends.backend_pdf \
    --hidden-import yaas.engines.pynec \
    --exclude-module PySide6.QtNetwork \
    --exclude-module pyqtgraph \
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

echo "Comprobando graficos y exportacion PNG/SVG/PDF en yaas-gui..."
"$exe" "${smoke_export_args[@]}"
assert_smoke_images "yaas-gui"

echo "Comprobando la apertura de proyectos v1-v4 en yaas-gui..."
check_projects "yaas-gui" "$exe"

check_calculation "yaas-gui" "$exe"

echo "Comprobando las bibliotecas incorporadas..."
analysis_toc="$project_root/build/yaas-gui/Analysis-00.toc"
# Las entradas incorporadas empiezan con "('nombre"; la lista de
# exclusiones tambien menciona esos nombres, pero sin "(".
if grep -qiE "xampp" "$analysis_toc"; then
    echo "yaas-gui incorpora bibliotecas de una instalacion ajena (xampp)." >&2
    exit 1
fi
if grep -qE "\('pyqtgraph['.]" "$analysis_toc"; then
    echo "yaas-gui incorpora pyqtgraph." >&2
    exit 1
fi
# El motor si debe estar: modulo Python y extension nativa.
if ! grep -qE "\('PyNEC'" "$analysis_toc" \
    || ! grep -qE "\('_PyNEC\." "$analysis_toc"; then
    echo "yaas-gui no incorpora PyNEC: no podria calcular patrones." >&2
    exit 1
fi
if grep -qE "QtNetwork\.(abi3\.so|so|pyd)" "$analysis_toc"; then
    echo "yaas-gui incorpora el modulo PySide6.QtNetwork." >&2
    exit 1
fi

size_mb="$(du -m "$exe" | cut -f1)"
echo ""
echo "Build experimental de la GUI para Linux completado correctamente (~${size_mb} MB)."
echo "Ejecutable: $exe"
