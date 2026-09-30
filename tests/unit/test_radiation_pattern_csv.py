"""Exportación CSV de RadiationPatternResult."""

import csv
import io
import locale

import pytest

from yaas.domain import (
    RadiationPatternResult,
    SimulationResult,
    SweepPoint,
    SweepResult,
)
from yaas.exporters import (
    export_radiation_pattern_csv,
    radiation_pattern_to_csv,
)

HEADER = "frequency_mhz,theta_deg,phi_deg,gain_db\r\n"


def build_result(**overrides) -> RadiationPatternResult:
    values = {
        "frequency_mhz": 14.15,
        "theta_angles_deg": (0.0, 90.0),
        "phi_angles_deg": (0.0, 90.0, 180.0),
        "gain_db": (
            (2.5, 0.0, -1.25),
            (None, 2.1232781085189183, None),
        ),
    }
    values.update(overrides)
    return RadiationPatternResult(**values)


def parse(text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text, newline="")))


# ---------------------------------------------------------------------------
# Contenido exacto
# ---------------------------------------------------------------------------


def test_single_cell_result_exact_text():
    result = build_result(
        theta_angles_deg=(90.0,),
        phi_angles_deg=(90.0,),
        gain_db=((2.1233,),),
    )

    assert radiation_pattern_to_csv(result) == (
        HEADER
        + "14.15,90.0,90.0,2.1233\r\n"
    )


def test_non_square_result_exact_text_and_order():
    # 2x3: theta en el lazo externo, phi en el interno; frecuencia en
    # cada fila; los None como campos vacíos.
    assert radiation_pattern_to_csv(build_result()) == (
        HEADER
        + "14.15,0.0,0.0,2.5\r\n"
        "14.15,0.0,90.0,0.0\r\n"
        "14.15,0.0,180.0,-1.25\r\n"
        "14.15,90.0,0.0,\r\n"
        "14.15,90.0,90.0,2.1232781085189183\r\n"
        "14.15,90.0,180.0,\r\n"
    )


def test_row_order_matches_domain_samples():
    result = build_result()
    rows = parse(radiation_pattern_to_csv(result))[1:]

    assert [(float(row[1]), float(row[2])) for row in rows] == [
        (sample.theta_deg, sample.phi_deg) for sample in result.samples
    ]
    assert all(float(row[0]) == 14.15 for row in rows)


def test_text_ends_with_a_single_line_break():
    text = radiation_pattern_to_csv(build_result())

    assert text.endswith("\r\n")
    assert not text.endswith("\r\n\r\n")


# ---------------------------------------------------------------------------
# Nulos y el centinela de NEC
# ---------------------------------------------------------------------------


def test_none_is_an_empty_field():
    text = radiation_pattern_to_csv(build_result())

    null_rows = [row for row in parse(text)[1:] if row[3] == ""]
    assert len(null_rows) == 2
    for forbidden in ("-999.99", "None", "null", "NaN", "nan", "N/A"):
        assert forbidden not in text


def test_all_null_cut_writes_only_empty_gain_fields():
    result = build_result(
        theta_angles_deg=(90.0,),
        phi_angles_deg=(0.0, 180.0, 360.0),
        gain_db=((None, None, None),),
    )

    assert radiation_pattern_to_csv(result) == (
        HEADER
        + "14.15,90.0,0.0,\r\n"
        "14.15,90.0,180.0,\r\n"
        "14.15,90.0,360.0,\r\n"
    )


def test_numeric_sentinel_is_written_as_a_number():
    # Traducir -999.99 a None le corresponde al adaptador PyNEC, no al
    # CSV: un -999.99 presente en el dominio es un número más.
    result = build_result(
        theta_angles_deg=(90.0,),
        phi_angles_deg=(0.0,),
        gain_db=((-999.99,),),
    )

    assert radiation_pattern_to_csv(result) == (
        HEADER + "14.15,90.0,0.0,-999.99\r\n"
    )


# ---------------------------------------------------------------------------
# Formato numérico
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "frequency_mhz,theta,phi,gain,expected_row",
    [
        (14.15, 43.0, 0.0, 0.0944, "14.15,43.0,0.0,0.0944"),
        (14.15, 0.0, 0.0, 0.0, "14.15,0.0,0.0,0.0"),
        (14.15, 89.0, 0.0, -29.5103, "14.15,89.0,0.0,-29.5103"),
        # Valor completo de PyNEC: sin redondeo.
        (
            14.15, 1.0, 0.0, -31.968442202556943,
            "14.15,1.0,0.0,-31.968442202556943",
        ),
        # Frecuencia, ángulos y ganancia enteros.
        (14, 90, 270, 5, "14,90,270,5"),
        # Decimales y valores pequeños.
        (7.0125, 0.5, 12.25, 1e-05, "7.0125,0.5,12.25,1e-05"),
        (0.001, 0.001, 359.999, -0.000125, "0.001,0.001,359.999,-0.000125"),
    ],
    ids=[
        "positive",
        "zero",
        "negative",
        "full_precision",
        "integers",
        "decimals",
        "small_values",
    ],
)
def test_number_format(frequency_mhz, theta, phi, gain, expected_row):
    result = RadiationPatternResult(
        frequency_mhz=frequency_mhz,
        theta_angles_deg=(theta,),
        phi_angles_deg=(phi,),
        gain_db=((gain,),),
    )

    assert radiation_pattern_to_csv(result) == HEADER + expected_row + "\r\n"


