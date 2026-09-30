"""Modelos fundamentales del simulador."""

import math
from dataclasses import dataclass
from enum import Enum

from yaas.domain.calculations import (
    calculate_swr,
    reflection_coefficient_to_impedance,
)


def _validate_finite(value: float, name: str) -> None:
    """Comprueba que un valor numérico sea finito."""
    if not math.isfinite(value):
        raise ValueError(f"{name} debe ser un número finito.")


def _validate_wires_against_ground(
    wires: "tuple[Wire, ...]",
    environment: "Environment",
) -> None:
    """Verifica los conductores contra el plano de tierra, si aplica.

    En espacio libre (``FreeSpaceEnvironment``) no se aplica ninguna
    restricción aquí: se conserva exactamente el comportamiento
    actual, incluidas coordenadas z negativas o conductores en z=0.

    Cuando el entorno declara un plano de tierra en z=0 (por ahora,
    ``PerfectGroundEnvironment``), todo extremo de todo conductor debe
    cumplir z >= 0 (comparación estricta con cero, sin tolerancia), y
    ningún conductor puede quedar completamente contenido en el plano
    de tierra (z=0 en ambos extremos): eso sería un radial de pantalla
    de tierra, no un conductor común, y YAAS no lo modela.
    """
    if isinstance(environment, FreeSpaceEnvironment):
        return

    for wire in wires:
        z1 = wire.start.z
        z2 = wire.end.z

        if z1 < 0 or z2 < 0:
            raise ValueError(
                f"El conductor {wire.tag} tiene un extremo con "
                "coordenada z negativa; con un plano de tierra, todo "
                "conductor debe cumplir z >= 0."
            )

        if z1 == 0 and z2 == 0:
            raise ValueError(
                f"El conductor {wire.tag} queda completamente "
                "contenido en el plano de tierra (z=0 en ambos "
                "extremos)."
            )


@dataclass(frozen=True)
class Point3D:
    """Punto tridimensional expresado en metros."""

    x: float
    y: float
    z: float

    def __post_init__(self) -> None:
        _validate_finite(self.x, "x")
        _validate_finite(self.y, "y")
        _validate_finite(self.z, "z")


@dataclass(frozen=True)
class Wire:
    """Conductor recto representado mediante segmentos NEC."""

    tag: int
    start: Point3D
    end: Point3D
    radius_m: float
    segments: int

    def __post_init__(self) -> None:
        if self.tag <= 0:
            raise ValueError(
                "La etiqueta del conductor debe ser positiva."
            )

        if self.segments <= 0:
            raise ValueError(
                "La cantidad de segmentos debe ser positiva."
            )

        _validate_finite(
            self.radius_m,
            "El radio del conductor",
        )

        if self.radius_m <= 0:
            raise ValueError(
                "El radio del conductor debe ser positivo."
            )

        if self.start == self.end:
            raise ValueError(
                "Los extremos del conductor deben ser diferentes."
            )


@dataclass(frozen=True)
class VoltageSource:
    """Fuente de tensión aplicada a un segmento."""

    wire_tag: int
    segment: int
    voltage: complex = complex(1.0, 0.0)

    def __post_init__(self) -> None:
        if self.wire_tag <= 0:
            raise ValueError(
                "La etiqueta de la fuente debe ser positiva."
            )

        if self.segment <= 0:
            raise ValueError(
                "El segmento de alimentación debe ser positivo."
            )

        if not math.isfinite(self.voltage.real):
            raise ValueError(
                "La parte real de la tensión debe ser finita."
            )

        if not math.isfinite(self.voltage.imag):
            raise ValueError(
                "La parte imaginaria de la tensión debe ser finita."
            )


@dataclass(frozen=True)
class FreeSpaceEnvironment:
    """Sin plano de tierra: comportamiento actual de YAAS."""


@dataclass(frozen=True)
class PerfectGroundEnvironment:
    """Plano de tierra perfectamente conductor en z=0."""


class RealGroundModel(str, Enum):
    """Método NEC2 usado para calcular tierra real (con pérdidas).

    Un único valor por ahora: Sommerfeld-Norton, el único método
    validado para YAAS hasta el momento (ver
    ``docs/research/nec-real-ground.md`` y
    ``docs/validation/real-ground-dipole-4nec2.md``). El coeficiente
    de reflexión queda deliberadamente fuera: la investigación
    encontró resultados sin sentido físico para conductores cercanos
    al plano de tierra, y su alcance quedó pospuesto para una fase
    posterior.
    """

    SOMMERFELD_NORTON = "sommerfeld_norton"


