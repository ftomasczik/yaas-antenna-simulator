"""Casos de uso de patrones de radiación (yaas.application), sin PyNEC."""

import dataclasses
import subprocess
import sys
import textwrap

import pytest

from yaas.application import (
    MissingRadiationPatternError,
    RadiationPatternAnalysis,
    RadiationPatternSummary,
    calculate_radiation_pattern,
    export_project_radiation_pattern_nec,
    prepare_radiation_pattern_request,
    summarize_radiation_pattern,
)
from yaas.domain import RadiationPatternResult, RadiationPatternSample
from yaas.exporters import radiation_pattern_request_to_nec
from yaas.projects import load_project

PATTERN_EXAMPLE = "examples/dipole-20m-radiation-pattern.yaas"
NO_PATTERN_EXAMPLE = "examples/dipole-20m.yaas"

# Ganancia de theta=0 observada en Ubuntu 24.04 para el ejemplo v4.
BASE_GAIN_DB = 2.1232781085185755


def result_with(gain_db, theta=None, phi=(0.0,)):
    """Resultado con un theta por fila (0, 1, 2... grados) por defecto."""
    if theta is None:
        theta = tuple(float(index) for index in range(len(gain_db)))
    return RadiationPatternResult(
        frequency_mhz=14.15,
        theta_angles_deg=theta,
        phi_angles_deg=phi,
        gain_db=gain_db,
    )


def vertical_cut(*gains):
    return result_with(tuple((gain,) for gain in gains))


