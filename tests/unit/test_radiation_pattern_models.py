import dataclasses
import math
from decimal import Decimal
from fractions import Fraction

import pytest

from yaas.domain import (
    AngularSweep,
    FreeSpaceEnvironment,
    PerfectGroundEnvironment,
    Point3D,
    RadiationPatternRequest,
    RadiationPatternResult,
    RadiationPatternSample,
    RealGroundEnvironment,
    SimulationRequest,
    VoltageSource,
    Wire,
)


def create_free_space_wire() -> Wire:
    return Wire(
        tag=1,
        start=Point3D(-5.03, 0.0, 0.0),
        end=Point3D(5.03, 0.0, 0.0),
        radius_m=0.001,
        segments=101,
    )


def create_wire_with_z(z1: float, z2: float, tag: int = 1) -> Wire:
    return Wire(
        tag=tag,
        start=Point3D(0.0, 0.0, z1),
        end=Point3D(0.0, 0.0, z2),
        radius_m=0.001,
        segments=11,
    )


def create_horizontal_wire_at_z(z: float, tag: int = 1) -> Wire:
    return Wire(
        tag=tag,
        start=Point3D(-5.0, 0.0, z),
        end=Point3D(5.0, 0.0, z),
        radius_m=0.001,
        segments=11,
    )


def create_source_for(wire: Wire) -> VoltageSource:
    return VoltageSource(wire_tag=wire.tag, segment=1)


def build_real_ground() -> RealGroundEnvironment:
    return RealGroundEnvironment(
        relative_permittivity=13.0,
        conductivity_s_per_m=0.005,
    )


def full_azimuth() -> AngularSweep:
    return AngularSweep(start_deg=0.0, count=361, step_deg=1.0)


def build_request(**overrides) -> RadiationPatternRequest:
    wire = create_free_space_wire()
    values = {
        "wires": (wire,),
        "environment": FreeSpaceEnvironment(),
        "source": VoltageSource(wire_tag=1, segment=51),
        "frequency_mhz": 14.15,
        "theta": AngularSweep(start_deg=0.0, count=181, step_deg=1.0),
        "phi": AngularSweep(start_deg=0.0, count=1, step_deg=0.0),
    }
    values.update(overrides)
    return RadiationPatternRequest(**values)


def build_ground_request(environment, **overrides):
    wire = create_wire_with_z(0.0, 5.03)
    values = {
        "wires": (wire,),
        "environment": environment,
        "source": create_source_for(wire),
    }
    values.update(overrides)
    return build_request(**values)


def build_result(**overrides) -> RadiationPatternResult:
    values = {
        "frequency_mhz": 14.15,
        "theta_angles_deg": (0.0, 90.0),
        "phi_angles_deg": (0.0, 90.0, 180.0),
        "gain_db": (
            (1.0, 2.0, 3.0),
            (4.0, None, -6.0),
        ),
    }
    values.update(overrides)
    return RadiationPatternResult(**values)


class FakeAngularSweep:
    """Tiene los atributos de un AngularSweep, pero no lo es."""

    start_deg = 0.0
    count = 1
    step_deg = 0.0
    stop_deg = 0.0


class FakeWire:
    """Objeto que no es un Wire."""

    tag = 1
    segments = 101


@dataclasses.dataclass(frozen=True)
class UnknownEnvironment:
    """Entorno que el dominio no conoce."""


# ---------------------------------------------------------------------------
# AngularSweep
# ---------------------------------------------------------------------------


def test_angular_sweep_single_point_accepts_zero_step():
    sweep = AngularSweep(start_deg=90.0, count=1, step_deg=0.0)

    assert sweep.stop_deg == 90.0
    assert sweep.angles_deg == (90.0,)


def test_angular_sweep_multiple_points():
    sweep = AngularSweep(start_deg=0.0, count=5, step_deg=22.5)

    assert sweep.stop_deg == 90.0
    # Igualdad con una tuple: una lista no sería igual.
    assert sweep.angles_deg == (0.0, 22.5, 45.0, 67.5, 90.0)


def test_angular_sweep_last_angle_matches_stop():
    sweep = full_azimuth()

    assert len(sweep.angles_deg) == 361
    assert sweep.angles_deg[0] == 0.0
    assert sweep.angles_deg[-1] == sweep.stop_deg == 360.0


