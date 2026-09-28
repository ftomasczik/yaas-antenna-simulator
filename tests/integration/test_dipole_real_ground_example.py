"""Prueba de integración del ejemplo examples/dipole-20m-real-ground.yaas.

Carga el archivo real (no una construcción en memoria) y ejercita el
flujo completo: lectura del proyecto v3, conversión a solicitudes de
dominio, simulación puntual y barrido reales mediante PyNecEngine
(tierra real, Sommerfeld-Norton), y exportación NEC — igual que haría
un usuario real del ejemplo. Los valores esperados están validados
externamente en docs/validation/real-ground-dipole-4nec2.md.

El barrido de 81 puntos con tierra real crea un contexto NEC2++ nuevo
por frecuencia (ver PyNecEngine._simulate_sweep_per_frequency), así
que se calcula una única vez por módulo (fixture ``sweep_result``) y
se reutiliza entre pruebas, en vez de recalcularlo en cada una.
"""

import pytest

from yaas.domain import RealGroundEnvironment, RealGroundModel
from yaas.engines import PyNecEngine
from yaas.exporters import simulation_request_to_nec, sweep_request_to_nec
from yaas.projects import load_project

EXAMPLE_PATH = "examples/dipole-20m-real-ground.yaas"

EXPECTED_ENVIRONMENT = RealGroundEnvironment(
    relative_permittivity=13.0,
    conductivity_s_per_m=0.005,
)


@pytest.fixture(scope="module")
def project():
    return load_project(EXAMPLE_PATH)


@pytest.fixture(scope="module")
def engine():
    return PyNecEngine()


@pytest.fixture(scope="module")
def sweep_result(project, engine):
    return engine.simulate_sweep(project.to_sweep_request())


def test_example_has_schema_version_3(project):
    assert project.schema_version == 3


def test_example_environment_is_real_ground(project):
    assert isinstance(project.environment, RealGroundEnvironment)
    assert project.environment == EXPECTED_ENVIRONMENT


def test_example_environment_model_is_sommerfeld_norton(project):
    assert project.environment.model == RealGroundModel.SOMMERFELD_NORTON


def test_example_environment_permittivity_and_conductivity(project):
    assert project.environment.relative_permittivity == 13.0
    assert project.environment.conductivity_s_per_m == 0.005


def test_example_has_exactly_one_wire_with_the_expected_geometry(project):
    assert len(project.wires) == 1

    wire = project.wires[0]
    assert wire.tag == 1
    assert (wire.start.x, wire.start.y, wire.start.z) == (-5.03, 0.0, 10.0)
    assert (wire.end.x, wire.end.y, wire.end.z) == (5.03, 0.0, 10.0)
    assert wire.radius_m == 0.001


def test_example_wire_has_101_segments(project):
    assert project.wires[0].segments == 101


def test_example_source_is_on_wire_1_segment_51(project):
    assert project.source.wire_tag == 1
    assert project.source.segment == 51


def test_example_to_simulation_request_preserves_all_parameters(project):
    request = project.to_simulation_request()

    assert request.environment == EXPECTED_ENVIRONMENT
    assert request.frequency_mhz == 14.15
    assert request.reference_impedance == 50.0
    assert request.source.wire_tag == 1
    assert request.source.segment == 51
    assert request.source.voltage == complex(1.0, 0.0)
    assert len(request.wires) == 1


def test_example_simulate_produces_validated_impedance(project, engine):
    """Valor de referencia:
    docs/validation/real-ground-dipole-4nec2.md, seccion 7
    (PyNEC 66.57 - j41.36 ohm, ROE 2.13; 4nec2 66.6 - j41.4 ohm, ROE 2.13).
    """
    result = engine.simulate(project.to_simulation_request())

    assert 65.0 < result.impedance.real < 68.0
    assert -43.0 < result.impedance.imag < -39.0
    assert 2.0 < result.swr < 2.25


def test_example_to_sweep_request_preserves_real_ground(project):
    request = project.to_sweep_request()

    assert request.environment == EXPECTED_ENVIRONMENT


def test_example_sweep_returns_81_ordered_points(sweep_result):
    assert len(sweep_result.points) == 81

    frequencies = [point.frequency_mhz for point in sweep_result.points]
    assert frequencies == sorted(frequencies)
    assert frequencies[0] == pytest.approx(13.5)
    assert frequencies[-1] == pytest.approx(15.5)


@pytest.mark.parametrize(
    "frequency_mhz,expected_r,expected_x,expected_swr",
    [
        (13.5, 60.30, -106.76, 5.64),
        (14.5, 69.96, -6.05, 1.42),
        (15.5, 81.80, 97.18, 4.32),
    ],
)
def test_example_sweep_matches_validated_points(
    sweep_result, frequency_mhz, expected_r, expected_x, expected_swr
):
    """Valores de referencia:
    docs/validation/real-ground-dipole-4nec2.md, seccion 8.
    """
    point = next(
        candidate
        for candidate in sweep_result.points
        if candidate.frequency_mhz == pytest.approx(frequency_mhz)
    )

    assert point.impedance.real == pytest.approx(expected_r, abs=0.5)
    assert point.impedance.imag == pytest.approx(expected_x, abs=0.5)
    assert point.swr == pytest.approx(expected_swr, abs=0.05)


def test_example_simulation_nec_export_has_real_ground_cards(project):
    nec_text = simulation_request_to_nec(
        request=project.to_simulation_request(),
        title=project.metadata.name,
    )

    assert "GE 1\n" in nec_text
    assert "GN 2 0 0 0 13 0.005 0 0 0 0\n" in nec_text
    assert "EX 0 1 51 0 1 0\n" in nec_text
    assert "FR 0 1 0 0 14.15 0\n" in nec_text


def test_example_sweep_nec_export_has_real_ground_cards(project):
    nec_text = sweep_request_to_nec(
        request=project.to_sweep_request(),
        title=project.metadata.name,
    )

    assert nec_text.count("\nGN ") == 1
    assert "GN 2 0 0 0 13 0.005 0 0 0 0\n" in nec_text
    assert "FR 0 81 0 0 13.5 0.025\n" in nec_text


def test_example_gn_card_has_exact_structure(project):
    """Parsea la tarjeta GN campo por campo: token inicial, 10 campos,
    I1..I4 == 2,0,0,0, F1/F2 == permitividad/conductividad, F3..F6 == 0."""
    nec_text = simulation_request_to_nec(
        request=project.to_simulation_request(),
        title=project.metadata.name,
    )
    lines = nec_text.splitlines()
    gn_line = next(line for line in lines if line.startswith("GN "))
    fields = gn_line.split()

    assert fields[0] == "GN"
    assert len(fields) - 1 == 10
    assert fields[1:5] == ["2", "0", "0", "0"]
    assert fields[5] == "13"
    assert fields[6] == "0.005"
    assert fields[7:11] == ["0", "0", "0", "0"]
