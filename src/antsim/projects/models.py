"""Modelos de proyecto del simulador."""

import math
from dataclasses import dataclass

from antsim.domain import (
    SimulationRequest,
    SweepRequest,
    VoltageSource,
    Wire,
)


CURRENT_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ProjectMetadata:
    """Información descriptiva del proyecto."""

    name: str
    description: str = ""

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError(
                "El proyecto debe tener un nombre."
            )


@dataclass(frozen=True)
class SweepSettings:
    """Configuración persistente de un barrido."""

    start_frequency_mhz: float
    stop_frequency_mhz: float
    points: int
    swr_limit: float = 2.0

    def __post_init__(self) -> None:
        if not math.isfinite(self.start_frequency_mhz):
            raise ValueError(
                "La frecuencia inicial debe ser finita."
            )

        if not math.isfinite(self.stop_frequency_mhz):
            raise ValueError(
                "La frecuencia final debe ser finita."
            )

        if self.start_frequency_mhz <= 0:
            raise ValueError(
                "La frecuencia inicial debe ser positiva."
            )

        if (
            self.stop_frequency_mhz
            <= self.start_frequency_mhz
        ):
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

        if (
            not math.isfinite(self.swr_limit)
            or self.swr_limit < 1.0
        ):
            raise ValueError(
                "El límite de ROE debe ser finito "
                "y mayor o igual a 1."
            )


@dataclass(frozen=True)
class AntennaProject:
    """Proyecto completo de una antena."""

    metadata: ProjectMetadata
    wires: tuple[Wire, ...]
    source: VoltageSource
    frequency_mhz: float
    reference_impedance: float
    sweep: SweepSettings
    schema_version: int = CURRENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != CURRENT_SCHEMA_VERSION:
            raise ValueError(
                "Versión de esquema no soportada: "
                f"{self.schema_version}."
            )

        # Reutiliza las validaciones del dominio.
        self.to_simulation_request()
        self.to_sweep_request()

    def to_simulation_request(self) -> SimulationRequest:
        """Convierte el proyecto en una simulación simple."""
        return SimulationRequest(
            frequency_mhz=self.frequency_mhz,
            wires=self.wires,
            source=self.source,
            reference_impedance=self.reference_impedance,
        )

    def to_sweep_request(self) -> SweepRequest:
        """Convierte el proyecto en una solicitud de barrido."""
        return SweepRequest(
            start_frequency_mhz=(
                self.sweep.start_frequency_mhz
            ),
            stop_frequency_mhz=(
                self.sweep.stop_frequency_mhz
            ),
            points=self.sweep.points,
            wires=self.wires,
            source=self.source,
            reference_impedance=self.reference_impedance,
        )