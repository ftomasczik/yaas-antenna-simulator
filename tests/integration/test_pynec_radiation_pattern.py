"""Patrones de radiación con PyNecEngine (frecuencia única).

Valores de referencia: docs/research/nec-radiation-patterns.md y
docs/validation/radiation-patterns-4nec2.md. Las tolerancias numéricas
(1e-3 dB) parten de los valores completos de PyNEC, no del redondeo a
dos decimales de 4nec2: los valores de referencia están registrados
con cuatro decimales (error de redondeo <= 5e-5 dB), y el margen
restante cubre diferencias de punto flotante entre plataformas.
"""

import math

import numpy as np
import pytest

import yaas.engines.pynec as pynec_module
from yaas.domain import (
    AngularSweep,
    FreeSpaceEnvironment,
    PerfectGroundEnvironment,
    Point3D,
    RadiationPatternRequest,
    RadiationPatternResult,
    RealGroundEnvironment,
    VoltageSource,
    Wire,
)
from yaas.engines import PyNecEngine

GAIN_TOLERANCE_DB = 1e-3


def create_free_space_dipole() -> Wire:
    return Wire(
        tag=1,
        start=Point3D(-5.03, 0.0, 0.0),
        end=Point3D(5.03, 0.0, 0.0),
        radius_m=0.001,
        segments=101,
    )


def create_monopole() -> Wire:
    return Wire(
        tag=1,
        start=Point3D(0.0, 0.0, 0.0),
        end=Point3D(0.0, 0.0, 5.03),
        radius_m=0.001,
        segments=38,
    )


def create_real_ground_dipole() -> Wire:
    return Wire(
        tag=1,
        start=Point3D(-5.03, 0.0, 10.0),
        end=Point3D(5.03, 0.0, 10.0),
        radius_m=0.001,
        segments=101,
    )


def single_angle(angle_deg: float) -> AngularSweep:
    return AngularSweep(start_deg=angle_deg, count=1, step_deg=0.0)


def build_request(
    wire: Wire,
    environment,
    segment: int,
    theta: AngularSweep,
    phi: AngularSweep,
) -> RadiationPatternRequest:
    return RadiationPatternRequest(
        wires=(wire,),
        environment=environment,
        source=VoltageSource(wire_tag=1, segment=segment),
        frequency_mhz=14.15,
        theta=theta,
        phi=phi,
    )


def assert_angles(angles, start_deg: float, step_deg: float, count: int):
    """Los ángulos devueltos por PyNEC conservan inicio, paso y conteo."""
    assert angles == pytest.approx(
        tuple(start_deg + index * step_deg for index in range(count)),
        abs=1e-9,
    )


def column(result: RadiationPatternResult) -> list:
    """Corte vertical (n_phi == 1): ganancia por índice de theta."""
    return [row[0] for row in result.gain_db]


# ---------------------------------------------------------------------------
# Modelos validados (PyNEC real). Alcance de módulo: cada patrón se
# calcula una sola vez, en particular el de tierra real, que es el más
# lento.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def engine() -> PyNecEngine:
    return PyNecEngine()


@pytest.fixture(scope="module")
def free_space_vertical(engine) -> RadiationPatternResult:
    return engine.simulate_radiation_pattern(
        build_request(
            create_free_space_dipole(),
            FreeSpaceEnvironment(),
            51,
            theta=AngularSweep(start_deg=0.0, count=181, step_deg=1.0),
            phi=single_angle(0.0),
        )
    )


@pytest.fixture(scope="module")
def free_space_azimuth(engine) -> RadiationPatternResult:
    return engine.simulate_radiation_pattern(
        build_request(
            create_free_space_dipole(),
            FreeSpaceEnvironment(),
            51,
            theta=single_angle(90.0),
            phi=AngularSweep(start_deg=0.0, count=361, step_deg=1.0),
        )
    )