def test_angular_sweep_does_not_wrap_angles():
    # 360 no se envuelve a 0, y un ángulo fuera de 0..360 tampoco se
    # normaliza aquí (los rangos se validan en RadiationPatternRequest).
    sweep = AngularSweep(start_deg=350.0, count=3, step_deg=10.0)

    assert sweep.angles_deg == (350.0, 360.0, 370.0)


def test_angular_sweep_is_immutable():
    sweep = AngularSweep(start_deg=0.0, count=3, step_deg=1.0)

    with pytest.raises(dataclasses.FrozenInstanceError):
        sweep.count = 4  # type: ignore[misc]


@pytest.mark.parametrize("count", [0, -1, -3])
def test_non_positive_count_is_rejected_before_any_engine_call(count):
    # Razón de seguridad: un conteo negativo pasado a rp_card() de
    # PyNEC provoca un segmentation fault del proceso
    # (docs/research/nec-radiation-patterns.md, §1.6). Este módulo no
    # importa PyNEC: el conteo inválido se rechaza al construir el
    # objeto de dominio, antes de que un adaptador pueda usarlo.
    with pytest.raises(ValueError, match="entero positivo"):
        AngularSweep(start_deg=0.0, count=count, step_deg=10.0)


@pytest.mark.parametrize(
    "count",
    [3.0, 1.5, True, False, "3", Decimal("3"), Fraction(3)],
)
def test_angular_sweep_rejects_non_int_count(count):
    with pytest.raises(ValueError, match="entero positivo"):
        AngularSweep(start_deg=0.0, count=count, step_deg=1.0)


@pytest.mark.parametrize(
    "value",
    [
        math.nan,
        math.inf,
        -math.inf,
        True,
        False,
        "1.0",
        None,
        Decimal("1.0"),
        Fraction(1, 2),
    ],
)
def test_real_number_helper_rejects_non_finite_and_non_float(value):
    # Todos los campos numéricos nuevos comparten el mismo helper
    # (estrictamente int | float finito, nunca bool ni un tipo
    # convertible); aquí se ejercita su contrato completo una vez. El
    # resto de las pruebas solo verifica que cada campo lo use.
    with pytest.raises(ValueError, match="número finito"):
        AngularSweep(start_deg=value, count=3, step_deg=1.0)


@pytest.mark.parametrize("value", [math.nan, True])
def test_angular_sweep_validates_step_as_real_number(value):
    with pytest.raises(ValueError, match="paso angular"):
        AngularSweep(start_deg=0.0, count=3, step_deg=value)


def test_angular_sweep_rejects_negative_step():
    with pytest.raises(ValueError, match="no puede ser negativo"):
        AngularSweep(start_deg=90.0, count=3, step_deg=-10.0)


def test_angular_sweep_rejects_zero_step_with_several_points():
    with pytest.raises(ValueError, match="debe ser positivo"):
        AngularSweep(start_deg=0.0, count=2, step_deg=0.0)


def test_angular_sweep_rejects_non_finite_stop():
    with pytest.raises(ValueError, match="ángulo final"):
        AngularSweep(start_deg=1e308, count=3, step_deg=1e308)


# ---------------------------------------------------------------------------
# RadiationPatternRequest: dominio angular
# ---------------------------------------------------------------------------


def test_free_space_accepts_full_theta_range():
    request = build_request(
        theta=AngularSweep(start_deg=0.0, count=181, step_deg=1.0),
    )

    assert request.theta.stop_deg == 180.0


@pytest.mark.parametrize(
    "environment",
    [PerfectGroundEnvironment(), build_real_ground()],
    ids=["perfect_ground", "real_ground"],
)
def test_ground_accepts_theta_up_to_horizon(environment):
    request = build_ground_request(
        environment,
        theta=AngularSweep(start_deg=0.0, count=91, step_deg=1.0),
    )

    assert request.theta.stop_deg == 90.0


@pytest.mark.parametrize(
    "environment",
    [PerfectGroundEnvironment(), build_real_ground()],
    ids=["perfect_ground", "real_ground"],
)
@pytest.mark.parametrize(
    "theta",
    [
        AngularSweep(start_deg=0.0, count=92, step_deg=1.0),
        AngularSweep(start_deg=90.5, count=1, step_deg=0.0),
    ],
    ids=["sweep_ends_at_91", "single_point_at_90_5"],
)
def test_ground_rejects_theta_below_horizon(environment, theta):
    with pytest.raises(ValueError, match="plano de tierra.*90 grados"):
        build_ground_request(environment, theta=theta)