@dataclass(frozen=True)
class RealGroundEnvironment:
    """Tierra real homogénea (con pérdidas) en z=0.

    Todavía no soportada por ``PyNecEngine``: este tipo de dominio se
    agrega antes que el motor, siguiendo el mismo orden ya usado en la
    fase 7A para introducir ``PerfectGroundEnvironment``. Hasta que el
    motor lo admita explícitamente, cualquier intento de simular con
    este entorno debe rechazarse con claridad en vez de simularse de
    forma incorrecta.

    ``conductivity_s_per_m=0.0`` se admite explícitamente: representa
    un dieléctrico homogéneo sin pérdidas, un caso límite válido de la
    formulación física, distinto de "no hay tierra" (eso se expresa
    con ``FreeSpaceEnvironment``).
    """

    relative_permittivity: float
    conductivity_s_per_m: float
    model: RealGroundModel = RealGroundModel.SOMMERFELD_NORTON

    def __post_init__(self) -> None:
        _validate_finite(
            self.relative_permittivity,
            "La permitividad relativa",
        )

        if self.relative_permittivity <= 0:
            raise ValueError(
                "La permitividad relativa debe ser positiva."
            )

        _validate_finite(
            self.conductivity_s_per_m,
            "La conductividad",
        )

        if self.conductivity_s_per_m < 0:
            raise ValueError(
                "La conductividad no puede ser negativa."
            )

        if not isinstance(self.model, RealGroundModel):
            raise ValueError(
                "El método de tierra real debe ser un "
                "RealGroundModel válido."
            )


Environment = (
    FreeSpaceEnvironment
    | PerfectGroundEnvironment
    | RealGroundEnvironment
)


@dataclass(frozen=True)
class SimulationRequest:
    """Datos necesarios para ejecutar una simulación básica."""

    frequency_mhz: float
    wires: tuple[Wire, ...]
    source: VoltageSource
    reference_impedance: float = 50.0
    environment: Environment = FreeSpaceEnvironment()

    def __post_init__(self) -> None:
        _validate_finite(
            self.frequency_mhz,
            "La frecuencia",
        )

        if self.frequency_mhz <= 0:
            raise ValueError(
                "La frecuencia debe ser positiva."
            )

        if not self.wires:
            raise ValueError(
                "La simulación debe contener al menos un conductor."
            )

        _validate_wires_against_ground(
            self.wires,
            self.environment,
        )

        _validate_finite(
            self.reference_impedance,
            "La impedancia de referencia",
        )

        if self.reference_impedance <= 0:
            raise ValueError(
                "La impedancia de referencia debe ser positiva."
            )

        tags = [wire.tag for wire in self.wires]

        if len(tags) != len(set(tags)):
            raise ValueError(
                "Las etiquetas de los conductores no pueden repetirse."
            )

        source_wire = next(
            (
                wire
                for wire in self.wires
                if wire.tag == self.source.wire_tag
            ),
            None,
        )

        if source_wire is None:
            raise ValueError(
                "La fuente referencia un conductor inexistente."
            )

        if self.source.segment > source_wire.segments:
            raise ValueError(
                "La fuente referencia un segmento inexistente."
            )


@dataclass(frozen=True)
class SimulationResult:
    """Resultado básico normalizado de una simulación."""

    frequency_mhz: float
    impedance: complex
    swr: float

