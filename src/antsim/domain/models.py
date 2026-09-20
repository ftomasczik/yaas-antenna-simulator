"""Modelos fundamentales del simulador."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Point3D:
    """Punto tridimensional expresado en metros."""

    x: float
    y: float
    z: float


@dataclass(frozen=True)
class Wire:
    """Conductor recto representado mediante segmentos NEC."""

    tag: int
    start: Point3D
    end: Point3D
    radius_m: float
    segments: int


@dataclass(frozen=True)
class VoltageSource:
    """Fuente de tensión aplicada a un segmento."""

    wire_tag: int
    segment: int
    voltage: complex = complex(1.0, 0.0)


@dataclass(frozen=True)
class SimulationRequest:
    """Datos necesarios para ejecutar una simulación básica."""

    frequency_mhz: float
    wires: tuple[Wire, ...]
    source: VoltageSource
    reference_impedance: float = 50.0


@dataclass(frozen=True)
class SimulationResult:
    """Resultado básico normalizado de una simulación."""

    frequency_mhz: float
    impedance: complex
    swr: float