@pytest.fixture(scope="module")
def monopole_vertical(engine) -> RadiationPatternResult:
    return engine.simulate_radiation_pattern(
        build_request(
            create_monopole(),
            PerfectGroundEnvironment(),
            1,
            theta=AngularSweep(start_deg=0.0, count=91, step_deg=1.0),
            phi=single_angle(0.0),
        )
    )


@pytest.fixture(scope="module")
def real_ground_vertical(engine) -> RadiationPatternResult:
    # theta termina exactamente en 90: con tierra, theta > 90 no es
    # reproducible y el dominio lo rechaza.
    return engine.simulate_radiation_pattern(
        build_request(
            create_real_ground_dipole(),
            RealGroundEnvironment(
                relative_permittivity=13.0,
                conductivity_s_per_m=0.005,
            ),
            51,
            theta=AngularSweep(start_deg=0.0, count=91, step_deg=1.0),
            phi=single_angle(0.0),
        )
    )


def test_free_space_vertical_cut(free_space_vertical):
    gains = column(free_space_vertical)
    finite_gains = [gain for gain in gains if gain is not None]

    assert free_space_vertical.shape == (181, 1)
    assert free_space_vertical.frequency_mhz == 14.15
    assert_angles(free_space_vertical.theta_angles_deg, 0.0, 1.0, 181)
    assert free_space_vertical.phi_angles_deg == pytest.approx((0.0,))
    assert max(finite_gains) == pytest.approx(2.1233, abs=GAIN_TOLERANCE_DB)
    assert gains[0] == pytest.approx(2.1233, abs=GAIN_TOLERANCE_DB)
    assert gains[90] is None
    assert gains[180] == pytest.approx(2.1233, abs=GAIN_TOLERANCE_DB)
    # Solo la dirección del eje del conductor es nula en este corte.
    assert gains.count(None) == 1


def test_free_space_vertical_cut_is_symmetric(free_space_vertical):
    # Conductor en el plano XY, espacio libre: G(theta) == G(180 - theta).
    # La diferencia observada es ~5e-9 dB.
    gains = column(free_space_vertical)

    for theta_index in range(181):
        mirrored = gains[180 - theta_index]

        if gains[theta_index] is None:
            assert mirrored is None
        else:
            assert gains[theta_index] == pytest.approx(mirrored, abs=1e-6)


def test_free_space_azimuth_cut(free_space_azimuth):
    gains = free_space_azimuth.gain_db[0]

    assert free_space_azimuth.shape == (1, 361)
    assert free_space_azimuth.theta_angles_deg == pytest.approx((90.0,))
    assert_angles(free_space_azimuth.phi_angles_deg, 0.0, 1.0, 361)
    # Nulos a lo largo de +-X, incluida la costura 0/360.
    for phi_deg in (0, 180, 360):
        assert gains[phi_deg] is None
    # Máximos hacia +-Y.
    for phi_deg in (90, 270):
        assert gains[phi_deg] == pytest.approx(
            2.1233, abs=GAIN_TOLERANCE_DB
        )
    for phi_deg in (45, 135, 225, 315):
        assert gains[phi_deg] == pytest.approx(
            -1.8418, abs=GAIN_TOLERANCE_DB
        )


def test_monopole_over_perfect_ground_vertical_cut(monopole_vertical):
    gains = column(monopole_vertical)

    assert monopole_vertical.shape == (91, 1)
    assert_angles(monopole_vertical.theta_angles_deg, 0.0, 1.0, 91)
    assert monopole_vertical.phi_angles_deg == pytest.approx((0.0,))
    assert gains[0] is None
    assert gains[1] == pytest.approx(-31.9684, abs=GAIN_TOLERANCE_DB)
    assert gains[90] == pytest.approx(5.1334, abs=GAIN_TOLERANCE_DB)


