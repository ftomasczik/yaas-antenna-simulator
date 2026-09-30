#!/usr/bin/env bash
# Build experimental de YAAS para Linux (ejecutable efimero, no publicado).
#
# A diferencia de scripts/build_windows.ps1, este script no exige un
# entorno virtual activado: esta pensado para ejecutarse en un job de
# CI donde actions/setup-python ya deja "python"/"pip" resueltos en el
# PATH, sin un .venv local que activar.
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

echo "Ejecutando pruebas..."
python3 -m pytest

echo "Limpiando resultados anteriores del build de YAAS..."
# Borrado puntual, sin globs: solo lo que esta build puede haber
# generado antes (el ejecutable onefile, el directorio de trabajo de
# PyInstaller para este spec y el .spec generado). No se toca ningun
# otro contenido de dist/ o build/.
rm -f "$project_root/dist/yaas"
rm -rf "$project_root/build/yaas"
rm -f "$project_root/yaas.spec"

echo "Generando el ejecutable yaas..."
python3 -m PyInstaller \
    --name yaas \
    --onefile \
    --console \
    --clean \
    --noconfirm \
    --paths ./src \
    --hidden-import numpy \
    --add-data "src/yaas/locales:yaas/locales" \
    ./src/yaas/cli/main.py

exe="$project_root/dist/yaas"

if [[ ! -x "$exe" ]]; then
    echo "La generacion del ejecutable fallo: no se encontro $exe" >&2
    exit 1
fi

assert_contains() {
    local haystack="$1"
    local needle="$2"
    local message="$3"
    if [[ "$haystack" != *"$needle"* ]]; then
        echo "$message" >&2
        echo "--- salida obtenida ---" >&2
        echo "$haystack" >&2
        exit 1
    fi
}

echo "Comprobando --version..."
version_output="$("$exe" --version)"
echo "$version_output"
assert_contains "$version_output" "yaas 0.4.0.dev0" \
    "La salida de --version no es la esperada."

echo "Comprobando doctor..."
doctor_output="$("$exe" doctor)"
echo "$doctor_output"
assert_contains "$doctor_output" "PyNEC: OK" \
    "El diagnostico no reporto PyNEC: OK."
assert_contains "$doctor_output" "Environment: OK" \
    "El diagnostico no reporto Environment: OK."

# Verifica que la unica tarjeta GE del archivo sea exactamente la
# esperada, y que exista una unica linea "GN " (o ninguna) cuyos
# campos, separados por espacios, coincidan campo a campo con
# $expected_gn_fields. Reutilizable para los tres esquemas (v1 sin
# tarjeta GN, v2 y v3 con GN de 10 campos cada uno).
assert_ge_gn_cards() {
    local nec_file="$1"
    local expected_ge="$2"
    local context="$3"
    shift 3
    local expected_gn_fields=("$@")

    local ge_lines
    ge_lines="$(grep -c "^GE " "$nec_file" || true)"
    if [[ "$ge_lines" -ne 1 ]]; then
        echo "$context: deberia contener exactamente una tarjeta GE y contiene $ge_lines." >&2
        exit 1
    fi
    local actual_ge
    actual_ge="$(grep "^GE " "$nec_file")"
    if [[ "$actual_ge" != "$expected_ge" ]]; then
        echo "$context: la tarjeta GE deberia ser '$expected_ge' y es '$actual_ge'." >&2
        exit 1
    fi

    local gn_count
    gn_count="$(grep -c "^GN " "$nec_file" || true)"

    if [[ "${#expected_gn_fields[@]}" -eq 0 ]]; then
        if [[ "$gn_count" -ne 0 ]]; then
            echo "$context: no deberia contener ninguna tarjeta GN y contiene $gn_count." >&2
            exit 1
        fi
        return 0
    fi

    if [[ "$gn_count" -ne 1 ]]; then
        echo "$context: deberia contener exactamente una tarjeta GN y contiene $gn_count." >&2
        exit 1
    fi

    local gn_line
    gn_line="$(grep "^GN " "$nec_file")"
    read -r -a gn_tokens <<< "$gn_line"

    local actual_fields=("${gn_tokens[@]:1}")
    if [[ "${#actual_fields[@]}" -ne "${#expected_gn_fields[@]}" ]]; then
        echo "$context: la tarjeta GN deberia tener ${#expected_gn_fields[@]} campos despues de 'GN' y tiene ${#actual_fields[@]}." >&2
        exit 1
    fi

    local index
    for index in "${!expected_gn_fields[@]}"; do
        if [[ "${actual_fields[$index]}" != "${expected_gn_fields[$index]}" ]]; then
            echo "$context: el campo $((index + 1)) de la tarjeta GN deberia ser '${expected_gn_fields[$index]}' y es '${actual_fields[$index]}'." >&2
            exit 1
        fi
    done
}

