"""CLI: comando ``pattern`` y ``export-nec --pattern``."""

import math

import pytest

import yaas.application.radiation_pattern as pattern_workflow
from yaas.cli.main import main
from yaas.domain import RadiationPatternResult
from yaas.engines import pynec as pynec_module
from yaas.exporters import (
    radiation_pattern_request_to_nec,
    radiation_pattern_to_csv,
    simulation_request_to_nec,
    sweep_request_to_nec,
)
from yaas.projects import load_project

PATTERN_EXAMPLE = "examples/dipole-20m-radiation-pattern.yaas"
NO_PATTERN_EXAMPLE = "examples/dipole-20m.yaas"


@pytest.fixture(autouse=True)
def use_spanish_cli(monkeypatch):
    """Mismo idioma por defecto que tests/test_cli.py."""
    monkeypatch.setenv("YAAS_LANGUAGE", "es")


class FakePatternEngine:
    """Reemplaza PyNecEngine.simulate_radiation_pattern y cuenta llamadas."""

    def __init__(self, monkeypatch, result=None, error=None):
        self.calls = 0

        def simulate(_engine, _request):
            self.calls += 1
            if error is not None:
                raise error
            return result

        monkeypatch.setattr(
            pynec_module.PyNecEngine,
            "simulate_radiation_pattern",
            simulate,
        )


def pattern_result(gain_db, theta=(10.0, 20.0), phi=(30.0, 40.0)):
    return RadiationPatternResult(
        frequency_mhz=14.15,
        theta_angles_deg=theta,
        phi_angles_deg=phi,
        gain_db=gain_db,
    )


@pytest.fixture
def forbid_pynec(monkeypatch):
    """Falla si algún comando instancia PyNecEngine."""

    def _fail_init(self):
        raise AssertionError("PyNecEngine no debe instanciarse.")

    monkeypatch.setattr(pynec_module.PyNecEngine, "__init__", _fail_init)


# ---------------------------------------------------------------------------
# Ayuda
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "language,expected",
    [
        ("es", "Calcular el patrón de radiación"),
        ("en", "Calculate the radiation pattern"),
    ],
)
def test_main_help_lists_the_pattern_command(capsys, language, expected):
    with pytest.raises(SystemExit) as exit_info:
        main(["--language", language, "--help"])

    output = capsys.readouterr().out

    assert exit_info.value.code == 0
    assert "pattern" in output
    assert expected in output


@pytest.mark.parametrize(
    "language,expected",
    [
        ("es", "Archivo CSV donde guardar el patrón de radiación."),
        ("en", "CSV file where the radiation pattern will be saved."),
    ],
)
def test_pattern_help_lists_csv_option(capsys, language, expected):
    with pytest.raises(SystemExit) as exit_info:
        main(["--language", language, "pattern", "--help"])

    output = capsys.readouterr().out

    assert exit_info.value.code == 0
    assert "--csv" in output
    assert expected in " ".join(output.split())


@pytest.mark.parametrize(
    "language,expected",
    [
        ("es", "No puede combinarse con --sweep."),
        ("en", "Cannot be combined with --sweep."),
    ],
)
def test_export_nec_help_lists_pattern_option(capsys, language, expected):
    with pytest.raises(SystemExit) as exit_info:
        main(["--language", language, "export-nec", "--help"])

    output = capsys.readouterr().out

    assert exit_info.value.code == 0
    assert "--pattern" in output
    assert "--sweep" in output
    assert expected in " ".join(output.split())


# ---------------------------------------------------------------------------
# pattern con el motor real (ejemplo v4, 181 x 1)
# ---------------------------------------------------------------------------


def test_pattern_summary_in_spanish(capsys):
    exit_code = main(["--language", "es", "pattern", PATTERN_EXAMPLE])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.err == ""
    assert captured.out.splitlines() == [
        "Calculando patrón de radiación: "
        "Dipolo de 20 metros - patrón de radiación",
        "Frecuencia: 14.150 MHz",
        "Grilla: 181 x 1 (181 puntos)",
        "Puntos válidos: 180",
        "Nulos: 1",
        "Ganancia máxima: 2.12 dBi",
        "Dirección del máximo: theta=0.00 grados, phi=0.00 grados",
    ]


def test_pattern_summary_in_english(capsys):
    exit_code = main(["--language", "en", "pattern", PATTERN_EXAMPLE])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert output.splitlines()[1:] == [
        "Frequency: 14.150 MHz",
        "Grid: 181 x 1 (181 points)",
        "Valid points: 180",
        "Null points: 1",
        "Maximum gain: 2.12 dBi",
        "Direction of maximum: theta=0.00 deg, phi=0.00 deg",
    ]


