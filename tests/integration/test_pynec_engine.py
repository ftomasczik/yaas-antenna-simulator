from antsim.domain import (
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