temp_dir="$(mktemp -d)"
cleanup() {
    rm -rf "$temp_dir"
}
trap cleanup EXIT

run_example() {
    local label="$1"
    local project="$2"
    local expected_schema="$3"
    local expected_impedance="$4"
    local expected_swr="$5"
    local expected_ge="$6"
    shift 6
    local expected_gn_fields=("$@")

    local project_path="$project_root/examples/$project"
    if [[ ! -f "$project_path" ]]; then
        echo "No se encontro el proyecto de ejemplo: $project_path" >&2
        exit 1
    fi

    echo "Validando $label ($project)..."
    local validation_output
    validation_output="$("$exe" validate "$project_path")"
    echo "$validation_output"
    assert_contains "$validation_output" "Schema version: $expected_schema" \
        "$label no se valido con schema_version $expected_schema."

    echo "Simulando $label..."
    local simulation_output
    simulation_output="$("$exe" simulate "$project_path")"
    echo "$simulation_output"
    assert_contains "$simulation_output" "Impedance: $expected_impedance" \
        "$label: la impedancia simulada no coincide con el valor esperado."
    assert_contains "$simulation_output" "SWR relative to 50 ohm: $expected_swr" \
        "$label: la SWR simulada no coincide con el valor esperado."

    echo "Ejecutando el barrido de $label..."
    local sweep_output
    sweep_output="$("$exe" sweep "$project_path")"
    echo "$sweep_output"
    assert_contains "$sweep_output" "Points: 81" \
        "$label: el barrido no reporto 81 puntos."

    local nec_file="$temp_dir/$project.nec"
    echo "Exportando NEC de $label..."
    "$exe" export-nec "$project_path" "$nec_file"

    if [[ ! -f "$nec_file" ]]; then
        echo "$label: no se genero el archivo NEC en $nec_file." >&2
        exit 1
    fi

    assert_ge_gn_cards "$nec_file" "$expected_ge" "$label" "${expected_gn_fields[@]}"
}

run_example \
    "el dipolo v1 (espacio libre)" \
    "dipole-20m.yaas" \
    "1" \
    "67.43 -31.25j ohm" \
    "1.83" \
    "GE 0"

run_example \
    "el monopolo v2 (tierra perfecta)" \
    "monopole-20m-perfect-ground.yaas" \
    "2" \
    "33.79 -15.62j ohm" \
    "1.72" \
    "GE 1" \
    "1" "0" "0" "0" "0" "0" "0" "0"

run_example \
    "el dipolo v3 (tierra real)" \
    "dipole-20m-real-ground.yaas" \
    "3" \
    "66.57 -41.36j ohm" \
    "2.13" \
    "GE 1" \
    "2" "0" "0" "0" "13" "0.005" "0" "0" "0" "0"

# Devuelve el numero de linea (1-based) de la unica linea exactamente
# igual a $2 en el archivo $1; falla si no aparece exactamente una vez.
line_number_of() {
    local file="$1"
    local expected="$2"
    local context="$3"
    local matches
    matches="$(grep -n -x -F -- "$expected" "$file" | cut -d: -f1 || true)"
    if [[ -z "$matches" || "$matches" == *$'\n'* ]]; then
        echo "$context: deberia contener exactamente una linea '$expected'." >&2
        exit 1
    fi
    echo "$matches"
}