def test_pattern_csv_with_real_engine(tmp_path, capsys):
    destination = tmp_path / "patron.csv"

    exit_code = main(
        ["pattern", PATTERN_EXAMPLE, "--csv", str(destination)]
    )
    output = capsys.readouterr().out

    lines = destination.read_text(encoding="utf-8").splitlines()
    assert exit_code == 0
    assert f"Archivo CSV: {destination.resolve()}" in output
    assert lines[0] == "frequency_mhz,theta_deg,phi_deg,gain_db"
    assert len(lines) == 1 + 181
    # Máximo válido en theta=0 y nulo (celda vacía) en theta=90.
    assert lines[1].startswith("14.15,0.0,0.0,2.12")
    assert lines[1 + 90] == "14.15,90.0,0.0,"


# ---------------------------------------------------------------------------
# Resumen: empate y todos nulos (motor sustituido)
# ---------------------------------------------------------------------------


def test_pattern_tie_selects_first_theta_major_sample(monkeypatch, capsys):
    # (10, 40) y (20, 30) empatan en 5.0: gana la primera en el orden
    # theta externo / phi interno.
    FakePatternEngine(
        monkeypatch,
        result=pattern_result(((1.0, 5.0), (5.0, None))),
    )

    exit_code = main(["pattern", PATTERN_EXAMPLE])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Grilla: 2 x 2 (4 puntos)" in output
    assert "Puntos válidos: 3" in output
    assert "Nulos: 1" in output
    assert "Ganancia máxima: 5.00 dBi" in output
    assert (
        "Dirección del máximo: theta=10.00 grados, phi=40.00 grados"
        in output
    )


def test_pattern_maximum_ignores_nulls_and_negative_gains(
    monkeypatch, capsys,
):
    FakePatternEngine(
        monkeypatch,
        result=pattern_result(((None, -30.0), (-4.5, None))),
    )

    main(["pattern", PATTERN_EXAMPLE])
    output = capsys.readouterr().out

    assert "Ganancia máxima: -4.50 dBi" in output
    assert "theta=20.00 grados, phi=30.00 grados" in output


@pytest.mark.parametrize(
    "language,expected",
    [
        (
            "es",
            "Ganancia máxima: no disponible; el patrón no tiene "
            "ganancias finitas.",
        ),
        (
            "en",
            "Maximum gain: unavailable; the pattern has no finite "
            "gain values.",
        ),
    ],
)
def test_pattern_with_only_nulls_succeeds(
    monkeypatch, capsys, language, expected
):
    FakePatternEngine(
        monkeypatch,
        result=pattern_result(((None, None), (None, None))),
    )

    exit_code = main(["--language", language, "pattern", PATTERN_EXAMPLE])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.err == ""
    assert expected in captured.out
    assert "dBi" not in captured.out
    assert "theta=" not in captured.out


# ---------------------------------------------------------------------------
# Máximo del resumen (yaas.application): empate numérico, tolerancia 1e-9 dB
# ---------------------------------------------------------------------------

# Ganancia de theta=0 observada en Ubuntu 24.04 para el ejemplo v4.
BASE_GAIN_DB = 2.1232781085185755


def vertical_cut(*gains):
    """Corte con un theta por ganancia (0, 1, 2, ... grados) y phi=0."""
    return pattern_result(
        tuple((gain,) for gain in gains),
        theta=tuple(float(index) for index in range(len(gains))),
        phi=(0.0,),
    )


def test_tie_tolerance_is_absolute_and_small():
    assert pattern_workflow._PATTERN_GAIN_TIE_TOLERANCE_DB == 1e-9


@pytest.mark.parametrize(
    "gains,expected_theta",
    [
        # Máximos exactamente iguales: la primera muestra.
        ((BASE_GAIN_DB, BASE_GAIN_DB), 0.0),
        # Ruido observado en CI entre theta=0 y theta=180 (~3.6e-15 dB).
        ((BASE_GAIN_DB, 2.1232781085185790), 0.0),
        # Mayor, pero dentro de la tolerancia: sigue la primera.
        ((BASE_GAIN_DB, BASE_GAIN_DB + 5e-10), 0.0),
        # Mayor por más que la tolerancia: la segunda.
        ((BASE_GAIN_DB, BASE_GAIN_DB + 2e-9), 1.0),
        # Una muestra posterior claramente mayor.
        ((1.0, 2.0, 5.0, 3.0), 2.0),
        # Los nulos se ignoran, también en primera posición.
        ((None, 1.0, None, 4.0), 3.0),
    ],
    ids=[
        "exact_tie",
        "ci_float_noise",
        "within_tolerance",
        "beyond_tolerance",
        "clearly_greater_later",
        "nulls_ignored",
    ],
)
def test_find_pattern_maximum_boundaries(gains, expected_theta):
    maximum = pattern_workflow.summarize_radiation_pattern(
        vertical_cut(*gains)
    ).maximum

    assert maximum.theta_deg == expected_theta
    # El valor informado es el de la muestra elegida, sin redondeo.
    assert maximum.gain_db == gains[int(expected_theta)]