def test_free_space_rejects_theta_above_180():
    with pytest.raises(ValueError, match="180 grados"):
        build_request(
            theta=AngularSweep(start_deg=0.0, count=182, step_deg=1.0),
        )


def test_request_rejects_negative_theta_start():
    with pytest.raises(ValueError, match="theta inicial"):
        build_request(
            theta=AngularSweep(start_deg=-1.0, count=3, step_deg=1.0),
        )


def test_request_rejects_negative_phi_start():
    with pytest.raises(ValueError, match="phi inicial"):
        build_request(
            phi=AngularSweep(start_deg=-1.0, count=3, step_deg=1.0),
        )


def test_request_rejects_phi_stop_above_360():
    with pytest.raises(ValueError, match="360 grados"):
        build_request(
            phi=AngularSweep(start_deg=0.0, count=362, step_deg=1.0),
        )


def test_request_accepts_phi_from_0_to_360_inclusive():
    request = build_request(
        theta=AngularSweep(start_deg=90.0, count=1, step_deg=0.0),
        phi=full_azimuth(),
    )

    assert request.phi.angles_deg[0] == 0.0
    assert request.phi.angles_deg[-1] == 360.0


def test_request_accepts_single_phi_at_360():
    request = build_request(
        phi=AngularSweep(start_deg=360.0, count=1, step_deg=0.0),
    )

    assert request.phi.stop_deg == 360.0


# ---------------------------------------------------------------------------
# RadiationPatternRequest: tipos de los campos anidados
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("field", ["theta", "phi"])
@pytest.mark.parametrize(
    "value",
    [None, "invalid", (0.0, 1.0, 2.0), FakeAngularSweep()],
    ids=["none", "string", "tuple", "duck_typed"],
)
def test_request_requires_angular_sweep_axes(field, value):
    # Un objeto con start_deg/stop_deg que no es AngularSweep también se
    # rechaza: el contrato es isinstance, no duck typing.
    with pytest.raises(ValueError, match=f"{field} debe ser un AngularSweep"):
        build_request(**{field: value})


@pytest.mark.parametrize(
    "source",
    [None, "1:51", (1, 51)],
    ids=["none", "string", "tuple"],
)
def test_request_rejects_source_that_is_not_voltage_source(source):
    # SimulationRequest no comprueba el tipo y fallaría con un
    # AttributeError incidental; RadiationPatternRequest da un
    # ValueError claro.
    with pytest.raises(ValueError, match="VoltageSource"):
        build_request(source=source)


@pytest.mark.parametrize(
    "wires",
    [(None,), ("wire",), (create_free_space_wire(), FakeWire())],
    ids=["none", "string", "mixed"],
)
def test_request_rejects_wires_that_are_not_wire(wires):
    with pytest.raises(ValueError, match="deben ser Wire"):
        build_request(wires=wires)


def test_request_keeps_the_historical_wires_contract():
    # Limitación documentada: igual que SimulationRequest, no se exige
    # tuple para wires, así que una lista se acepta y se conserva tal
    # cual (sigue siendo mutable). Resolverlo requiere una decisión
    # general del proyecto, no solo de este modelo.
    wires = [create_free_space_wire()]
    source = VoltageSource(wire_tag=1, segment=51)

    SimulationRequest(frequency_mhz=14.15, wires=wires, source=source)
    request = build_request(wires=wires, source=source)

    assert request.wires is wires


@pytest.mark.parametrize(
    "environment",
    [UnknownEnvironment(), None, "free_space"],
    ids=["unknown_dataclass", "none", "string"],
)
def test_request_rejects_unknown_environment_type(environment):
    with pytest.raises(ValueError, match="entorno desconocido"):
        build_request(environment=environment)


@pytest.mark.parametrize(
    "environment",
    [FreeSpaceEnvironment(), PerfectGroundEnvironment(), build_real_ground()],
    ids=["free_space", "perfect_ground", "real_ground"],
)
def test_request_preserves_exact_environment_instance(environment):
    request = build_ground_request(
        environment,
        theta=AngularSweep(start_deg=0.0, count=91, step_deg=1.0),
    )

    assert request.environment is environment