run_pattern_example() {
    local project_path="$project_root/examples/dipole-20m-radiation-pattern.yaas"
    if [[ ! -f "$project_path" ]]; then
        echo "No se encontro el proyecto de ejemplo: $project_path" >&2
        exit 1
    fi

    echo "Validando el dipolo con patron de radiacion (schema v4)..."
    local validation_output
    validation_output="$("$exe" --language en validate "$project_path")"
    echo "$validation_output"
    assert_contains "$validation_output" "Schema version: 4" \
        "El dipolo con patron no se valido con schema_version 4."

    echo "Calculando el patron de radiacion..."
    local pattern_output
    pattern_output="$("$exe" --language en pattern "$project_path")"
    echo "$pattern_output"
    assert_contains "$pattern_output" "Frequency: 14.150 MHz" \
        "La frecuencia del patron no es la esperada."
    assert_contains "$pattern_output" "Grid: 181 x 1 (181 points)" \
        "La grilla del patron no es 181 x 1."
    assert_contains "$pattern_output" "Valid points: 180" \
        "El patron no reporta 180 puntos validos."
    assert_contains "$pattern_output" "Null points: 1" \
        "El patron no reporta exactamente un nulo."
    assert_contains "$pattern_output" "Maximum gain: 2.12 dBi" \
        "La ganancia maxima del patron no coincide con el valor validado con 4nec2."
    assert_contains "$pattern_output" "Direction of maximum: theta=0.00 deg, phi=0.00 deg" \
        "La direccion del maximo del patron no es la esperada."

    local csv_file="$temp_dir/pattern.csv"
    echo "Exportando el patron de radiacion a CSV..."
    local csv_output
    csv_output="$("$exe" --language en pattern "$project_path" --csv "$csv_file")"
    assert_contains "$csv_output" "CSV file:" \
        "pattern --csv no informo el archivo CSV creado."
    if [[ ! -f "$csv_file" ]]; then
        echo "No se genero el archivo CSV del patron en $csv_file." >&2
        exit 1
    fi

    # El CSV usa fin de linea CRLF (misma convencion que los demas CSV).
    local csv_header
    csv_header="$(head -n 1 "$csv_file" | tr -d '\r')"
    if [[ "$csv_header" != "frequency_mhz,theta_deg,phi_deg,gain_db" ]]; then
        echo "El encabezado del CSV del patron no es el esperado: $csv_header" >&2
        exit 1
    fi
    local csv_lines
    csv_lines="$(wc -l < "$csv_file")"
    if [[ "$csv_lines" -ne 182 ]]; then
        echo "El CSV del patron deberia tener 182 lineas y tiene $csv_lines." >&2
        exit 1
    fi
    local first_row
    first_row="$(sed -n '2p' "$csv_file" | tr -d '\r')"
    if [[ "$first_row" != "14.15,0.0,0.0,2.12"* ]]; then
        echo "El CSV del patron no contiene el maximo esperado en theta=0: $first_row" >&2
        exit 1
    fi
    if ! tr -d '\r' < "$csv_file" | grep -q -x -F "14.15,90.0,0.0,"; then
        echo "El CSV del patron no representa el nulo de theta=90 como campo vacio." >&2
        exit 1
    fi

    local nec_file="$temp_dir/pattern.nec"
    echo "Exportando NEC con tarjeta RP del patron de radiacion..."
    "$exe" --language en export-nec --pattern "$project_path" "$nec_file"
    if [[ ! -f "$nec_file" ]]; then
        echo "No se genero el archivo NEC del patron en $nec_file." >&2
        exit 1
    fi

    local context="El archivo NEC del patron de radiacion"
    local ex_line fr_line rp_line en_line
    ex_line="$(line_number_of "$nec_file" "EX 0 1 51 0 1 0" "$context")"
    fr_line="$(line_number_of "$nec_file" "FR 0 1 0 0 14.15 0" "$context")"
    rp_line="$(line_number_of "$nec_file" "RP 0 181 1 0000 0 0 1 0 0 0" "$context")"
    en_line="$(line_number_of "$nec_file" "EN" "$context")"
    if ! (( ex_line < fr_line && fr_line < rp_line && rp_line < en_line )); then
        echo "$context no respeta el orden EX < FR < RP < EN." >&2
        exit 1
    fi
    if [[ "$en_line" -ne "$(wc -l < "$nec_file")" ]]; then
        echo "$context: EN no es la ultima tarjeta." >&2
        exit 1
    fi
    if grep -q "^XQ" "$nec_file"; then
        echo "$context no deberia contener XQ." >&2
        exit 1
    fi

    assert_ge_gn_cards "$nec_file" "GE 0" "$context"
}

run_pattern_example

echo ""
echo "Build experimental de Linux completado correctamente."
echo "Ejecutable: $exe"