def test_numbers_round_trip_exactly():
    result = build_result()
    rows = parse(radiation_pattern_to_csv(result))[1:]

    assert [
        None if row[3] == "" else float(row[3]) for row in rows
    ] == [sample.gain_db for sample in result.samples]


def test_output_does_not_depend_on_the_locale():
    expected = radiation_pattern_to_csv(build_result())
    previous = locale.setlocale(locale.LC_ALL)

    for candidate in ("de_DE.UTF-8", "de_DE", "German_Germany.1252"):
        try:
            locale.setlocale(locale.LC_ALL, candidate)
            break
        except locale.Error:
            continue
    else:
        pytest.skip("No hay un locale con coma decimal disponible.")

    try:
        assert radiation_pattern_to_csv(build_result()) == expected
    finally:
        locale.setlocale(locale.LC_ALL, previous)


# ---------------------------------------------------------------------------
# Escritura de archivos
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("as_string", [False, True], ids=["path", "str"])
def test_export_writes_exactly_the_in_memory_text(tmp_path, as_string):
    result = build_result()
    destination = tmp_path / "patron.csv"

    returned = export_radiation_pattern_csv(
        result,
        str(destination) if as_string else destination,
    )

    assert returned == destination
    assert destination.read_bytes() == (
        radiation_pattern_to_csv(result).encode("utf-8")
    )
    content = destination.read_bytes()
    assert not content.startswith(b"\xef\xbb\xbf")  # sin BOM
    assert content.endswith(b"\r\n")
    assert not content.endswith(b"\r\n\r\n")


def test_export_overwrites_an_existing_file(tmp_path):
    # Mismo comportamiento que export_sweep_csv/export_comparison_csv:
    # el archivo existente se reemplaza.
    destination = tmp_path / "patron.csv"
    destination.write_text("contenido anterior\n", encoding="utf-8")
    result = build_result(
        theta_angles_deg=(90.0,),
        phi_angles_deg=(90.0,),
        gain_db=((2.1233,),),
    )

    export_radiation_pattern_csv(result, destination)

    assert destination.read_bytes() == (
        HEADER + "14.15,90.0,90.0,2.1233\r\n"
    ).encode("utf-8")


def test_export_does_not_create_missing_directories(tmp_path):
    # Igual que los demás exportadores CSV: el directorio debe existir.
    destination = tmp_path / "no-existe" / "patron.csv"

    with pytest.raises(FileNotFoundError):
        export_radiation_pattern_csv(build_result(), destination)


# ---------------------------------------------------------------------------
# Tipos incorrectos
# ---------------------------------------------------------------------------

WRONG_TYPES = [
    pytest.param(None, id="none"),
    pytest.param("14.15,90,0,", id="string"),
    pytest.param(
        SimulationResult(
            frequency_mhz=14.15,
            impedance=complex(67.43, -31.25),
            swr=1.83,
        ),
        id="simulation_result",
    ),
    pytest.param(
        SweepResult(
            points=(
                SweepPoint(
                    frequency_mhz=14.15,
                    impedance=complex(67.43, -31.25),
                    swr=1.83,
                ),
            )
        ),
        id="sweep_result",
    ),
]


@pytest.mark.parametrize("wrong", WRONG_TYPES)
def test_to_csv_rejects_other_types(wrong):
    with pytest.raises(TypeError, match="RadiationPatternResult"):
        radiation_pattern_to_csv(wrong)


@pytest.mark.parametrize("wrong", WRONG_TYPES)
def test_export_rejects_other_types_without_creating_a_file(tmp_path, wrong):
    destination = tmp_path / "patron.csv"

    with pytest.raises(TypeError, match="RadiationPatternResult"):
        export_radiation_pattern_csv(wrong, destination)

    assert not destination.exists()


def test_export_rejection_leaves_an_existing_file_untouched(tmp_path):
    destination = tmp_path / "patron.csv"
    destination.write_bytes(b"previo\r\n")

    with pytest.raises(TypeError):
        export_radiation_pattern_csv(None, destination)

    assert destination.read_bytes() == b"previo\r\n"


# ---------------------------------------------------------------------------
# Resultado con valores documentados del motor
# ---------------------------------------------------------------------------


def test_documented_real_ground_cut_keeps_null_and_precision(tmp_path):
    # Valores completos de PyNEC para el dipolo a 10 m sobre tierra real
    # (docs/research/nec-radiation-patterns.md,
    # docs/validation/radiation-patterns-4nec2.md): máximo en
    # theta=43, nulo exacto en el horizonte, ya traducido a None por el
    # adaptador del motor.
    result = RadiationPatternResult(
        frequency_mhz=14.15,
        theta_angles_deg=(0.0, 43.0, 89.0, 90.0),
        phi_angles_deg=(0.0,),
        gain_db=(
            (-4.956962614803608,),
            (0.09435248827252335,),
            (-29.510283658955668,),
            (None,),
        ),
    )
    destination = tmp_path / "tierra-real.csv"

    export_radiation_pattern_csv(result, destination)

    assert destination.read_text(encoding="utf-8", newline="") == (
        HEADER
        + "14.15,0.0,0.0,-4.956962614803608\r\n"
        "14.15,43.0,0.0,0.09435248827252335\r\n"
        "14.15,89.0,0.0,-29.510283658955668\r\n"
        "14.15,90.0,0.0,\r\n"
    )