def test_request_is_immutable():
    request = build_request()

    with pytest.raises(dataclasses.FrozenInstanceError):
        request.frequency_mhz = 7.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# RadiationPatternRequest: mismas validaciones estructurales que
# SimulationRequest
# ---------------------------------------------------------------------------


def assert_same_rejection(simulation_kwargs, pattern_kwargs, match):
    """Ambas solicitudes rechazan la misma entrada con el mismo mensaje."""
    with pytest.raises(ValueError, match=match):
        SimulationRequest(**simulation_kwargs)

    with pytest.raises(ValueError, match=match):
        build_request(**pattern_kwargs)


@pytest.mark.parametrize(
    "frequency_mhz,match",
    [
        (0.0, "frecuencia debe ser positiva"),
        (math.nan, "frecuencia debe ser un número finito"),
    ],
)
def test_request_rejects_invalid_frequency_like_simulation_request(
    frequency_mhz,
    match,
):
    wire = create_free_space_wire()
    source = VoltageSource(wire_tag=1, segment=51)

    assert_same_rejection(
        {"frequency_mhz": frequency_mhz, "wires": (wire,), "source": source},
        {"frequency_mhz": frequency_mhz},
        match,
    )


def test_request_rejects_bool_frequency():
    # SimulationRequest acepta True como frecuencia (vale 1); la
    # solicitud de patrón no.
    with pytest.raises(ValueError, match="frecuencia"):
        build_request(frequency_mhz=True)


def test_request_requires_at_least_one_wire():
    source = VoltageSource(wire_tag=1, segment=1)

    assert_same_rejection(
        {"frequency_mhz": 14.15, "wires": (), "source": source},
        {"wires": (), "source": source},
        "al menos un conductor",
    )


def test_request_rejects_duplicated_wire_tags():
    first = create_wire_with_z(1.0, 2.0, tag=1)
    second = create_wire_with_z(3.0, 4.0, tag=1)
    source = create_source_for(first)

    assert_same_rejection(
        {
            "frequency_mhz": 14.15,
            "wires": (first, second),
            "source": source,
        },
        {"wires": (first, second), "source": source},
        "no pueden repetirse",
    )


def test_request_rejects_unknown_source_wire():
    wire = create_free_space_wire()
    source = VoltageSource(wire_tag=99, segment=51)

    assert_same_rejection(
        {"frequency_mhz": 14.15, "wires": (wire,), "source": source},
        {"wires": (wire,), "source": source},
        "conductor inexistente",
    )


def test_request_rejects_unknown_source_segment():
    wire = create_free_space_wire()
    source = VoltageSource(wire_tag=1, segment=200)

    assert_same_rejection(
        {"frequency_mhz": 14.15, "wires": (wire,), "source": source},
        {"wires": (wire,), "source": source},
        "segmento inexistente",
    )


# ---------------------------------------------------------------------------
# RadiationPatternRequest: conductores frente a z=0
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "environment",
    [PerfectGroundEnvironment(), build_real_ground()],
    ids=["perfect_ground", "real_ground"],
)
@pytest.mark.parametrize(
    "wire,match",
    [
        (create_wire_with_z(-2.0, 3.0), "coordenada z negativa"),
        (
            create_horizontal_wire_at_z(0.0),
            "completamente contenido en el plano de tierra",
        ),
    ],
    ids=["crossing", "contained_in_plane"],
)
def test_ground_rejects_wires_like_simulation_request(
    environment,
    wire,
    match,
):
    source = create_source_for(wire)

    assert_same_rejection(
        {
            "frequency_mhz": 14.15,
            "wires": (wire,),
            "source": source,
            "environment": environment,
        },
        {
            "wires": (wire,),
            "source": source,
            "environment": environment,
            "theta": AngularSweep(start_deg=0.0, count=91, step_deg=1.0),
        },
        match,
    )


@pytest.mark.parametrize(
    "wire",
    [create_wire_with_z(-5.0, -1.0), create_horizontal_wire_at_z(0.0)],
    ids=["below_z0", "contained_in_z0"],
)
def test_free_space_allows_any_z_like_simulation_request(wire):
    source = create_source_for(wire)

    SimulationRequest(frequency_mhz=14.15, wires=(wire,), source=source)
    request = build_request(wires=(wire,), source=source)

    assert request.wires == (wire,)