def test_dipole_over_real_ground_vertical_cut(real_ground_vertical):
    gains = column(real_ground_vertical)
    finite_gains = [gain for gain in gains if gain is not None]

    assert real_ground_vertical.shape == (91, 1)
    assert_angles(real_ground_vertical.theta_angles_deg, 0.0, 1.0, 91)
    assert real_ground_vertical.phi_angles_deg == pytest.approx((0.0,))
    assert gains[43] == pytest.approx(0.0944, abs=GAIN_TOLERANCE_DB)
    assert max(finite_gains) == gains[43]
    assert gains[89] == pytest.approx(-29.5103, abs=GAIN_TOLERANCE_DB)
    assert gains[90] is None


def test_non_square_grid_keeps_theta_phi_orientation(engine):
    # Dipolo sobre X. theta = 0/45/90, phi = 0/90/180/270/360.
    # theta=0 es el cenit (máximo en cualquier phi); en theta=90 el
    # patrón es nulo a lo largo de X (phi=0/180/360) y máximo hacia Y.
    # Una matriz traspuesta ubicaría estos nulos en otras celdas.
    result = engine.simulate_radiation_pattern(
        build_request(
            create_free_space_dipole(),
            FreeSpaceEnvironment(),
            51,
            theta=AngularSweep(start_deg=0.0, count=3, step_deg=45.0),
            phi=AngularSweep(start_deg=0.0, count=5, step_deg=90.0),
        )
    )

    assert result.shape == (3, 5)
    assert_angles(result.theta_angles_deg, 0.0, 45.0, 3)
    assert_angles(result.phi_angles_deg, 0.0, 90.0, 5)
    assert all(
        gain == pytest.approx(2.1233, abs=GAIN_TOLERANCE_DB)
        for gain in result.gain_db[0]
    )
    assert result.gain_db[1][0] == pytest.approx(
        -1.8418, abs=GAIN_TOLERANCE_DB
    )
    assert result.gain_db[1][1] == pytest.approx(
        2.1233, abs=GAIN_TOLERANCE_DB
    )
    assert [gain is None for gain in result.gain_db[2]] == [
        True, False, True, False, True,
    ]

    samples = result.samples
    assert [(s.theta_deg, s.phi_deg) for s in samples[:6]] == [
        (0.0, 0.0),
        (0.0, 90.0),
        (0.0, 180.0),
        (0.0, 270.0),
        (0.0, 360.0),
        (45.0, 0.0),
    ]
    assert samples[10].theta_deg == 90.0
    assert samples[10].gain_db is None


def test_result_contains_only_native_python_numbers(free_space_azimuth):
    # Ningún tipo de numpy llega al dominio.
    assert all(
        type(angle) is float
        for angle in free_space_azimuth.phi_angles_deg
    )
    assert all(
        gain is None or type(gain) is float
        for gain in free_space_azimuth.gain_db[0]
    )


# ---------------------------------------------------------------------------
# Dobles de prueba de la API nativa: orden de llamadas y fallos de
# integración, sin provocar ningún fallo nativo real.
# ---------------------------------------------------------------------------


THETA = AngularSweep(start_deg=10.0, count=3, step_deg=20.0)
PHI = AngularSweep(start_deg=5.0, count=5, step_deg=30.0)
THETA_ANGLES = np.array([10.0, 30.0, 50.0])
PHI_ANGLES = np.array([5.0, 35.0, 65.0, 95.0, 125.0])


_DEFAULT_GAIN = object()


class FakePattern:
    def __init__(
        self,
        gain=_DEFAULT_GAIN,
        theta_angles=THETA_ANGLES,
        phi_angles=PHI_ANGLES,
    ):
        if gain is _DEFAULT_GAIN:
            gain = np.arange(15, dtype=float).reshape(3, 5) - 20.0
        self._gain = gain
        self._theta_angles = theta_angles
        self._phi_angles = phi_angles

    def get_gain(self):
        return self._gain

    def get_theta_angles(self):
        return self._theta_angles

    def get_phi_angles(self):
        return self._phi_angles


class FakeGeometry:
    def __init__(self, calls):
        self._calls = calls

    def wire(self, *args):
        self._calls.append(("wire", args))