class FakeEngine:
    """Implementa el protocolo SimulationEngine sin PyNEC."""

    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.requests = []

    def simulate(self, request):
        raise AssertionError("simulate no debe llamarse")

    def simulate_sweep(self, request):
        raise AssertionError("simulate_sweep no debe llamarse")

    def simulate_radiation_pattern(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return self.result


# ---------------------------------------------------------------------------
# summarize_radiation_pattern
# ---------------------------------------------------------------------------


def test_single_valid_cell():
    summary = summarize_radiation_pattern(vertical_cut(2.5))

    assert summary == RadiationPatternSummary(
        total_points=1,
        valid_points=1,
        null_points=0,
        maximum=RadiationPatternSample(theta_deg=0.0, phi_deg=0.0, gain_db=2.5),
    )


def test_mix_of_valid_and_null_gains():
    result = result_with(
        ((1.0, None, 3.0), (None, -2.0, None)),
        theta=(0.0, 90.0),
        phi=(0.0, 90.0, 180.0),
    )

    summary = summarize_radiation_pattern(result)

    assert (summary.total_points, summary.valid_points, summary.null_points) == (
        6, 3, 3,
    )
    assert summary.maximum == RadiationPatternSample(
        theta_deg=0.0, phi_deg=180.0, gain_db=3.0
    )


def test_only_null_gains():
    summary = summarize_radiation_pattern(vertical_cut(None, None, None))

    assert (summary.total_points, summary.valid_points, summary.null_points) == (
        3, 0, 3,
    )
    assert summary.maximum is None


def test_negative_gains_are_valid_candidates():
    summary = summarize_radiation_pattern(vertical_cut(None, -30.0, -4.5, None))

    assert summary.maximum.theta_deg == 2.0
    assert summary.maximum.gain_db == -4.5


@pytest.mark.parametrize(
    "gains,expected_theta",
    [
        ((BASE_GAIN_DB, BASE_GAIN_DB), 0.0),
        # Ruido observado en CI entre theta=0 y theta=180 (~3.6e-15 dB).
        ((BASE_GAIN_DB, 2.1232781085185790), 0.0),
        ((BASE_GAIN_DB, BASE_GAIN_DB + 5e-10), 0.0),
        ((BASE_GAIN_DB, BASE_GAIN_DB + 2e-9), 1.0),
        ((1.0, 2.0, 5.0, 3.0), 2.0),
    ],
    ids=[
        "exact_tie",
        "ci_float_noise",
        "within_tolerance",
        "beyond_tolerance",
        "clearly_greater_later",
    ],
)
def test_maximum_tie_rule(gains, expected_theta):
    maximum = summarize_radiation_pattern(vertical_cut(*gains)).maximum

    assert maximum.theta_deg == expected_theta
    # El valor informado es el de la muestra elegida, sin modificar.
    assert maximum.gain_db == gains[int(expected_theta)]


def test_maximum_tie_keeps_first_theta_major_sample():
    # (10, 40) y (20, 30) empatan: gana la primera en theta externo /
    # phi interno, no la de menor phi.
    result = result_with(
        ((1.0, 5.0), (5.0, None)),
        theta=(10.0, 20.0),
        phi=(30.0, 40.0),
    )

    maximum = summarize_radiation_pattern(result).maximum

    assert (maximum.theta_deg, maximum.phi_deg) == (10.0, 40.0)


def test_summary_does_not_modify_the_result():
    result = vertical_cut(BASE_GAIN_DB, None, -1.0)
    snapshot = dataclasses.replace(result)

    summarize_radiation_pattern(result)

    assert result == snapshot


def test_summary_is_immutable():
    summary = summarize_radiation_pattern(vertical_cut(1.0))

    with pytest.raises(dataclasses.FrozenInstanceError):
        summary.valid_points = 0  # type: ignore[misc]


VALID_MAXIMUM = RadiationPatternSample(theta_deg=0.0, phi_deg=0.0, gain_db=1.0)
NULL_SAMPLE = RadiationPatternSample(theta_deg=0.0, phi_deg=0.0, gain_db=None)


@pytest.mark.parametrize(
    "fields",
    [
        {"total_points": -1, "valid_points": 0, "null_points": -1, "maximum": None},
        {"total_points": 1, "valid_points": -1, "null_points": 2, "maximum": None},
        {"total_points": 2, "valid_points": 1, "null_points": 2, "maximum": VALID_MAXIMUM},
        {"total_points": 2, "valid_points": 0, "null_points": 2, "maximum": VALID_MAXIMUM},
        {"total_points": 1, "valid_points": 1, "null_points": 0, "maximum": None},
        {"total_points": 1, "valid_points": 1, "null_points": 0, "maximum": NULL_SAMPLE},
        {"total_points": 1, "valid_points": 1, "null_points": 0, "maximum": "max"},
        {"total_points": True, "valid_points": 1, "null_points": 0, "maximum": VALID_MAXIMUM},
        {"total_points": 1.0, "valid_points": 1, "null_points": 0, "maximum": VALID_MAXIMUM},
    ],
    ids=[
        "negative_total",
        "negative_valid",
        "counts_do_not_add_up",
        "maximum_without_valid_points",
        "valid_points_without_maximum",
        "null_maximum",
        "maximum_not_a_sample",
        "bool_count",
        "float_count",
    ],
)
def test_summary_rejects_invalid_invariants(fields):
    with pytest.raises(ValueError):
        RadiationPatternSummary(**fields)


# ---------------------------------------------------------------------------
# prepare_radiation_pattern_request + calculate_radiation_pattern
# ---------------------------------------------------------------------------


def test_prepare_uses_the_project_request():
    project = load_project(PATTERN_EXAMPLE)

    assert prepare_radiation_pattern_request(project) == (
        project.to_radiation_pattern_request()
    )


def test_prepare_rejects_project_without_pattern():
    project = load_project(NO_PATTERN_EXAMPLE)

    with pytest.raises(MissingRadiationPatternError) as error:
        prepare_radiation_pattern_request(project)

    # Es un ValueError: quien ya atrapaba el error del proyecto sigue
    # funcionando, y la causa original se conserva.
    assert isinstance(error.value, ValueError)
    assert isinstance(error.value.__cause__, ValueError)


def test_calculate_calls_the_engine_once_and_keeps_identities():
    project = load_project(PATTERN_EXAMPLE)
    request = prepare_radiation_pattern_request(project)
    result = vertical_cut(None, BASE_GAIN_DB, 1.0)
    engine = FakeEngine(result=result)

    analysis = calculate_radiation_pattern(request, engine=engine)

    assert len(engine.requests) == 1
    assert engine.requests[0] is request
    assert isinstance(analysis, RadiationPatternAnalysis)
    assert analysis.result is result
    assert analysis.summary == summarize_radiation_pattern(result)


def test_calculate_propagates_engine_errors_unchanged():
    request = prepare_radiation_pattern_request(load_project(PATTERN_EXAMPLE))
    failure = RuntimeError("fallo del motor")

    with pytest.raises(RuntimeError) as error:
        calculate_radiation_pattern(request, engine=FakeEngine(error=failure))

    assert error.value is failure
    assert not isinstance(error.value, MissingRadiationPatternError)


def test_calculate_does_not_wrap_engine_value_errors():
    # Un ValueError del motor no se confunde con un proyecto sin patrón.
    request = prepare_radiation_pattern_request(load_project(PATTERN_EXAMPLE))
    failure = ValueError("modelo de tierra no admitido")

    with pytest.raises(ValueError) as error:
        calculate_radiation_pattern(request, engine=FakeEngine(error=failure))

    assert error.value is failure
    assert not isinstance(error.value, MissingRadiationPatternError)


# ---------------------------------------------------------------------------
# export_project_radiation_pattern_nec
# ---------------------------------------------------------------------------


def test_nec_export_matches_previous_cli_output(tmp_path):
    project = load_project(PATTERN_EXAMPLE)
    destination = tmp_path / "patron.nec"

    returned = export_project_radiation_pattern_nec(project, destination)

    assert returned == destination
    # Mismo texto que escribía la CLI: título y referencia del proyecto.
    assert destination.read_bytes() == radiation_pattern_request_to_nec(
        project.to_radiation_pattern_request(),
        title=project.metadata.name,
        reference_impedance=project.reference_impedance,
    ).encode("utf-8")
    assert destination.read_text(encoding="utf-8") == (
        "CM Dipolo de 20 metros - patrón de radiación\n"
        "CM Reference impedance: 50 ohm\n"
        "CM Informational only: NEC/4nec2 may require manually "
        "setting this reference impedance to display SWR.\n"
        "CE\n"
        "GW 1 101 -5.03 0 0 5.03 0 0 0.001\n"
        "GE 0\n"
        "EX 0 1 51 0 1 0\n"
        "FR 0 1 0 0 14.15 0\n"
        "RP 0 181 1 0000 0 0 1 0 0 0\n"
        "EN\n"
    )


def test_nec_export_uses_the_project_reference_impedance(tmp_path):
    project = dataclasses.replace(
        load_project(PATTERN_EXAMPLE),
        reference_impedance=75.0,
    )
    destination = tmp_path / "patron.nec"

    export_project_radiation_pattern_nec(project, str(destination))

    assert "CM Reference impedance: 75 ohm" in (
        destination.read_text(encoding="utf-8").splitlines()
    )


def test_nec_export_rejects_project_without_pattern_without_a_file(tmp_path):
    destination = tmp_path / "patron.nec"

    with pytest.raises(MissingRadiationPatternError):
        export_project_radiation_pattern_nec(
            load_project(NO_PATTERN_EXAMPLE), destination
        )

    assert not destination.exists()


def test_nec_export_propagates_write_errors(tmp_path):
    with pytest.raises(OSError):
        export_project_radiation_pattern_nec(
            load_project(PATTERN_EXAMPLE),
            tmp_path / "no-existe" / "patron.nec",
        )


# ---------------------------------------------------------------------------
# Arquitectura: dependencias del módulo
# ---------------------------------------------------------------------------


FORBIDDEN_MODULES = (
    "yaas.cli",
    "yaas.cli.main",
    "yaas.engines.pynec",
    "PyNEC",
    "numpy",
    "argparse",
    "gettext",
    "PySide6",
    "PyQt5",
    "PyQt6",
    "matplotlib",
    "pyqtgraph",
)


def test_module_does_not_load_cli_engine_numpy_or_gui():
    # En un proceso nuevo: importar el módulo y ejecutar el caso de uso
    # completo con un motor falso no carga la CLI, PyNEC, numpy,
    # argparse, gettext ni ninguna biblioteca gráfica.
    script = textwrap.dedent(f"""
        import sys
        from yaas.application.radiation_pattern import (
            calculate_radiation_pattern,
            export_project_radiation_pattern_nec,
            prepare_radiation_pattern_request,
        )
        from yaas.domain import RadiationPatternResult
        from yaas.projects import load_project

        class Engine:
            def simulate_radiation_pattern(self, request):
                return RadiationPatternResult(
                    frequency_mhz=14.15,
                    theta_angles_deg=(0.0,),
                    phi_angles_deg=(0.0,),
                    gain_db=((1.0,),),
                )

        project = load_project({PATTERN_EXAMPLE!r})
        calculate_radiation_pattern(
            prepare_radiation_pattern_request(project), engine=Engine()
        )
        loaded = [name for name in {FORBIDDEN_MODULES!r} if name in sys.modules]
        print(loaded)
        sys.exit(1 if loaded else 0)
    """)

    completed = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
