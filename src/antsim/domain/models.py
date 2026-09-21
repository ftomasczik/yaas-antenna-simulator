"""Modelos fundamentales del simulador."""

import math
from dataclasses import dataclass


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
class SimulationRequest:
    """Datos necesarios para ejecutar una simulación básica."""

    frequency_mhz: float
    wires: tuple[Wire, ...]
    source: VoltageSource
    reference_impedance: float = 50.0

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

        # Reutiliza las validaciones de conductores, fuente
        # e impedancia de referencia.
        SimulationRequest(
            frequency_mhz=self.start_frequency_mhz,
            wires=self.wires,
            source=self.source,
            reference_impedance=self.reference_impedance,
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
class SweepResult:
    """Resultado completo de un barrido de frecuencia."""

    points: tuple[SweepPoint, ...]

    def __post_init__(self) -> None:
        if not self.points:
            raise ValueError(
                "El barrido debe contener resultados."
            )

    @property
    def resonance_point(self) -> SweepPoint:
        """Punto cuya reactancia está más próxima a cero."""
        return min(
            self.points,
            key=lambda point: abs(point.impedance.imag),
        )

    @property
    def minimum_swr_point(self) -> SweepPoint:
        """Punto con la menor ROE del barrido."""
        return min(
            self.points,
            key=lambda point: point.swr,
        )