class FakeContext:
    """Registra cada llamada a la API de nec_context, en orden."""

    def __init__(self, calls, pattern):
        self._calls = calls
        self._pattern = pattern

    def get_geometry(self):
        return FakeGeometry(self._calls)

    def get_radiation_pattern(self, index):
        self._calls.append(("get_radiation_pattern", (index,)))
        return self._pattern

    def __getattr__(self, name):
        def record(*args):
            self._calls.append((name, args))

        return record


class FakeNative:
    def __init__(self, monkeypatch):
        self.calls = []
        self.contexts = []
        self.pattern = FakePattern()
        monkeypatch.setattr(pynec_module, "nec_context", self._create)

    def _create(self):
        context = FakeContext(self.calls, self.pattern)
        self.contexts.append(context)
        return context

    def names(self):
        return [name for name, _ in self.calls]

    def args_of(self, name):
        return [args for call_name, args in self.calls if call_name == name]


@pytest.fixture
def fake_native(monkeypatch) -> FakeNative:
    return FakeNative(monkeypatch)


def simulate_fake() -> RadiationPatternResult:
    return PyNecEngine().simulate_radiation_pattern(
        build_request(
            create_free_space_dipole(),
            FreeSpaceEnvironment(),
            51,
            theta=THETA,
            phi=PHI,
        )
    )


def test_pattern_uses_the_verified_pynec_call_order(fake_native):
    simulate_fake()
    names = fake_native.names()

    assert len(fake_native.contexts) == 1
    assert names.index("fr_card") < names.index("ex_card")
    assert names.index("ex_card") < names.index("rp_card")
    assert names.count("rp_card") == 1
    assert "xq_card" not in names
    assert fake_native.args_of("fr_card") == [(0, 1, 14.15, 0.0)]
    # Una sola frecuencia y una sola tarjeta RP en un contexto nuevo:
    # el único patrón es el de índice 0, leído una vez, después de RP.
    assert fake_native.args_of("get_radiation_pattern") == [(0,)]
    assert names.index("rp_card") < names.index("get_radiation_pattern")


def test_pattern_passes_rp_card_arguments_in_position(fake_native):
    # Valores angulares distintos entre sí, para que cualquier
    # intercambio theta/phi o inicio/paso cambie la tupla.
    simulate_fake()

    assert fake_native.args_of("rp_card") == [
        (
            0,       # calc_mode
            3,       # n_theta
            5,       # n_phi
            0, 0, 0, 0,  # output_format, normalization, D, A
            10.0,    # theta0
            5.0,     # phi0
            20.0,    # delta_theta
            30.0,    # delta_phi
            0.0,     # radial_distance
            0.0,     # gain_norm
        )
    ]


def test_each_request_creates_its_own_context(fake_native):
    simulate_fake()
    simulate_fake()

    assert len(fake_native.contexts) == 2
    assert fake_native.names().count("rp_card") == 2


def test_fake_pattern_keeps_orientation_and_negative_gains(fake_native):
    result = simulate_fake()

    assert result.shape == (3, 5)
    assert result.theta_angles_deg == (10.0, 30.0, 50.0)
    assert result.gain_db[0] == (-20.0, -19.0, -18.0, -17.0, -16.0)
    assert result.gain_db[2][4] == -6.0


@pytest.mark.parametrize(
    "native_value,expected",
    [
        (-999.99, None),
        # Diferencias dentro de la tolerancia absoluta (1e-6 dB),
        # atribuibles a representación en punto flotante.
        (-999.99 + 5e-7, None),
        (-999.99 - 5e-7, None),
        # Fuera de la tolerancia: son ganancias ordinarias. La regla es
        # igualdad controlada, no una condición amplia como <= -999.
        (-999.98, -999.98),
        (-999.0, -999.0),
        (-34.98, -34.98),
    ],
)
def test_only_the_nec_sentinel_becomes_none(
    fake_native,
    native_value,
    expected,
):
    gain = np.full((3, 5), -10.0)
    gain[1, 2] = native_value
    fake_native.pattern = FakePattern(gain=gain)

    result = simulate_fake()

    assert result.gain_db[1][2] == expected
    assert sum(row.count(None) for row in result.gain_db) == (
        1 if expected is None else 0
    )


