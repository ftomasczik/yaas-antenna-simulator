import time

import pytest

from antsim.domain import (
    FreeSpaceEnvironment,
    PerfectGroundEnvironment,
    Point3D,
    RealGroundEnvironment,
    SimulationRequest,
    SweepRequest,
    VoltageSource,
    Wire,
)
# from antsim import PyNecEngine
from antsim.engines import PyNecEngine
from antsim.projects import (
    AntennaProject,
    ProjectMetadata,
    SweepSettings,
)

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


# ---------------------------------------------------------------------------
# Tierra real, Sommerfeld-Norton (fase 7B)
#
# Modelo de referencia y valores aproximados esperados, ya validados
# externamente con 4nec2: ver docs/research/nec-real-ground.md y
# docs/validation/real-ground-dipole-4nec2.md.
# ---------------------------------------------------------------------------


def create_real_ground_dipole() -> Wire:
    return Wire(
        tag=1,
        start=Point3D(-5.03, 0.0, 10.0),
        end=Point3D(5.03, 0.0, 10.0),
        radius_m=0.001,
        segments=101,
    )


def create_real_ground_environment(
    conductivity_s_per_m: float = 0.005,
) -> RealGroundEnvironment:
    return RealGroundEnvironment(
        relative_permittivity=13.0,
        conductivity_s_per_m=conductivity_s_per_m,
    )


def test_pynec_engine_simulates_dipole_over_real_ground():
    """Dipolo a 10 m sobre tierra real, Sommerfeld-Norton, a 14.15 MHz.

    Valor de referencia (docs/validation/real-ground-dipole-4nec2.md,
    sección 7): PyNEC 66.57 - j41.36 ohm, ROE 2.13 (50 ohm); 4nec2
    66.6 - j41.4 ohm, ROE 2.13. Rangos amplios a propósito para
    tolerar pequeñas diferencias entre plataformas.
    """
    dipole = create_real_ground_dipole()

    request = SimulationRequest(
        frequency_mhz=14.15,
        wires=(dipole,),
        source=VoltageSource(wire_tag=1, segment=51),
        reference_impedance=50.0,
        environment=create_real_ground_environment(),
    )

    engine = PyNecEngine()
    result = engine.simulate(request)

    assert result.frequency_mhz == 14.15
    assert 65.0 < result.impedance.real < 68.0
    assert -43.0 < result.impedance.imag < -39.0
    assert 2.0 < result.swr < 2.25


def test_pynec_engine_rejects_unsupported_real_ground_model():
    """Un RealGroundModel no reconocido falla explícitamente.

    El dominio hoy solo admite ``SOMMERFELD_NORTON``, así que este
    caso requiere construir el entorno sin pasar por
    ``RealGroundEnvironment.__post_init__`` (con ``object.__new__`` y
    asignación directa vía ``object.__setattr__``, dado que es una
    dataclass congelada), simulando qué pasaría si el dominio llegara
    a admitir en el futuro un segundo valor que el motor todavía no
    reconozca.
    """
    dipole = create_real_ground_dipole()

    environment = object.__new__(RealGroundEnvironment)
    object.__setattr__(environment, "relative_permittivity", 13.0)
    object.__setattr__(environment, "conductivity_s_per_m", 0.005)
    object.__setattr__(environment, "model", "coeficiente_de_reflexion")

    request = SimulationRequest(
        frequency_mhz=14.15,
        wires=(dipole,),
        source=VoltageSource(wire_tag=1, segment=51),
        environment=environment,
    )

    engine = PyNecEngine()
    with pytest.raises(ValueError, match="RealGroundModel"):
        engine.simulate(request)


