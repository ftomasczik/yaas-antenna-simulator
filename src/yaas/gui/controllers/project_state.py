"""Estado inmutable de presentación de un proyecto abierto.

Contiene únicamente datos semánticos tomados del proyecto (números,
objetos del dominio), nunca textos visibles ni objetos Qt: las
etiquetas las arma la vista (ver `yaas.gui.texts`). Este módulo no
importa Qt.
"""

from dataclasses import dataclass
from pathlib import Path

from yaas.application import OpenedProject
from yaas.domain import (
    AngularSweep,
    Environment,
    FreeSpaceEnvironment,
    PerfectGroundEnvironment,
    RealGroundEnvironment,
)

_ENVIRONMENT_TYPES = (
    FreeSpaceEnvironment,
    PerfectGroundEnvironment,
    RealGroundEnvironment,
)


@dataclass(frozen=True)
class ProjectViewState:
    """Lo que la GUI muestra de un proyecto abierto.

    ``theta`` y ``phi`` son los ejes del patrón tal como los define el
    proyecto (theta es el ángulo polar de NEC, nunca una elevación);
    ambos son None cuando el proyecto no define un patrón.
    """

    path: Path
    name: str
    schema_version: int
    conductor_count: int
    frequency_mhz: float
    reference_impedance_ohm: float
    environment: Environment
    has_sweep: bool
    theta: AngularSweep | None
    phi: AngularSweep | None

    def __post_init__(self) -> None:
        if not isinstance(self.path, Path):
            raise TypeError("path debe ser un pathlib.Path.")

        if not isinstance(self.environment, _ENVIRONMENT_TYPES):
            raise TypeError("environment debe ser un entorno del dominio.")

        if (self.theta is None) != (self.phi is None):
            raise ValueError(
                "theta y phi deben estar ambos presentes o ambos ausentes."
            )

    @property
    def has_radiation_pattern(self) -> bool:
        return self.theta is not None

    @classmethod
    def from_opened_project(cls, opened: OpenedProject) -> "ProjectViewState":
        project = opened.project
        pattern = project.radiation_pattern
        return cls(
            path=opened.path,
            name=project.metadata.name,
            schema_version=project.schema_version,
            conductor_count=len(project.wires),
            frequency_mhz=project.frequency_mhz,
            reference_impedance_ohm=project.reference_impedance,
            environment=project.environment,
            # El esquema exige un barrido en todas las versiones; se
            # informa igual explícitamente en vez de suponerlo en la vista.
            has_sweep=project.sweep is not None,
            theta=None if pattern is None else pattern.theta,
            phi=None if pattern is None else pattern.phi,
        )