# ---------------------------------------------------------------------------
# RadiationPatternSample
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("gain_db", [2.1233, 0.0, -34.9789, 5])
def test_sample_accepts_finite_gains(gain_db):
    sample = RadiationPatternSample(
        theta_deg=90.0,
        phi_deg=90.0,
        gain_db=gain_db,
    )

    assert sample.gain_db == gain_db


def test_sample_accepts_none_as_explicit_null():
    sample = RadiationPatternSample(
        theta_deg=90.0,
        phi_deg=0.0,
        gain_db=None,
    )

    assert sample.gain_db is None


def test_sample_accepts_the_nec_sentinel_as_an_ordinary_number():
    # -999.99 es el centinela de NEC2 para una ganancia nula, pero el
    # dominio no lo conoce ni lo compara con ninguna constante: aquí es
    # solo un número finito más. Traducirlo a None (el nulo explícito
    # del dominio) es responsabilidad de la futura capa PyNEC, antes de
    # construir el resultado.
    sample = RadiationPatternSample(
        theta_deg=90.0,
        phi_deg=0.0,
        gain_db=-999.99,
    )

    assert sample.gain_db == -999.99


@pytest.mark.parametrize("gain_db", [math.nan, math.inf, True, "2.1"])
def test_sample_rejects_invalid_gain(gain_db):
    with pytest.raises(ValueError, match="ganancia"):
        RadiationPatternSample(theta_deg=0.0, phi_deg=0.0, gain_db=gain_db)


@pytest.mark.parametrize(
    "theta_deg,phi_deg",
    [(0.0, 0.0), (180.0, 360.0), (90, 270)],
)
def test_sample_accepts_angle_range_boundaries(theta_deg, phi_deg):
    sample = RadiationPatternSample(
        theta_deg=theta_deg,
        phi_deg=phi_deg,
        gain_db=0.0,
    )

    assert (sample.theta_deg, sample.phi_deg) == (theta_deg, phi_deg)


@pytest.mark.parametrize(
    "field,value,match",
    [
        ("theta_deg", -0.1, "theta"),
        ("theta_deg", 180.1, "theta"),
        ("theta_deg", math.nan, "theta"),
        ("theta_deg", True, "theta"),
        ("phi_deg", -0.1, "phi"),
        ("phi_deg", 360.1, "phi"),
        ("phi_deg", math.inf, "phi"),
        ("phi_deg", False, "phi"),
    ],
)
def test_sample_rejects_invalid_angles(field, value, match):
    values = {"theta_deg": 0.0, "phi_deg": 0.0, "gain_db": 0.0}
    values[field] = value

    with pytest.raises(ValueError, match=match):
        RadiationPatternSample(**values)


def test_sample_is_immutable():
    sample = RadiationPatternSample(theta_deg=0.0, phi_deg=0.0, gain_db=0.0)

    with pytest.raises(dataclasses.FrozenInstanceError):
        sample.gain_db = 1.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# RadiationPatternResult
# ---------------------------------------------------------------------------


def test_result_accepts_single_point_matrix():
    result = build_result(
        theta_angles_deg=(90.0,),
        phi_angles_deg=(90.0,),
        gain_db=((2.1233,),),
    )

    assert result.shape == (1, 1)
    assert result.n_theta == 1
    assert result.n_phi == 1


def test_result_accepts_non_square_matrix():
    result = build_result()

    assert result.n_theta == 2
    assert result.n_phi == 3
    assert result.shape == (2, 3)


def test_result_indexes_gain_as_theta_then_phi():
    result = build_result()

    # gain_db[theta_index][phi_index]
    assert result.gain_db[0][2] == 3.0
    assert result.gain_db[1][0] == 4.0
    assert result.gain_db[1][2] == -6.0


def test_result_samples_iterate_theta_outer_phi_inner():
    result = build_result()

    # Incluye el None de (90, 90): el nulo explícito se conserva.
    assert [
        (sample.theta_deg, sample.phi_deg, sample.gain_db)
        for sample in result.samples
    ] == [
        (0.0, 0.0, 1.0),
        (0.0, 90.0, 2.0),
        (0.0, 180.0, 3.0),
        (90.0, 0.0, 4.0),
        (90.0, 90.0, None),
        (90.0, 180.0, -6.0),
    ]
    assert isinstance(result.samples, tuple)
    assert all(
        isinstance(sample, RadiationPatternSample)
        for sample in result.samples
    )


