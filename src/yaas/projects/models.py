"""Modelos de proyecto del simulador."""

import math
from dataclasses import dataclass

from yaas.domain import (
    AngularSweep,
    Environment,
    FreeSpaceEnvironment,
    RadiationPatternRequest,
    SimulationRequest,
    SweepRequest,
    VoltageSource,
    Wire,
)


CURRENT_SCHEMA_VERSION = 4

# Versiones que el lector y el modelo aceptan explícitamente. La
# versión 1 no contiene simulation.environment (se interpreta siempre
# como FreeSpaceEnvironment). Las versiones 2, 3 y 4 lo exigen; la
# versión 2 admite únicamente free_space/perfect_ground, mientras que
# la versión 3 agrega real_ground (ver
# docs/research/nec-real-ground.md). La versión 4 admite los mismos
# entornos que la 3 y agrega simulation.radiation_pattern, opcional.
# Cualquier otra versión (0, 5, ...) se rechaza explícitamente, nunca
# en silencio.
SUPPORTED_SCHEMA_VERSIONS = (1, 2, 3, 4)


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
class RadiationPatternSettings:
    """Configuración persistente de un patrón de radiación.

    Solo declara los ejes angulares: el patrón usa la frecuencia
    puntual y el entorno del proyecto. Las reglas numéricas de cada eje
    las valida ``AngularSweep``; las que dependen del entorno (por
    ejemplo, ``theta <= 90`` con tierra), ``RadiationPatternRequest``.
    """

    theta: AngularSweep
    phi: AngularSweep

    def __post_init__(self) -> None:
        if not isinstance(self.theta, AngularSweep):
            raise ValueError("theta debe ser un AngularSweep.")

        if not isinstance(self.phi, AngularSweep):
            raise ValueError("phi debe ser un AngularSweep.")


@dataclass(frozen=True)
class AntennaProject:
    """Proyecto completo de una antena."""

    metadata: ProjectMetadata
    wires: tuple[Wire, ...]
    source: VoltageSource
    frequency_mhz: float
    reference_impedance: float
    sweep: SweepSettings
    environment: Environment = FreeSpaceEnvironment()
    schema_version: int = CURRENT_SCHEMA_VERSION
    radiation_pattern: RadiationPatternSettings | None = None

    def __post_init__(self) -> None:
        if self.schema_version not in SUPPORTED_SCHEMA_VERSIONS:
            raise ValueError(
                "Versión de esquema no soportada: "
                f"{self.schema_version}."
            )

        # Reutiliza las validaciones del dominio.
        self.to_simulation_request()
        self.to_sweep_request()

        if self.radiation_pattern is not None:
            # Rechaza al construir el proyecto (y por lo tanto al
            # cargar un archivo) un patrón incoherente con el entorno,
            # en vez de recién al simular.
            self.to_radiation_pattern_request()

    def to_simulation_request(self) -> SimulationRequest:
        """Convierte el proyecto en una simulación simple."""
        return SimulationRequest(
            frequency_mhz=self.frequency_mhz,
            wires=self.wires,
            source=self.source,
            reference_impedance=self.reference_impedance,
            environment=self.environment,
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
            environment=self.environment,
        )

    def to_radiation_pattern_request(self) -> RadiationPatternRequest:
        """Convierte el proyecto en una solicitud de patrón de radiación.

        Usa la frecuencia puntual, los conductores, la fuente y el
        entorno del proyecto, con los ejes de ``radiation_pattern``.

        Raises:
            ValueError: Si el proyecto no define un patrón de radiación.
        """
        if self.radiation_pattern is None:
            raise ValueError(
                "El proyecto no define un patrón de radiación."
            )

        return RadiationPatternRequest(
            wires=self.wires,
            environment=self.environment,
            source=self.source,
            frequency_mhz=self.frequency_mhz,
            theta=self.radiation_pattern.theta,
            phi=self.radiation_pattern.phi,
        )