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
# from antsim import PyNecEngine
from antsim.engines import PyNecEngine

def test_pynec_engine_simulates_reference_dipole():
    dipole = Wire(
        tag=1,
        start=Point3D(-5.03, 0.0, 0.0),
        end=Point3D(5.03, 0.0, 0.0),
        radius_m=0.001,
        segments=101,
    )

    request = SimulationRequest(
        frequency_mhz=14.15,
        wires=(dipole,),
        source=VoltageSource(
            wire_tag=1,
            segment=51,
        ),
        reference_impedance=50.0,
    )

    engine = PyNecEngine()
    result = engine.simulate(request)

    assert result.frequency_mhz == 14.15

    # Límites suficientemente amplios para no depender de
    # pequeñas diferencias numéricas entre plataformas.
    assert 50.0 < result.impedance.real < 90.0
    assert -60.0 < result.impedance.imag < 0.0
    assert 1.0 < result.swr < 3.0

def test_pynec_engine_executes_frequency_sweep():
    dipole = Wire(
        tag=1,
        start=Point3D(-5.03, 0.0, 0.0),
        end=Point3D(5.03, 0.0, 0.0),
        radius_m=0.001,
        segments=101,
    )

    request = SweepRequest(
        start_frequency_mhz=13.0,
        stop_frequency_mhz=16.0,
        points=13,
        wires=(dipole,),
        source=VoltageSource(
            wire_tag=1,
            segment=51,
        ),
        reference_impedance=50.0,
    )

    engine = PyNecEngine()
    result = engine.simulate_sweep(request)

    assert len(result.points) == 13
    assert result.points[0].frequency_mhz == 13.0
    assert result.points[-1].frequency_mhz == 16.0

    assert all(
        point.swr >= 1.0
        for point in result.points
    )

    assert any(
        point.impedance.imag < 0
        for point in result.points
    )

    assert any(
        point.impedance.imag > 0
        for point in result.points
    )


# ---------------------------------------------------------------------------
# Tierra perfecta (fase 7A)
# ---------------------------------------------------------------------------


def test_pynec_engine_reference_dipole_matches_documented_value():
    """El dipolo histórico en espacio libre no cambia con esta fase.

    Valor documentado en docs/decisions/0002-use-nec2plusplus.md:
    67.43 - j31.25 ohm. El entorno es el predeterminado
    (FreeSpaceEnvironment), sin mencionarlo explícitamente.
    """
    dipole = Wire(
        tag=1,
        start=Point3D(-5.03, 0.0, 0.0),
        end=Point3D(5.03, 0.0, 0.0),
        radius_m=0.001,
        segments=101,
    )

    request = SimulationRequest(
        frequency_mhz=14.15,
        wires=(dipole,),
        source=VoltageSource(wire_tag=1, segment=51),
        reference_impedance=50.0,
    )

    engine = PyNecEngine()
    result = engine.simulate(request)

    assert 66.0 < result.impedance.real < 69.0
    assert -33.0 < result.impedance.imag < -29.0


def test_pynec_engine_simulates_monopole_over_perfect_ground():
    """Monopolo cuarto de onda sobre tierra perfecta.

    Geometría y valores esperados según
    docs/research/nec-ground-configuration.md (sección 3): resistencia
    aproximada 33.79 ohm, reactancia aproximada -15.62 ohm.
    """
    monopole = Wire(
        tag=1,
        start=Point3D(0.0, 0.0, 0.0),
        end=Point3D(0.0, 0.0, 5.03),
        radius_m=0.001,
        segments=38,
    )

    request = SimulationRequest(
        frequency_mhz=14.15,
        wires=(monopole,),
        source=VoltageSource(wire_tag=1, segment=1),
        reference_impedance=50.0,
        environment=PerfectGroundEnvironment(),
    )

    engine = PyNecEngine()
    result = engine.simulate(request)

    assert result.frequency_mhz == 14.15
    assert 32.0 < result.impedance.real < 36.0
    assert -18.0 < result.impedance.imag < -13.0