def test_result_accepts_both_phi_seam_angles():
    result = build_result(
        theta_angles_deg=(90.0,),
        phi_angles_deg=(0.0, 360.0),
        gain_db=((None, None),),
    )

    assert result.phi_angles_deg == (0.0, 360.0)


@pytest.mark.parametrize(
    "gain_db",
    [
        ((1.0, 2.0, 3.0),),
        ((1.0, 2.0, 3.0), (4.0, 5.0, 6.0), (7.0, 8.0, 9.0)),
    ],
    ids=["missing_row", "extra_row"],
)
def test_result_rejects_wrong_row_count(gain_db):
    with pytest.raises(ValueError, match="fila por cada ángulo theta"):
        build_result(gain_db=gain_db)


@pytest.mark.parametrize(
    "gain_db",
    [
        ((1.0, 2.0), (4.0, 5.0)),
        ((1.0, 2.0, 3.0, 0.0), (4.0, 5.0, 6.0, 0.0)),
        ((1.0, 2.0, 3.0), (4.0, 5.0)),
    ],
    ids=["missing_columns", "extra_columns", "ragged"],
)
def test_result_rejects_wrong_column_count(gain_db):
    with pytest.raises(ValueError, match="columna por cada ángulo phi"):
        build_result(gain_db=gain_db)


def test_result_rejects_mutable_rows():
    with pytest.raises(ValueError, match="columna por cada ángulo phi"):
        build_result(gain_db=([1.0, 2.0, 3.0], (4.0, 5.0, 6.0)))


def test_result_rejects_mutable_matrix():
    with pytest.raises(ValueError, match="fila por cada ángulo theta"):
        build_result(gain_db=[(1.0, 2.0, 3.0), (4.0, 5.0, 6.0)])


@pytest.mark.parametrize("field", ["theta_angles_deg", "phi_angles_deg"])
def test_result_rejects_mutable_angle_lists(field):
    angles = list(getattr(build_result(), field))

    with pytest.raises(ValueError, match="tupla no vacía"):
        build_result(**{field: angles})


@pytest.mark.parametrize("field", ["theta_angles_deg", "phi_angles_deg"])
def test_result_rejects_empty_angles(field):
    with pytest.raises(ValueError, match="tupla no vacía"):
        build_result(**{field: ()})


@pytest.mark.parametrize(
    "frequency_mhz,match",
    [
        (math.nan, "número finito"),
        (True, "número finito"),
        (0.0, "positiva"),
    ],
)
def test_result_rejects_invalid_frequency(frequency_mhz, match):
    with pytest.raises(ValueError, match=match):
        build_result(frequency_mhz=frequency_mhz)


@pytest.mark.parametrize(
    "theta_angles_deg",
    [(0.0, math.nan), (0.0, True), (-1.0, 90.0), (0.0, 181.0)],
)
def test_result_rejects_invalid_theta_angles(theta_angles_deg):
    with pytest.raises(ValueError, match="theta"):
        build_result(theta_angles_deg=theta_angles_deg)


@pytest.mark.parametrize(
    "phi_angles_deg",
    [
        (0.0, 90.0, math.inf),
        (0.0, 90.0, False),
        (-1.0, 90.0, 180.0),
        (0.0, 90.0, 361.0),
    ],
)
def test_result_rejects_invalid_phi_angles(phi_angles_deg):
    with pytest.raises(ValueError, match="phi"):
        build_result(phi_angles_deg=phi_angles_deg)


@pytest.mark.parametrize("gain", [math.nan, math.inf, True, "1"])
def test_result_rejects_invalid_gains(gain):
    with pytest.raises(ValueError, match="ganancia"):
        build_result(gain_db=((1.0, 2.0, 3.0), (4.0, gain, 6.0)))


def test_result_accepts_negative_and_integer_gains():
    result = build_result(gain_db=((-1, 0, 2), (-34.98, -12.44, 6.63)))

    assert result.gain_db[0] == (-1, 0, 2)


def test_result_is_immutable():
    result = build_result()

    with pytest.raises(dataclasses.FrozenInstanceError):
        result.gain_db = ()  # type: ignore[misc]
