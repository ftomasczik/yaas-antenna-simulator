import dataclasses
import math

import pytest

from antsim.domain import (
    FreeSpaceEnvironment,
    PerfectGroundEnvironment,
    Point3D,
    SimulationRequest,
    SweepRequest,
    VoltageSource,
    Wire,
)


def create_valid_wire() -> Wire:
    return Wire(
        tag=1,
        start=Point3D(-5.0, 0.0, 0.0),
        end=Point3D(5.0, 0.0, 0.0),
        radius_m=0.001,
        segments=101,
    )


def test_wire_rejects_identical_endpoints():
    point = Point3D(0.0, 0.0, 0.0)

    with pytest.raises(ValueError):
        Wire(
            tag=1,
            start=point,
            end=point,
            radius_m=0.001,
            segments=11,
        )


def test_wire_rejects_invalid_radius():
    with pytest.raises(ValueError):
        Wire(
            tag=1,
            start=Point3D(0.0, 0.0, 0.0),
            end=Point3D(1.0, 0.0, 0.0),
            radius_m=0.0,
            segments=11,
        )


def test_request_requires_at_least_one_wire():
    with pytest.raises(ValueError):
        SimulationRequest(
            frequency_mhz=14.15,
            wires=(),
            source=VoltageSource(
                wire_tag=1,
                segment=1,
            ),
        )


def test_request_rejects_unknown_source_wire():
    with pytest.raises(ValueError):
        SimulationRequest(
            frequency_mhz=14.15,
            wires=(create_valid_wire(),),
            source=VoltageSource(
                wire_tag=99,
                segment=51,
            ),
        )


def test_request_rejects_unknown_source_segment():
    with pytest.raises(ValueError):
        SimulationRequest(
            frequency_mhz=14.15,
            wires=(create_valid_wire(),),
            source=VoltageSource(
                wire_tag=1,
                segment=200,
            ),
        )


def test_point_rejects_non_finite_coordinate():
    with pytest.raises(ValueError):
        Point3D(math.inf, 0.0, 0.0)


# ---------------------------------------------------------------------------
# Environment (fase 7A: modelo de dominio básico, sin validación de
# coordenadas Z todavía)
# ---------------------------------------------------------------------------


def create_valid_source() -> VoltageSource:
    return VoltageSource(wire_tag=1, segment=51)


def test_free_space_environment_can_be_constructed():
    assert FreeSpaceEnvironment() is not None


def test_perfect_ground_environment_can_be_constructed():
    assert PerfectGroundEnvironment() is not None


@pytest.mark.parametrize(
    "environment",
    [FreeSpaceEnvironment(), PerfectGroundEnvironment()],
)
def test_environments_are_immutable(environment):
    with pytest.raises(dataclasses.FrozenInstanceError):
        environment.kind = "changed"  # type: ignore[attr-defined]


def test_simulation_request_defaults_to_free_space():
    request = SimulationRequest(
        frequency_mhz=14.15,
        wires=(create_valid_wire(),),
        source=create_valid_source(),
    )

    assert request.environment == FreeSpaceEnvironment()


def test_sweep_request_defaults_to_free_space():
    request = SweepRequest(
        start_frequency_mhz=14.0,
        stop_frequency_mhz=14.3,
        points=3,
        wires=(create_valid_wire(),),
        source=create_valid_source(),
    )

    assert request.environment == FreeSpaceEnvironment()


def test_simulation_request_accepts_explicit_perfect_ground():
    request = SimulationRequest(
        frequency_mhz=14.15,
        wires=(create_valid_wire(),),
        source=create_valid_source(),
        environment=PerfectGroundEnvironment(),
    )

    assert request.environment == PerfectGroundEnvironment()


def test_sweep_request_accepts_explicit_perfect_ground():
    request = SweepRequest(
        start_frequency_mhz=14.0,
        stop_frequency_mhz=14.3,
        points=3,
        wires=(create_valid_wire(),),
        source=create_valid_source(),
        environment=PerfectGroundEnvironment(),
    )

    assert request.environment == PerfectGroundEnvironment()


def test_separately_created_requests_do_not_share_environment_state():
    free_space_request = SimulationRequest(
        frequency_mhz=14.15,
        wires=(create_valid_wire(),),
        source=create_valid_source(),
    )
    perfect_ground_request = SimulationRequest(
        frequency_mhz=14.15,
        wires=(create_valid_wire(),),
        source=create_valid_source(),
        environment=PerfectGroundEnvironment(),
    )

    # Cada solicitud conserva el entorno con el que se construyó; una
    # no queda afectada por la otra.
    assert free_space_request.environment == FreeSpaceEnvironment()
    assert (
        perfect_ground_request.environment == PerfectGroundEnvironment()
    )
    assert (
        free_space_request.environment
        != perfect_ground_request.environment
    )


def test_existing_constructors_keep_working_without_environment():
    # Los mismos constructores usados antes de la fase 7A, sin
    # mencionar environment, deben seguir funcionando sin cambios.
    simulation_request = SimulationRequest(
        frequency_mhz=14.15,
        wires=(create_valid_wire(),),
        source=create_valid_source(),
        reference_impedance=50.0,
    )
    sweep_request = SweepRequest(
        start_frequency_mhz=13.5,
        stop_frequency_mhz=15.5,
        points=81,
        wires=(create_valid_wire(),),
        source=create_valid_source(),
        reference_impedance=50.0,
    )

    assert simulation_request.environment == FreeSpaceEnvironment()
    assert sweep_request.environment == FreeSpaceEnvironment()