@dataclass(frozen=True)
class SweepRequest:
    """Parámetros para un barrido lineal de frecuencia."""

    start_frequency_mhz: float
    stop_frequency_mhz: float
    points: int
    wires: tuple[Wire, ...]
    source: VoltageSource
    reference_impedance: float = 50.0
    environment: Environment = FreeSpaceEnvironment()

    def __post_init__(self) -> None:
        _validate_finite(
            self.start_frequency_mhz,
            "La frecuencia inicial",
        )
        _validate_finite(
            self.stop_frequency_mhz,
            "La frecuencia final",
        )

        if self.start_frequency_mhz <= 0:
            raise ValueError(
                "La frecuencia inicial debe ser positiva."
            )

        if self.stop_frequency_mhz <= self.start_frequency_mhz:
            raise ValueError(
                "La frecuencia final debe ser mayor "
                "que la frecuencia inicial."
            )

        if (
            not isinstance(self.points, int)
            or isinstance(self.points, bool)
            or self.points < 2
        ):
            raise ValueError(
                "El barrido debe contener al menos dos puntos."
            )

        # Reutiliza las validaciones de conductores, fuente,
        # impedancia de referencia y entorno.
        SimulationRequest(
            frequency_mhz=self.start_frequency_mhz,
            wires=self.wires,
            source=self.source,
            reference_impedance=self.reference_impedance,
            environment=self.environment,
        )

    @property
    def frequency_step_mhz(self) -> float:
        """Separación lineal entre puntos consecutivos."""
        return (
            self.stop_frequency_mhz
            - self.start_frequency_mhz
        ) / (self.points - 1)


@dataclass(frozen=True)
class SweepPoint:
    """Resultado correspondiente a una frecuencia del barrido."""

    frequency_mhz: float
    impedance: complex
    swr: float


@dataclass(frozen=True)
class SwrBandwidth:
    """Intervalo continuo que satisface un límite de ROE.

    ``truncated_below``/``truncated_above`` indican que el intervalo
    alcanza el primer o el último punto muestreado del barrido: en
    ese caso no se sabe si el límite de ROE se sigue cumpliendo más
    allá del rango barrido, así que ese extremo no debe presentarse
    como si fuera el límite real del ancho de banda.
    """

    threshold: float
    lower_frequency_mhz: float
    upper_frequency_mhz: float
    truncated_below: bool = False
    truncated_above: bool = False

    @property
    def bandwidth_mhz(self) -> float:
        """Ancho del intervalo expresado en MHz."""
        return (
            self.upper_frequency_mhz
            - self.lower_frequency_mhz
        )

    @property
    def bandwidth_khz(self) -> float:
        """Ancho del intervalo expresado en kHz."""
        return self.bandwidth_mhz * 1000.0

    @property
    def center_frequency_mhz(self) -> float:
        """Frecuencia central del intervalo."""
        return (
            self.lower_frequency_mhz
            + self.upper_frequency_mhz
        ) / 2.0

    @property
    def fractional_bandwidth_percent(self) -> float:
        """Ancho de banda porcentual respecto del centro."""
        return (
            self.bandwidth_mhz
            / self.center_frequency_mhz
            * 100.0
        )


