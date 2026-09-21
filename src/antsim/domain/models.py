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