def test_pynec_engine_sweeps_dipole_over_real_ground():
    """Barrido de 3 puntos (13.5/14.5/15.5 MHz) con tierra real.

    Valores de referencia
    (docs/validation/real-ground-dipole-4nec2.md, sección 8):

    - 13.5 MHz: 60.30 - j106.76 ohm, ROE 5.64 (PyNEC); 4nec2 60.2981
      - j106.78 ohm, ROE 5.64002.
    - 14.5 MHz: 69.96 - j6.05 ohm, ROE 1.42 (PyNEC); 4nec2 69.9534
      - j6.0735 ohm, ROE 1.4203.
    - 15.5 MHz: 81.80 + j97.18 ohm, ROE 4.33 (PyNEC); 4nec2 81.7964
      + j97.1602 ohm, ROE 4.32414.

    Además de los rangos numéricos, comprueba que cada punto del
    barrido coincide con una simulación independiente a la misma
    frecuencia dentro de una tolerancia pequeña (evidencia de que el
    barrido no depende de haber ejecutado antes ninguna otra
    frecuencia: cada punto usa su propio contexto NEC2++, sin estado
    compartido) y que los puntos se devuelven ordenados por
    frecuencia ascendente, tal como se solicitó.
    """
    dipole = create_real_ground_dipole()
    source = VoltageSource(wire_tag=1, segment=51)
    environment = create_real_ground_environment()
    engine = PyNecEngine()

    sweep_request = SweepRequest(
        start_frequency_mhz=13.5,
        stop_frequency_mhz=15.5,
        points=3,
        wires=(dipole,),
        source=source,
        reference_impedance=50.0,
        environment=environment,
    )

    started_at = time.perf_counter()
    sweep_result = engine.simulate_sweep(sweep_request)
    elapsed_s = time.perf_counter() - started_at
    # Observación (no es una aserción): tiempo aproximado del barrido
    # de 3 puntos con un contexto nuevo por frecuencia.
    print(
        "\ntest_pynec_engine_sweeps_dipole_over_real_ground: "
        f"barrido de 3 puntos en {elapsed_s * 1000:.1f} ms "
        "(observación, no es parte de la aserción)"
    )

    assert [point.frequency_mhz for point in sweep_result.points] == [
        13.5,
        14.5,
        15.5,
    ]

    expected_ranges = {
        13.5: {"r": (58.0, 62.0), "x": (-109.0, -104.0), "swr": (5.4, 5.9)},
        14.5: {"r": (68.0, 72.0), "x": (-8.5, -4.0), "swr": (1.3, 1.55)},
        15.5: {"r": (79.5, 84.0), "x": (94.5, 100.0), "swr": (4.1, 4.5)},
    }

    for point in sweep_result.points:
        ranges = expected_ranges[point.frequency_mhz]
        assert ranges["r"][0] < point.impedance.real < ranges["r"][1]
        assert ranges["x"][0] < point.impedance.imag < ranges["x"][1]
        assert ranges["swr"][0] < point.swr < ranges["swr"][1]

        independent_request = SimulationRequest(
            frequency_mhz=point.frequency_mhz,
            wires=(dipole,),
            source=source,
            reference_impedance=50.0,
            environment=environment,
        )
        independent_result = engine.simulate(independent_request)

        assert (
            abs(point.impedance.real - independent_result.impedance.real)
            < 0.1
        )
        assert (
            abs(point.impedance.imag - independent_result.impedance.imag)
            < 0.1
        )


def test_real_ground_sweep_creates_one_context_per_frequency(monkeypatch):
    """Espía sobre ``_create_context``: tierra real crea un contexto
    NEC2++ por cada punto del barrido, no uno solo reutilizado."""
    original_create_context = PyNecEngine._create_context
    call_count = 0

    def spy_create_context(self, wires, environment):
        nonlocal call_count
        call_count += 1
        return original_create_context(self, wires, environment)

    monkeypatch.setattr(
        PyNecEngine, "_create_context", spy_create_context
    )

    dipole = create_real_ground_dipole()
    request = SweepRequest(
        start_frequency_mhz=13.5,
        stop_frequency_mhz=15.5,
        points=3,
        wires=(dipole,),
        source=VoltageSource(wire_tag=1, segment=51),
        environment=create_real_ground_environment(),
    )

    engine = PyNecEngine()
    result = engine.simulate_sweep(request)

    assert call_count == 3
    assert len(result.points) == 3


@pytest.mark.parametrize(
    "environment",
    [FreeSpaceEnvironment(), PerfectGroundEnvironment()],
)
def test_non_real_ground_sweep_still_creates_a_single_context(
    monkeypatch, environment
):
    """Espía sobre ``_create_context``: espacio libre y tierra perfecta
    conservan la estrategia histórica de un único contexto para todo
    el barrido, sin reconstruirlo por punto."""
    original_create_context = PyNecEngine._create_context
    call_count = 0

    def spy_create_context(self, wires, env):
        nonlocal call_count
        call_count += 1
        return original_create_context(self, wires, env)

    monkeypatch.setattr(
        PyNecEngine, "_create_context", spy_create_context
    )

    monopole = Wire(
        tag=1,
        start=Point3D(0.0, 0.0, 0.0),
        end=Point3D(0.0, 0.0, 5.03),
        radius_m=0.001,
        segments=38,
    )
    request = SweepRequest(
        start_frequency_mhz=13.5,
        stop_frequency_mhz=15.5,
        points=3,
        wires=(monopole,),
        source=VoltageSource(wire_tag=1, segment=1),
        environment=environment,
    )

    engine = PyNecEngine()
    result = engine.simulate_sweep(request)

    assert call_count == 1
    assert len(result.points) == 3


def test_pynec_engine_simulates_perfect_ground_project_end_to_end():
    """AntennaProject con tierra perfecta llega correctamente a PyNecEngine.

    Ejercita el flujo completo: AntennaProject.environment ->
    to_simulation_request() -> PyNecEngine.simulate(), usando la
    misma geometría y el mismo valor esperado ya verificados en
    test_pynec_engine_simulates_monopole_over_perfect_ground.
    """
    monopole = Wire(
        tag=1,
        start=Point3D(0.0, 0.0, 0.0),
        end=Point3D(0.0, 0.0, 5.03),
        radius_m=0.001,
        segments=38,
    )

    project = AntennaProject(
        metadata=ProjectMetadata(name="Monopolo sobre tierra perfecta"),
        wires=(monopole,),
        source=VoltageSource(wire_tag=1, segment=1),
        frequency_mhz=14.15,
        reference_impedance=50.0,
        sweep=SweepSettings(
            start_frequency_mhz=13.5,
            stop_frequency_mhz=15.5,
            points=81,
        ),
        environment=PerfectGroundEnvironment(),
    )

    engine = PyNecEngine()
    result = engine.simulate(project.to_simulation_request())

    assert 32.0 < result.impedance.real < 36.0
    assert -18.0 < result.impedance.imag < -13.0