@dataclass(frozen=True)
class SweepResult:
    """Resultado completo de un barrido de frecuencia."""

    points: tuple[SweepPoint, ...]

    def __post_init__(self) -> None:
        if not self.points:
            raise ValueError(
                "El barrido debe contener resultados."
            )

    @property
    def resonance_point(self) -> SweepPoint | None:
        """Mínima reactancia absoluta entre impedancias finitas, o None.

        Es una estimación muestreada; no demuestra un cruce por cero.
        """
        return min(
            (
                point for point in self.points
                if math.isfinite(point.impedance.real)
                and math.isfinite(point.impedance.imag)
            ),
            key=lambda point: abs(point.impedance.imag),
            default=None,
        )

    @property
    def resonance_is_at_boundary(self) -> bool:
        """Indica si la resonancia coincide, por valor, con un extremo.

        Un único punto es un extremo. Compara por valor (no por
        identidad) para detectar también un empate entre el punto
        elegido por ``resonance_point`` y un extremo del barrido,
        igual que ``MeasurementSweep.minimum_swr_is_at_boundary``. Si
        no hay ningún candidato finito, no aplica (``False``): la
        resonancia ya se presenta como no disponible en ese caso.
        """
        point = self.resonance_point

        if point is None:
            return False

        magnitude = abs(point.impedance.imag)

        return (
            magnitude == abs(self.points[0].impedance.imag)
            or magnitude == abs(self.points[-1].impedance.imag)
        )

    @property
    def minimum_swr_point(self) -> SweepPoint:
        """Punto con la menor ROE del barrido."""
        return min(
            self.points,
            key=lambda point: point.swr,
        )

    @property
    def minimum_swr_is_at_boundary(self) -> bool:
        """Indica si la ROE mínima coincide, por valor, con un extremo.

        Ver ``MeasurementSweep.minimum_swr_is_at_boundary``: misma
        definición, aplicada a un barrido simulado.
        """
        minimum = self.minimum_swr_point.swr

        return (
            minimum == self.points[0].swr
            or minimum == self.points[-1].swr
        )

    def swr_bandwidth(
        self,
        threshold: float = 2.0,
    ) -> SwrBandwidth | None:
        """Obtiene el intervalo continuo alrededor de la ROE mínima.

        Los límites corresponden a los puntos muestreados. En esta
        primera implementación no se interpolan los cruces exactos.

        Args:
            threshold: Límite máximo de ROE admitido.

        Returns:
            El intervalo encontrado o None si ningún punto cumple
            el límite.

        Raises:
            ValueError: Si el límite es menor que 1.
        """
        if not math.isfinite(threshold) or threshold < 1.0:
            raise ValueError(
                "El límite de ROE debe ser finito y mayor o igual a 1."
            )

        minimum_index = min(
            range(len(self.points)),
            key=lambda index: self.points[index].swr,
        )

        if self.points[minimum_index].swr > threshold:
            return None

        lower_index = minimum_index

        while (
            lower_index > 0
            and self.points[lower_index - 1].swr <= threshold
        ):
            lower_index -= 1

        upper_index = minimum_index

        while (
            upper_index < len(self.points) - 1
            and self.points[upper_index + 1].swr <= threshold
        ):
            upper_index += 1

        return SwrBandwidth(
            threshold=threshold,
            lower_frequency_mhz=(
                self.points[lower_index].frequency_mhz
            ),
            upper_frequency_mhz=(
                self.points[upper_index].frequency_mhz
            ),
            # El intervalo llega al primer/último punto muestreado:
            # no se sabe si el límite de ROE se sigue cumpliendo más
            # allá del barrido.
            truncated_below=(lower_index == 0),
            truncated_above=(
                upper_index == len(self.points) - 1
            ),
        )

@dataclass(frozen=True)
class MeasurementPoint:
    """Punto S11 medido en una frecuencia."""

    frequency_mhz: float
    reflection_coefficient: complex
    reference_impedance: float = 50.0

    def __post_init__(self) -> None:
        _validate_finite(
            self.frequency_mhz,
            "La frecuencia medida",
        )

        if self.frequency_mhz <= 0:
            raise ValueError(
                "La frecuencia medida debe ser positiva."
            )

        if (
            not math.isfinite(
                self.reflection_coefficient.real
            )
            or not math.isfinite(
                self.reflection_coefficient.imag
            )
        ):
            raise ValueError(
                "El coeficiente de reflexión debe ser finito."
            )

        _validate_finite(
            self.reference_impedance,
            "La impedancia de referencia",
        )

        if self.reference_impedance <= 0:
            raise ValueError(
                "La impedancia de referencia debe ser positiva."
            )

    @property
    def impedance(self) -> complex:
        """Impedancia calculada a partir de S11."""
        return reflection_coefficient_to_impedance(
            reflection_coefficient=(
                self.reflection_coefficient
            ),
            reference_impedance=(
                self.reference_impedance
            ),
        )

    @property
    def swr(self) -> float:
        """ROE calculada respecto de la impedancia de referencia."""
        return calculate_swr(
            impedance=self.impedance,
            reference_impedance=(
                self.reference_impedance
            ),
        )

