import dataclasses
import math

import pytest

from antsim.domain import (
    FreeSpaceEnvironment,
    PerfectGroundEnvironment,
    Point3D,
    RealGroundEnvironment,
    RealGroundModel,
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
    wire = create_wire_with_z(0.0, 5.0)

    request = SimulationRequest(
        frequency_mhz=14.15,
        wires=(wire,),
        source=create_source_for(wire),
        environment=PerfectGroundEnvironment(),
    )

    assert request.environment == PerfectGroundEnvironment()


def test_sweep_request_accepts_explicit_perfect_ground():
    wire = create_wire_with_z(0.0, 5.0)

    request = SweepRequest(
        start_frequency_mhz=14.0,
        stop_frequency_mhz=14.3,
        points=3,
        wires=(wire,),
        source=create_source_for(wire),
        environment=PerfectGroundEnvironment(),
    )

    assert request.environment == PerfectGroundEnvironment()


def test_separately_created_requests_do_not_share_environment_state():
    ground_wire = create_wire_with_z(0.0, 5.0)

    free_space_request = SimulationRequest(
        frequency_mhz=14.15,
        wires=(create_valid_wire(),),
        source=create_valid_source(),
    )
    perfect_ground_request = SimulationRequest(
        frequency_mhz=14.15,
        wires=(ground_wire,),
        source=create_source_for(ground_wire),
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


# ---------------------------------------------------------------------------
# Validación de conductores contra el plano de tierra (z=0)
# ---------------------------------------------------------------------------


def create_wire_with_z(z1: float, z2: float, tag: int = 1) -> Wire:
    return Wire(
        tag=tag,
        start=Point3D(0.0, 0.0, z1),
        end=Point3D(0.0, 0.0, z2),
        radius_m=0.001,
        segments=11,
    )


def create_horizontal_wire_at_z(z: float, tag: int = 1) -> Wire:
    """Conductor horizontal (no vertical) a una altura z constante.

    Distinto de ``create_wire_with_z``: mantiene los extremos
    distintos (en x) incluso cuando ``z`` es 0, para poder probar un
    conductor contenido en el plano de tierra sin violar la
    invariante preexistente de ``Wire`` (extremos distintos).
    """
    return Wire(
        tag=tag,
        start=Point3D(-5.0, 0.0, z),
        end=Point3D(5.0, 0.0, z),
        radius_m=0.001,
        segments=11,
    )


def create_source_for(wire: Wire) -> VoltageSource:
    return VoltageSource(wire_tag=wire.tag, segment=1)


def test_perfect_ground_accepts_wire_from_ground_to_above():
    wire = create_wire_with_z(0.0, 5.0)

    request = SimulationRequest(
        frequency_mhz=14.15,
        wires=(wire,),
        source=create_source_for(wire),
        environment=PerfectGroundEnvironment(),
    )

    assert request.environment == PerfectGroundEnvironment()


def test_perfect_ground_accepts_wire_floating_above_ground():
    wire = create_wire_with_z(2.0, 5.0)

    request = SimulationRequest(
        frequency_mhz=14.15,
        wires=(wire,),
        source=create_source_for(wire),
        environment=PerfectGroundEnvironment(),
    )

    assert request.environment == PerfectGroundEnvironment()


def test_perfect_ground_rejects_negative_first_endpoint():
    wire = create_wire_with_z(-1.0, 5.0)

    with pytest.raises(ValueError, match="coordenada z negativa"):
        SimulationRequest(
            frequency_mhz=14.15,
            wires=(wire,),
            source=create_source_for(wire),
            environment=PerfectGroundEnvironment(),
        )


def test_perfect_ground_rejects_negative_second_endpoint():
    wire = create_wire_with_z(5.0, -1.0)

    with pytest.raises(ValueError, match="coordenada z negativa"):
        SimulationRequest(
            frequency_mhz=14.15,
            wires=(wire,),
            source=create_source_for(wire),
            environment=PerfectGroundEnvironment(),
        )


def test_perfect_ground_rejects_wire_crossing_the_plane():
    wire = create_wire_with_z(-2.0, 3.0)

    with pytest.raises(ValueError, match="coordenada z negativa"):
        SimulationRequest(
            frequency_mhz=14.15,
            wires=(wire,),
            source=create_source_for(wire),
            environment=PerfectGroundEnvironment(),
        )


def test_perfect_ground_rejects_wire_entirely_below_ground():
    wire = create_wire_with_z(-5.0, -1.0)

    with pytest.raises(ValueError, match="coordenada z negativa"):
        SimulationRequest(
            frequency_mhz=14.15,
            wires=(wire,),
            source=create_source_for(wire),
            environment=PerfectGroundEnvironment(),
        )


def test_perfect_ground_rejects_wire_contained_in_ground_plane():
    wire = create_horizontal_wire_at_z(0.0)

    with pytest.raises(
        ValueError, match="completamente contenido en el plano de tierra"
    ):
        SimulationRequest(
            frequency_mhz=14.15,
            wires=(wire,),
            source=create_source_for(wire),
            environment=PerfectGroundEnvironment(),
        )


def test_perfect_ground_error_includes_the_offending_wire_tag():
    good_wire = create_wire_with_z(0.0, 5.0, tag=1)
    bad_wire = create_wire_with_z(-1.0, 5.0, tag=2)

    with pytest.raises(ValueError, match=r"conductor 2\b"):
        SimulationRequest(
            frequency_mhz=14.15,
            wires=(good_wire, bad_wire),
            source=create_source_for(good_wire),
            environment=PerfectGroundEnvironment(),
        )


def test_free_space_still_allows_negative_z_coordinates():
    wire = create_wire_with_z(-5.0, -1.0)

    request = SimulationRequest(
        frequency_mhz=14.15,
        wires=(wire,),
        source=create_source_for(wire),
    )

    assert request.environment == FreeSpaceEnvironment()


def test_free_space_still_allows_wire_contained_in_ground_plane():
    wire = create_horizontal_wire_at_z(0.0)

    request = SimulationRequest(
        frequency_mhz=14.15,
        wires=(wire,),
        source=create_source_for(wire),
    )

    assert request.environment == FreeSpaceEnvironment()


def test_sweep_request_applies_the_same_ground_rules():
    wire = create_wire_with_z(-2.0, 3.0)

    with pytest.raises(ValueError, match="coordenada z negativa"):
        SweepRequest(
            start_frequency_mhz=14.0,
            stop_frequency_mhz=14.3,
            points=3,
            wires=(wire,),
            source=create_source_for(wire),
            environment=PerfectGroundEnvironment(),
        )


def test_ground_validation_error_happens_before_any_engine_is_involved():
    # Este módulo de pruebas no importa PyNEC ni ningún motor: el
    # ValueError se levanta al construir el objeto de dominio, nunca
    # al simular. Si esta prueba pasa sin ninguna dependencia de
    # motor, la validación ocurre exclusivamente en el dominio.
    wire = create_wire_with_z(-1.0, 5.0)

    with pytest.raises(ValueError):
        SimulationRequest(
            frequency_mhz=14.15,
            wires=(wire,),
            source=create_source_for(wire),
            environment=PerfectGroundEnvironment(),
        )


# ---------------------------------------------------------------------------
# RealGroundEnvironment (Sommerfeld-Norton, fase 7B: solo dominio)
#
# PyNecEngine todavía no soporta este entorno (ver
# tests/integration/test_pynec_engine.py,
# test_pynec_engine_rejects_real_ground_environment_until_supported);
# aquí solo se prueba el modelo de dominio.
# ---------------------------------------------------------------------------


def build_real_ground(**overrides) -> RealGroundEnvironment:
    values = {
        "relative_permittivity": 13.0,
        "conductivity_s_per_m": 0.005,
    }
    values.update(overrides)
    return RealGroundEnvironment(**values)


def test_real_ground_environment_can_be_constructed():
    environment = build_real_ground()

    assert environment.relative_permittivity == 13.0
    assert environment.conductivity_s_per_m == 0.005


def test_real_ground_environment_defaults_to_sommerfeld_norton():
    environment = build_real_ground()

    assert environment.model is RealGroundModel.SOMMERFELD_NORTON


def test_real_ground_environment_is_immutable():
    environment = build_real_ground()

    with pytest.raises(dataclasses.FrozenInstanceError):
        environment.relative_permittivity = 20.0  # type: ignore[misc]


def test_real_ground_environment_accepts_lossless_dielectric():
    # sigma=0.0 representa un dieléctrico homogéneo sin pérdidas, no
    # "sin tierra": se admite explícitamente, a diferencia de
    # FreeSpaceEnvironment.
    environment = build_real_ground(conductivity_s_per_m=0.0)

    assert environment.conductivity_s_per_m == 0.0


@pytest.mark.parametrize(
    "overrides,match",
    [
        ({"relative_permittivity": 0.0}, "permitividad"),
        ({"relative_permittivity": -1.0}, "permitividad"),
        ({"relative_permittivity": math.nan}, "permitividad"),
        ({"relative_permittivity": math.inf}, "permitividad"),
        ({"relative_permittivity": -math.inf}, "permitividad"),
        ({"conductivity_s_per_m": -0.005}, "conductividad"),
        ({"conductivity_s_per_m": math.nan}, "conductividad"),
        ({"conductivity_s_per_m": math.inf}, "conductividad"),
        ({"conductivity_s_per_m": -math.inf}, "conductividad"),
        ({"model": "sommerfeld_norton"}, "RealGroundModel"),
        ({"model": 2}, "RealGroundModel"),
        ({"model": PerfectGroundEnvironment()}, "RealGroundModel"),
    ],
)
def test_real_ground_environment_rejects_invalid_fields(overrides, match):
    with pytest.raises(ValueError, match=match):
        build_real_ground(**overrides)


def test_real_ground_accepts_wire_from_ground_to_above():
    wire = create_wire_with_z(0.0, 5.0)

    request = SimulationRequest(
        frequency_mhz=14.15,
        wires=(wire,),
        source=create_source_for(wire),
        environment=build_real_ground(),
    )

    assert request.environment == build_real_ground()


def test_real_ground_accepts_wire_floating_above_ground():
    wire = create_wire_with_z(2.0, 5.0)

    request = SimulationRequest(
        frequency_mhz=14.15,
        wires=(wire,),
        source=create_source_for(wire),
        environment=build_real_ground(),
    )

    assert request.environment == build_real_ground()


def test_real_ground_rejects_negative_coordinate():
    wire = create_wire_with_z(-1.0, 5.0)

    with pytest.raises(ValueError, match="coordenada z negativa"):
        SimulationRequest(
            frequency_mhz=14.15,
            wires=(wire,),
            source=create_source_for(wire),
            environment=build_real_ground(),
        )


def test_real_ground_rejects_wire_contained_in_ground_plane():
    wire = create_horizontal_wire_at_z(0.0)

    with pytest.raises(
        ValueError, match="completamente contenido en el plano de tierra"
    ):
        SimulationRequest(
            frequency_mhz=14.15,
            wires=(wire,),
            source=create_source_for(wire),
            environment=build_real_ground(),
        )


def test_real_ground_sweep_request_applies_the_same_ground_rules():
    wire = create_wire_with_z(-2.0, 3.0)

    with pytest.raises(ValueError, match="coordenada z negativa"):
        SweepRequest(
            start_frequency_mhz=14.0,
            stop_frequency_mhz=14.3,
            points=3,
            wires=(wire,),
            source=create_source_for(wire),
            environment=build_real_ground(),
        )


def test_simulation_and_sweep_request_behave_identically_for_real_ground():
    valid_wire = create_wire_with_z(0.0, 5.0)
    invalid_wire = create_wire_with_z(-1.0, 5.0)

    # Ambas construyen correctamente con el mismo conductor válido...
    SimulationRequest(
        frequency_mhz=14.15,
        wires=(valid_wire,),
        source=create_source_for(valid_wire),
        environment=build_real_ground(),
    )
    SweepRequest(
        start_frequency_mhz=14.0,
        stop_frequency_mhz=14.3,
        points=3,
        wires=(valid_wire,),
        source=create_source_for(valid_wire),
        environment=build_real_ground(),
    )

    # ...y ambas rechazan el mismo conductor inválido, con el mismo
    # mensaje.
    with pytest.raises(ValueError, match="coordenada z negativa"):
        SimulationRequest(
            frequency_mhz=14.15,
            wires=(invalid_wire,),
            source=create_source_for(invalid_wire),
            environment=build_real_ground(),
        )

    with pytest.raises(ValueError, match="coordenada z negativa"):
        SweepRequest(
            start_frequency_mhz=14.0,
            stop_frequency_mhz=14.3,
            points=3,
            wires=(invalid_wire,),
            source=create_source_for(invalid_wire),
            environment=build_real_ground(),
        )


def test_simulation_request_preserves_real_ground_instance():
    wire = create_wire_with_z(0.0, 5.0)
    environment = build_real_ground(conductivity_s_per_m=0.01)

    request = SimulationRequest(
        frequency_mhz=14.15,
        wires=(wire,),
        source=create_source_for(wire),
        environment=environment,
    )

    assert request.environment is environment


def test_sweep_request_preserves_real_ground_instance():
    wire = create_wire_with_z(0.0, 5.0)
    environment = build_real_ground(conductivity_s_per_m=0.01)

    request = SweepRequest(
        start_frequency_mhz=14.0,
        stop_frequency_mhz=14.3,
        points=3,
        wires=(wire,),
        source=create_source_for(wire),
        environment=environment,
    )

    assert request.environment is environment