def test_missing_pattern_raises_runtime_error(fake_native):
    fake_native.pattern = None

    with pytest.raises(RuntimeError, match="ningún patrón"):
        simulate_fake()


@pytest.mark.parametrize(
    "gain",
    [
        np.zeros((5, 3)),
        np.zeros((3, 4)),
        np.zeros(15),
        np.zeros((2, 5)),
    ],
    ids=["transposed", "missing_column", "flat", "missing_row"],
)
def test_unexpected_gain_shape_raises_runtime_error(fake_native, gain):
    fake_native.pattern = FakePattern(gain=gain)

    with pytest.raises(RuntimeError, match=r"forma.*\(3, 5\)"):
        simulate_fake()


@pytest.mark.parametrize(
    "field,angles,match",
    [
        ("theta_angles", np.array([10.0, 30.0]), "2 ángulos theta"),
        ("phi_angles", np.array([5.0, 35.0, 65.0, 95.0]), "4 ángulos phi"),
    ],
    ids=["theta", "phi"],
)
def test_unexpected_angle_count_raises_runtime_error(
    fake_native,
    field,
    angles,
    match,
):
    fake_native.pattern = FakePattern(**{field: angles})

    with pytest.raises(RuntimeError, match=match):
        simulate_fake()


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_non_finite_gain_raises_runtime_error(fake_native, value):
    gain = np.zeros((3, 5))
    gain[1, 3] = value
    fake_native.pattern = FakePattern(gain=gain)

    # Un NaN/Inf nativo es un fallo, nunca un nulo (None).
    with pytest.raises(RuntimeError, match="no finita.*theta=30.*phi=95"):
        simulate_fake()


@pytest.mark.parametrize(
    "field,angles",
    [
        ("theta_angles", np.array([10.0, math.nan, 50.0])),
        ("phi_angles", np.array([5.0, 35.0, math.inf, 95.0, 125.0])),
    ],
    ids=["theta_nan", "phi_inf"],
)
def test_non_finite_angle_raises_runtime_error(fake_native, field, angles):
    fake_native.pattern = FakePattern(**{field: angles})

    with pytest.raises(RuntimeError, match="no finitos"):
        simulate_fake()


@pytest.mark.parametrize(
    "gain",
    [None, 42, object(), [1.0, 2.0, 3.0]],
    ids=["none", "scalar", "object", "rows_not_iterable"],
)
def test_unusable_gain_object_raises_runtime_error(fake_native, gain):
    fake_native.pattern = FakePattern(gain=gain)

    with pytest.raises(RuntimeError, match=r"forma.*\(3, 5\)"):
        simulate_fake()


@pytest.mark.parametrize(
    "field,angles",
    [
        ("theta_angles", None),
        ("phi_angles", 42),
        ("theta_angles", ["a", "b", "c"]),
    ],
    ids=["theta_none", "phi_not_iterable", "theta_not_numeric"],
)
def test_unconvertible_angles_raise_runtime_error(fake_native, field, angles):
    fake_native.pattern = FakePattern(**{field: angles})

    with pytest.raises(RuntimeError, match="no pueden convertirse"):
        simulate_fake()


@pytest.mark.parametrize("cell", ["x", None], ids=["string", "none"])
def test_unconvertible_gain_cell_raises_runtime_error(fake_native, cell):
    gain = np.zeros((3, 5), dtype=object)
    gain[2, 1] = cell
    fake_native.pattern = FakePattern(gain=gain)

    with pytest.raises(
        RuntimeError, match="no puede convertirse.*theta=50.*phi=35"
    ):
        simulate_fake()