def test_boundary_differences_straddle_the_tolerance():
    # Precondición de los casos anteriores: 5e-10 queda dentro y 2e-9
    # fuera de la tolerancia absoluta, con rel_tol=0.0.
    tolerance = pattern_workflow._PATTERN_GAIN_TIE_TOLERANCE_DB

    assert math.isclose(
        BASE_GAIN_DB + 5e-10, BASE_GAIN_DB, rel_tol=0.0, abs_tol=tolerance
    )
    assert not math.isclose(
        BASE_GAIN_DB + 2e-9, BASE_GAIN_DB, rel_tol=0.0, abs_tol=tolerance
    )


def test_find_pattern_maximum_with_only_nulls():
    assert pattern_workflow.summarize_radiation_pattern(
        vertical_cut(None, None)
    ).maximum is None


def test_tie_rule_keeps_theta_0_for_the_ci_values(monkeypatch, capsys):
    # Reproduce el fallo de CI: theta=180 apenas "mayor" que theta=0.
    gains = [None] * 181
    gains[0] = BASE_GAIN_DB
    gains[180] = 2.1232781085185790
    gains[1] = BASE_GAIN_DB - 0.002
    FakePatternEngine(
        monkeypatch,
        result=pattern_result(
            tuple((gain,) for gain in gains),
            theta=tuple(float(theta) for theta in range(181)),
            phi=(0.0,),
        ),
    )

    main(["--language", "en", "pattern", PATTERN_EXAMPLE])
    output = capsys.readouterr().out

    assert "Direction of maximum: theta=0.00 deg, phi=0.00 deg" in output


# ---------------------------------------------------------------------------
# pattern --csv (motor sustituido)
# ---------------------------------------------------------------------------