def test_pynec_engine_same_monopole_in_free_space_differs_clearly():
    """La misma geometría, sin tierra, no es un monopolo alimentado
    contra tierra: produce un resultado muy distinto (alimentación
    cerca del extremo de un conductor aislado en espacio libre).
    """
    monopole = Wire(
        tag=1,
        start=Point3D(0.0, 0.0, 0.0),
        end=Point3D(0.0, 0.0, 5.03),
        radius_m=0.001,
        segments=38,
    )

    request = SimulationRequest(
        frequency_mhz=14.15,
        wires=(monopole,),
        source=VoltageSource(wire_tag=1, segment=1),
        reference_impedance=50.0,
        environment=FreeSpaceEnvironment(),
    )

    engine = PyNecEngine()
    result = engine.simulate(request)

    # Con tierra perfecta la reactancia es de un orden de magnitud
    # pequeño (~-15.6 ohm); en espacio libre, para esta misma
    # geometría, es varios órdenes de magnitud mayor.
    assert abs(result.impedance.imag) > 1000.0


def test_pynec_engine_sweep_preserves_perfect_ground_across_all_points():
    """El barrido no vuelve a espacio libre en ningún punto.

    El primer punto del barrido (misma frecuencia que la simulación
    puntual) debe coincidir con `simulate()`, y todos los puntos deben
    quedar dentro de un rango consistente con tierra perfecta, no con
    espacio libre.
    """
    monopole = Wire(
        tag=1,
        start=Point3D(0.0, 0.0, 0.0),
        end=Point3D(0.0, 0.0, 5.03),
        radius_m=0.001,
        segments=38,
    )
    source = VoltageSource(wire_tag=1, segment=1)
    engine = PyNecEngine()

    single_request = SimulationRequest(
        frequency_mhz=14.15,
        wires=(monopole,),
        source=source,
        environment=PerfectGroundEnvironment(),
    )
    single_result = engine.simulate(single_request)

    sweep_request = SweepRequest(
        start_frequency_mhz=14.15,
        stop_frequency_mhz=14.35,
        points=3,
        wires=(monopole,),
        source=source,
        environment=PerfectGroundEnvironment(),
    )
    sweep_result = engine.simulate_sweep(sweep_request)

    first_point = sweep_result.points[0]
    assert first_point.frequency_mhz == 14.15
    assert (
        abs(first_point.impedance.real - single_result.impedance.real)
        < 0.5
    )
    assert (
        abs(first_point.impedance.imag - single_result.impedance.imag)
        < 0.5
    )

    for point in sweep_result.points:
        assert 25.0 < point.impedance.real < 45.0
        assert -25.0 < point.impedance.imag < 0.0


def test_invalid_ground_geometry_fails_before_reaching_pynec():
    """Un conductor que cruza el plano de tierra falla en el dominio.

    El ValueError se levanta al construir SimulationRequest, sin
    llegar a instanciar PyNecEngine ni a llamar a simulate().
    """
    crossing_wire = Wire(
        tag=7,
        start=Point3D(0.0, 0.0, -2.0),
        end=Point3D(0.0, 0.0, 3.0),
        radius_m=0.001,
        segments=21,
    )

    with pytest.raises(ValueError, match="conductor 7"):
        SimulationRequest(
            frequency_mhz=14.15,
            wires=(crossing_wire,),
            source=VoltageSource(wire_tag=7, segment=11),
            environment=PerfectGroundEnvironment(),
        )


def test_pynec_engine_rejects_unknown_environment_type():
    """PyNecEngine no asume espacio libre ante un entorno desconocido."""

    class _UnknownEnvironment:
        pass

    monopole = Wire(
        tag=1,
        start=Point3D(0.0, 0.0, 0.0),
        end=Point3D(0.0, 0.0, 5.03),
        radius_m=0.001,
        segments=38,
    )

    request = SimulationRequest(
        frequency_mhz=14.15,
        wires=(monopole,),
        source=VoltageSource(wire_tag=1, segment=1),
        environment=_UnknownEnvironment(),
    )

    engine = PyNecEngine()
    with pytest.raises(ValueError):
        engine.simulate(request)