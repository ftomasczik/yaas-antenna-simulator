"""Modelos fundamentales del simulador."""

import math
from dataclasses import dataclass

from antsim.domain.calculations import (
    calculate_swr,
    reflection_coefficient_to_impedance,
)


def _validate_finite(value: float, name: str) -> None:
    """Comprueba que un valor numérico sea finito."""
    if not math.isfinite(value):
        raise ValueError(f"{name} debe ser un número finito.")


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
    """Sin plano de tierra: comportamiento actual de AntSim."""


@dataclass(frozen=True)
class PerfectGroundEnvironment:
    """Plano de tierra perfectamente conductor en z=0."""


# Tierra real (con pérdidas, aproximación de Fresnel/Sommerfeld) queda
# postergada: ni el motor de simulación ni el esquema de proyecto la
# soportan todavía (ver docs/research/nec-ground-configuration.md).
Environment = FreeSpaceEnvironment | PerfectGroundEnvironment


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