def test_pattern_csv_uses_the_same_single_result(
    tmp_path, monkeypatch, capsys,
):
    result = pattern_result(((2.5, None), (-1.25, 0.0)))
    engine = FakePatternEngine(monkeypatch, result=result)
    destination = tmp_path / "patron.csv"

    exit_code = main(
        ["pattern", PATTERN_EXAMPLE, "--csv", str(destination)]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert engine.calls == 1
    assert destination.read_bytes() == (
        radiation_pattern_to_csv(result).encode("utf-8")
    )
    assert "14.15,10.0,40.0,\r\n" in destination.read_text(
        encoding="utf-8", newline=""
    )
    assert output.rstrip().endswith(
        f"Archivo CSV: {destination.resolve()}"
    )


def test_pattern_without_csv_runs_the_engine_once(monkeypatch, capsys):
    engine = FakePatternEngine(
        monkeypatch,
        result=pattern_result(((1.0, 2.0), (3.0, 4.0))),
    )

    main(["pattern", PATTERN_EXAMPLE])
    capsys.readouterr()

    assert engine.calls == 1


@pytest.mark.parametrize(
    "language,expected",
    [
        ("es", "No se pudo escribir el archivo CSV:"),
        ("en", "Could not write CSV file:"),
    ],
)
def test_pattern_csv_write_failure_does_not_report_success(
    tmp_path, monkeypatch, capsys, language, expected
):
    FakePatternEngine(
        monkeypatch,
        result=pattern_result(((1.0, 2.0), (3.0, 4.0))),
    )
    destination = tmp_path / "no-existe" / "patron.csv"

    exit_code = main(
        [
            "--language", language,
            "pattern", PATTERN_EXAMPLE, "--csv", str(destination),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 2
    assert expected in captured.err
    assert "CSV file:" not in captured.out
    assert "Archivo CSV:" not in captured.out
    assert not destination.exists()


# ---------------------------------------------------------------------------
# pattern: errores
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "language,expected",
    [
        (
            "es",
            "Proyecto inválido: el proyecto no define un patrón de "
            "radiación (simulation.radiation_pattern).",
        ),
        (
            "en",
            "Invalid project: the project does not define a radiation "
            "pattern (simulation.radiation_pattern).",
        ),
    ],
)
def test_pattern_rejects_project_without_pattern(
    tmp_path, capsys, forbid_pynec, language, expected
):
    destination = tmp_path / "patron.csv"

    exit_code = main(
        [
            "--language", language,
            "pattern", NO_PATTERN_EXAMPLE, "--csv", str(destination),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.out == ""
    assert expected in captured.err
    assert "Traceback" not in captured.err
    assert not destination.exists()


def test_pattern_rejects_missing_file(tmp_path, capsys):
    exit_code = main(["pattern", str(tmp_path / "no-existe.yaas")])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.out == ""
    assert "Proyecto inválido:" in captured.err


def test_pattern_rejects_invalid_project(tmp_path, capsys):
    project = tmp_path / "roto.yaas"
    project.write_text("{no es JSON", encoding="utf-8")

    exit_code = main(["pattern", str(project)])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.out == ""
    assert "Proyecto inválido:" in captured.err


@pytest.mark.parametrize(
    "error",
    [RuntimeError("salida nativa inesperada"), ValueError("modelo")],
    ids=["runtime_error", "value_error"],
)
def test_pattern_reports_engine_failure(
    tmp_path, monkeypatch, capsys, error
):
    FakePatternEngine(monkeypatch, error=error)
    destination = tmp_path / "patron.csv"

    exit_code = main(
        ["pattern", PATTERN_EXAMPLE, "--csv", str(destination)]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert (
        f"Falló el cálculo del patrón de radiación: {error}"
        in captured.err
    )
    assert not destination.exists()


# ---------------------------------------------------------------------------
# export-nec
# ---------------------------------------------------------------------------


def test_export_nec_without_options_keeps_point_export(tmp_path, capsys):
    destination = tmp_path / "puntual.nec"

    exit_code = main(["export-nec", PATTERN_EXAMPLE, str(destination)])
    capsys.readouterr()

    project = load_project(PATTERN_EXAMPLE)
    assert exit_code == 0
    assert destination.read_text(encoding="utf-8") == (
        simulation_request_to_nec(
            project.to_simulation_request(),
            title=project.metadata.name,
        )
    )
    assert "RP " not in destination.read_text(encoding="utf-8")


def test_export_nec_sweep_keeps_sweep_export(tmp_path, capsys):
    destination = tmp_path / "barrido.nec"

    exit_code = main(
        ["export-nec", PATTERN_EXAMPLE, str(destination), "--sweep"]
    )
    capsys.readouterr()

    project = load_project(PATTERN_EXAMPLE)
    assert exit_code == 0
    assert destination.read_text(encoding="utf-8") == (
        sweep_request_to_nec(
            project.to_sweep_request(),
            title=project.metadata.name,
        )
    )
    assert "RP " not in destination.read_text(encoding="utf-8")


def test_export_nec_pattern_writes_rp_without_running_pynec(
    tmp_path, capsys, forbid_pynec,
):
    destination = tmp_path / "patron.nec"

    exit_code = main(
        ["export-nec", PATTERN_EXAMPLE, str(destination), "--pattern"]
    )
    output = capsys.readouterr().out

    project = load_project(PATTERN_EXAMPLE)
    text = destination.read_text(encoding="utf-8")
    lines = text.splitlines()

    assert exit_code == 0
    assert output == f"Archivo NEC: {destination.resolve()}\n"
    assert text == radiation_pattern_request_to_nec(
        project.to_radiation_pattern_request(),
        title=project.metadata.name,
        reference_impedance=project.reference_impedance,
    )
    assert lines[-4:] == [
        "EX 0 1 51 0 1 0",
        "FR 0 1 0 0 14.15 0",
        "RP 0 181 1 0000 0 0 1 0 0 0",
        "EN",
    ]
    assert not any(line.startswith("XQ") for line in lines)


@pytest.mark.parametrize(
    "language,expected",
    [
        ("es", "Error: --pattern y --sweep no pueden usarse juntos."),
        ("en", "Error: --pattern and --sweep cannot be used together."),
    ],
)
def test_export_nec_rejects_pattern_with_sweep(
    tmp_path, capsys, language, expected
):
    destination = tmp_path / "salida.nec"

    exit_code = main(
        [
            "--language", language, "export-nec",
            PATTERN_EXAMPLE, str(destination), "--pattern", "--sweep",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.out == ""
    assert expected in captured.err
    assert not destination.exists()


@pytest.mark.parametrize(
    "language,expected",
    [
        ("es", "Proyecto inválido: el proyecto no define un patrón"),
        ("en", "Invalid project: the project does not define a"),
    ],
)
def test_export_nec_pattern_rejects_project_without_pattern(
    tmp_path, capsys, language, expected
):
    destination = tmp_path / "salida.nec"

    exit_code = main(
        [
            "--language", language, "export-nec",
            NO_PATTERN_EXAMPLE, str(destination), "--pattern",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.out == ""
    assert expected in captured.err
    assert "Traceback" not in captured.err
    assert not destination.exists()


def test_export_nec_pattern_reports_write_failure(tmp_path, capsys):
    destination = tmp_path / "no-existe" / "patron.nec"

    exit_code = main(
        ["export-nec", PATTERN_EXAMPLE, str(destination), "--pattern"]
    )
    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.out == ""
    assert "No se pudo escribir el archivo NEC:" in captured.err
