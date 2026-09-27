"""Prueba de integración del ejemplo examples/monopole-20m-perfect-ground.antsim.

Carga el archivo real (no una construcción en memoria) y ejercita el
flujo completo: lectura del proyecto v2, conversión a solicitudes de
dominio, simulación y barrido reales mediante PyNecEngine, y
exportación NEC — igual que haría un usuario real del ejemplo.
"""

import pytest

from antsim.domain import PerfectGroundEnvironment
from antsim.engines import PyNecEngine
from antsim.exporters import simulation_request_to_nec, sweep_request_to_nec
from antsim.projects import load_project

EXAMPLE_PATH = "examples/monopole-20m-perfect-ground.antsim"


def test_example_has_schema_version_2():
    project = load_project(EXAMPLE_PATH)

    assert project.schema_version == 2


def test_example_environment_is_perfect_ground():
    project = load_project(EXAMPLE_PATH)

    assert project.environment == PerfectGroundEnvironment()


def test_example_has_exactly_one_wire_with_the_expected_geometry():
    project = load_project(EXAMPLE_PATH)

    assert len(project.wires) == 1

    wire = project.wires[0]
    assert wire.tag == 1
    assert (wire.start.x, wire.start.y, wire.start.z) == (0.0, 0.0, 0.0)
    assert (wire.end.x, wire.end.y, wire.end.z) == (0.0, 0.0, 5.03)
    assert wire.radius_m == 0.001


def test_example_wire_has_38_segments():
    project = load_project(EXAMPLE_PATH)

    assert project.wires[0].segments == 38


def test_example_source_is_on_wire_1_segment_1():
    project = load_project(EXAMPLE_PATH)

    assert project.source.wire_tag == 1
    assert project.source.segment == 1


def test_example_to_simulation_request_preserves_perfect_ground():
    project = load_project(EXAMPLE_PATH)

    request = project.to_simulation_request()

    assert request.environment == PerfectGroundEnvironment()


def test_example_simulate_produces_expected_impedance():
    project = load_project(EXAMPLE_PATH)
    engine = PyNecEngine()

    result = engine.simulate(project.to_simulation_request())

    assert 32.0 < result.impedance.real < 36.0
    assert -18.0 < result.impedance.imag < -13.0


def test_example_to_sweep_request_preserves_perfect_ground():
    project = load_project(EXAMPLE_PATH)

    request = project.to_sweep_request()

    assert request.environment == PerfectGroundEnvironment()


def test_example_sweep_runs_and_returns_81_points():
    project = load_project(EXAMPLE_PATH)
    engine = PyNecEngine()

    result = engine.simulate_sweep(project.to_sweep_request())

    assert len(result.points) == 81
    assert result.points[0].frequency_mhz == pytest.approx(13.5)
    assert result.points[-1].frequency_mhz == pytest.approx(15.5)


def test_example_sweep_point_nearest_main_frequency_matches_simulate():
    """El punto del barrido más cercano a la frecuencia principal debe
    ser coherente con simulate(), sin exigir que el barrido incluya
    exactamente ese punto (búsqueda por cercanía, no por índice fijo)."""
    project = load_project(EXAMPLE_PATH)
    engine = PyNecEngine()

    single_result = engine.simulate(project.to_simulation_request())
    sweep_result = engine.simulate_sweep(project.to_sweep_request())

    closest_point = min(
        sweep_result.points,
        key=lambda point: abs(
            point.frequency_mhz - project.frequency_mhz
        ),
    )

    assert abs(
        closest_point.frequency_mhz - project.frequency_mhz
    ) < 0.05
    assert abs(
        closest_point.impedance.real - single_result.impedance.real
    ) < 0.5
    assert abs(
        closest_point.impedance.imag - single_result.impedance.imag
    ) < 0.5


def test_example_simulation_nec_export_has_perfect_ground_cards():
    project = load_project(EXAMPLE_PATH)

    nec_text = simulation_request_to_nec(
        request=project.to_simulation_request(),
        title=project.metadata.name,
    )

    assert "GE 1\n" in nec_text
    assert "GN 1 0 0 0 0 0 0 0\n" in nec_text
    assert "EX 0 1 1 0 1 0\n" in nec_text
    assert "FR 0 1 0 0 14.15 0\n" in nec_text


def test_example_sweep_nec_export_has_perfect_ground_cards():
    project = load_project(EXAMPLE_PATH)

    nec_text = sweep_request_to_nec(
        request=project.to_sweep_request(),
        title=project.metadata.name,
    )

    assert "GE 1\n" in nec_text
    assert "GN 1 0 0 0 0 0 0 0\n" in nec_text