@dataclass(frozen=True)
class MeasurementSweep:
    """Conjunto ordenado de mediciones S11."""

    points: tuple[MeasurementPoint, ...]

    def __post_init__(self) -> None:
        if not self.points:
            raise ValueError(
                "El barrido medido debe contener puntos."
            )

        previous_frequency = 0.0
        reference_impedance = (
            self.points[0].reference_impedance
        )

        for point in self.points:
            if point.frequency_mhz <= previous_frequency:
                raise ValueError(
                    "Las frecuencias medidas deben ser "
                    "estrictamente crecientes."
                )

            if not math.isclose(
                point.reference_impedance,
                reference_impedance,
                rel_tol=0.0,
                abs_tol=1e-12,
            ):
                raise ValueError(
                    "Todos los puntos deben utilizar la misma "
                    "impedancia de referencia."
                )

            previous_frequency = point.frequency_mhz

    @property
    def has_reactance_zero_crossing(self) -> bool:
        """Detecta cero exacto o cambio de signo entre impedancias finitas.

        Una impedancia no finita interrumpe la continuidad: no se infiere
        un cruce a través de un circuito abierto.
        """
        previous_reactance = None

        for point in self.points:
            impedance = point.impedance
            if not (
                math.isfinite(impedance.real)
                and math.isfinite(impedance.imag)
            ):
                previous_reactance = None
                continue

            current_reactance = impedance.imag

            if current_reactance == 0:
                return True

            if previous_reactance is not None and (
                previous_reactance < 0 < current_reactance
                or previous_reactance > 0 > current_reactance
            ):
                return True

            previous_reactance = current_reactance

        return False

    @property
    def minimum_swr_is_at_boundary(self) -> bool:
        """Indica si algún extremo alcanza la ROE mínima, incluidos empates.

        Un único punto es un extremo. Si todas las ROE son infinitas,
        ambos extremos empatan y el diagnóstico también es verdadero.
        """
        minimum = self.minimum_swr_point.swr

        return (
            minimum == self.points[0].swr
            or minimum == self.points[-1].swr
        )

    @property
    def reference_impedance(self) -> float:
        """Impedancia de referencia común del barrido."""
        return self.points[0].reference_impedance

    @property
    def start_frequency_mhz(self) -> float:
        """Primera frecuencia medida."""
        return self.points[0].frequency_mhz

    @property
    def stop_frequency_mhz(self) -> float:
        """Última frecuencia medida."""
        return self.points[-1].frequency_mhz

    @property
    def minimum_swr_point(self) -> MeasurementPoint:
        """Punto con menor ROE."""
        return min(
            self.points,
            key=lambda point: point.swr,
        )

    @property
    def resonance_point(self) -> MeasurementPoint | None:
        """Mínima reactancia absoluta entre impedancias finitas, o None.

        Los abiertos no son candidatos aunque su reactancia sea cero.
        Es una estimación muestreada; no demuestra un cruce por cero.
        """
        return min(
            (
                point for point in self.points
                if math.isfinite(point.impedance.real)
                and math.isfinite(point.impedance.imag)
            ),
            key=lambda point: abs(
                point.impedance.imag
            ),
            default=None,
        )


# ---------------------------------------------------------------------------
# Patrones de radiación (solo dominio; ningún motor los calcula todavía)
#
# Convención angular confirmada en
# docs/validation/radiation-patterns-4nec2.md: theta se mide desde +Z
# (0 = +Z, 90 = plano XY, 180 = -Z); phi se mide en el plano XY desde
# +X, en sentido antihorario visto desde +Z (90 = +Y). Los ejes son
# cartesianos: no se define ninguna orientación geográfica.
# ---------------------------------------------------------------------------

_THETA_MAX_FREE_SPACE_DEG = 180.0
_THETA_MAX_WITH_GROUND_DEG = 90.0
_PHI_MAX_DEG = 360.0


def _validate_real_number(value: object, name: str) -> None:
    """Comprueba que un valor sea un int o float finito, nunca un bool.

    A diferencia de ``_validate_finite``, rechaza explícitamente
    ``bool`` (subclase de ``int`` en Python) y cualquier otro tipo, sin
    intentar convertirlo.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} debe ser un número finito.")

    _validate_finite(value, name)


def _validate_angle_in_range(
    value: object,
    name: str,
    maximum_deg: float,
) -> None:
    """Comprueba que un ángulo sea finito y esté en 0..maximum_deg."""
    _validate_real_number(value, name)

    if not 0.0 <= value <= maximum_deg:  # type: ignore[operator]
        raise ValueError(
            f"{name} debe estar entre 0 y {maximum_deg:g} grados."
        )


def _validate_optional_gain(value: object, name: str) -> None:
    """Acepta ``None`` (nulo explícito) o una ganancia finita."""
    if value is None:
        return

    _validate_real_number(value, name)


@dataclass(frozen=True)
class AngularSweep:
    """Eje angular regular: ``count`` ángulos desde ``start_deg``.

    Los ángulos se expresan en grados y nunca se normalizan ni se
    envuelven (por ejemplo, 360 no se convierte en 0). ``count`` debe
    ser positivo: un conteo nulo o negativo se rechaza aquí porque,
    pasado a ``rp_card()`` de PyNEC, un conteo negativo provoca un
    ``segmentation fault`` del proceso
    (``docs/research/nec-radiation-patterns.md``, §1.6).
    """

    start_deg: float
    count: int
    step_deg: float

    def __post_init__(self) -> None:
        _validate_real_number(self.start_deg, "El ángulo inicial")
        _validate_real_number(self.step_deg, "El paso angular")

        if (
            not isinstance(self.count, int)
            or isinstance(self.count, bool)
            or self.count <= 0
        ):
            raise ValueError(
                "La cantidad de ángulos debe ser un entero positivo."
            )

        if self.step_deg < 0:
            raise ValueError(
                "El paso angular no puede ser negativo."
            )

        if self.count > 1 and self.step_deg == 0:
            raise ValueError(
                "El paso angular debe ser positivo cuando hay más "
                "de un ángulo."
            )

        _validate_finite(self.stop_deg, "El ángulo final")

    @property
    def stop_deg(self) -> float:
        """Último ángulo del eje."""
        return self.start_deg + (self.count - 1) * self.step_deg

    @property
    def angles_deg(self) -> tuple[float, ...]:
        """Todos los ángulos del eje, en orden creciente."""
        return tuple(
            self.start_deg + index * self.step_deg
            for index in range(self.count)
        )


@dataclass(frozen=True)
class RadiationPatternRequest:
    """Datos necesarios para calcular un patrón de radiación.

    El dominio angular seguro depende del entorno: ``0 <= theta <=
    180`` en espacio libre y ``0 <= theta <= 90`` con cualquier plano
    de tierra, porque con tierra ``theta > 90`` dio en PyNEC valores no
    reproducibles (``docs/research/nec-radiation-patterns.md``, §1.6).
    ``phi`` debe quedar en ``0..360``; 0 y 360 pueden coexistir.
    """

    wires: tuple[Wire, ...]
    environment: Environment
    source: VoltageSource
    frequency_mhz: float
    theta: AngularSweep
    phi: AngularSweep

    def __post_init__(self) -> None:
        # El tipo de entorno se comprueba antes que nada:
        # SimulationRequest trata cualquier entorno que no sea espacio
        # libre como un plano de tierra, y aquí el límite de theta
        # depende de identificarlo con exactitud.
        if isinstance(self.environment, FreeSpaceEnvironment):
            theta_max_deg = _THETA_MAX_FREE_SPACE_DEG
        elif isinstance(
            self.environment,
            (PerfectGroundEnvironment, RealGroundEnvironment),
        ):
            theta_max_deg = _THETA_MAX_WITH_GROUND_DEG
        else:
            raise ValueError(
                "Tipo de entorno desconocido para un patrón de "
                f"radiación: {self.environment!r}."
            )

        _validate_real_number(self.frequency_mhz, "La frecuencia")

        # SimulationRequest no comprueba el tipo de la fuente ni de los
        # conductores (produciría un AttributeError incidental), así
        # que aquí se rechazan antes de delegar. No se exige tuple para
        # wires: se conserva el mismo contrato que SimulationRequest.
        if not isinstance(self.source, VoltageSource):
            raise ValueError("La fuente debe ser un VoltageSource.")

        if self.wires and not all(
            isinstance(wire, Wire) for wire in self.wires
        ):
            raise ValueError("Todos los conductores deben ser Wire.")

        # Reutiliza las validaciones de frecuencia, conductores,
        # fuente y plano de tierra, igual que SweepRequest.
        SimulationRequest(
            frequency_mhz=self.frequency_mhz,
            wires=self.wires,
            source=self.source,
            environment=self.environment,
        )

        if not isinstance(self.theta, AngularSweep):
            raise ValueError("theta debe ser un AngularSweep.")

        if not isinstance(self.phi, AngularSweep):
            raise ValueError("phi debe ser un AngularSweep.")

        if self.theta.start_deg < 0:
            raise ValueError(
                "El ángulo theta inicial no puede ser negativo."
            )

        if self.theta.stop_deg > theta_max_deg:
            if theta_max_deg == _THETA_MAX_WITH_GROUND_DEG:
                raise ValueError(
                    "Con un plano de tierra, el ángulo theta final no "
                    "puede superar 90 grados."
                )

            raise ValueError(
                "El ángulo theta final no puede superar 180 grados."
            )

        if self.phi.start_deg < 0:
            raise ValueError(
                "El ángulo phi inicial no puede ser negativo."
            )

        if self.phi.stop_deg > _PHI_MAX_DEG:
            raise ValueError(
                "El ángulo phi final no puede superar 360 grados."
            )


@dataclass(frozen=True)
class RadiationPatternSample:
    """Ganancia total en una dirección (theta, phi).

    ``gain_db`` numérico es una ganancia total válida en dBi.
    ``gain_db=None`` representa un nulo o un valor no representable
    reportado por NEC (por ejemplo, el centinela ``-999.99``). Esta
    clase no traduce el centinela: esa conversión corresponde al
    adaptador del motor.
    """

    theta_deg: float
    phi_deg: float
    gain_db: float | None

    def __post_init__(self) -> None:
        _validate_angle_in_range(
            self.theta_deg,
            "El ángulo theta",
            _THETA_MAX_FREE_SPACE_DEG,
        )
        _validate_angle_in_range(
            self.phi_deg,
            "El ángulo phi",
            _PHI_MAX_DEG,
        )
        _validate_optional_gain(self.gain_db, "La ganancia")


@dataclass(frozen=True)
class RadiationPatternResult:
    """Patrón de radiación completo a una frecuencia.

    Contrato de orientación: ``gain_db[theta_index][phi_index]``, con
    forma lógica ``(n_theta, n_phi)`` (el primer eje es theta, el
    segundo es phi), igual que ``get_gain()`` de PyNEC. ``None`` en
    la matriz representa un nulo explícito (ver
    ``RadiationPatternSample``).
    """

    frequency_mhz: float
    theta_angles_deg: tuple[float, ...]
    phi_angles_deg: tuple[float, ...]
    gain_db: tuple[tuple[float | None, ...], ...]

    def __post_init__(self) -> None:
        _validate_real_number(self.frequency_mhz, "La frecuencia")

        if self.frequency_mhz <= 0:
            raise ValueError(
                "La frecuencia debe ser positiva."
            )

        for angles, name, maximum_deg in (
            (
                self.theta_angles_deg,
                "theta",
                _THETA_MAX_FREE_SPACE_DEG,
            ),
            (
                self.phi_angles_deg,
                "phi",
                _PHI_MAX_DEG,
            ),
        ):
            if not isinstance(angles, tuple) or not angles:
                raise ValueError(
                    f"Los ángulos {name} deben ser una tupla no vacía."
                )

            for angle in angles:
                _validate_angle_in_range(
                    angle,
                    f"El ángulo {name}",
                    maximum_deg,
                )

        if (
            not isinstance(self.gain_db, tuple)
            or len(self.gain_db) != len(self.theta_angles_deg)
        ):
            raise ValueError(
                "La matriz de ganancia debe ser una tupla con una "
                "fila por cada ángulo theta."
            )

        for row in self.gain_db:
            if (
                not isinstance(row, tuple)
                or len(row) != len(self.phi_angles_deg)
            ):
                raise ValueError(
                    "Cada fila de la matriz de ganancia debe ser una "
                    "tupla con una columna por cada ángulo phi."
                )

            for gain in row:
                _validate_optional_gain(gain, "La ganancia")

    @property
    def n_theta(self) -> int:
        """Cantidad de ángulos theta (filas de la matriz)."""
        return len(self.theta_angles_deg)

    @property
    def n_phi(self) -> int:
        """Cantidad de ángulos phi (columnas de la matriz)."""
        return len(self.phi_angles_deg)

    @property
    def shape(self) -> tuple[int, int]:
        """Forma lógica de la matriz: ``(n_theta, n_phi)``."""
        return (self.n_theta, self.n_phi)

    @property
    def samples(self) -> tuple[RadiationPatternSample, ...]:
        """Todas las muestras: theta en el lazo externo, phi en el interno."""
        return tuple(
            RadiationPatternSample(
                theta_deg=theta,
                phi_deg=phi,
                gain_db=self.gain_db[theta_index][phi_index],
            )
            for theta_index, theta in enumerate(self.theta_angles_deg)
            for phi_index, phi in enumerate(self.phi_angles_deg)
        )
