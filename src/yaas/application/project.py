"""Caso de uso: abrir un proyecto `.yaas` existente.

Este módulo solo delega en `yaas.projects.load_project`: no lee JSON por
su cuenta, no migra ni guarda el proyecto y no traduce mensajes. No
conoce ninguna interfaz ni motor de simulación, para reutilizarse desde
la CLI y desde la interfaz gráfica.
"""

from dataclasses import dataclass
from pathlib import Path

from yaas.projects import AntennaProject, load_project


@dataclass(frozen=True)
class OpenedProject:
    """Un proyecto cargado junto con la ruta desde la que se abrió.

    ``project`` es exactamente la instancia que devolvió
    `load_project`: conserva su ``schema_version`` original (por
    ejemplo, 1 para un archivo de esquema 1), aunque el escritor
    emitiría la versión actual si se guardara.
    """

    path: Path
    project: AntennaProject

    def __post_init__(self) -> None:
        if not isinstance(self.path, Path):
            raise TypeError("path debe ser un pathlib.Path.")

        if not isinstance(self.project, AntennaProject):
            raise TypeError("project debe ser un AntennaProject.")


def open_project(path: str | Path) -> OpenedProject:
    """Abre un archivo `.yaas` sin modificarlo.

    La ruta se convierte a `Path` tal como se recibe (sin resolverla ni
    volverla absoluta), igual que hace `load_project`.

    Raises:
        ProjectFormatError: Si la extensión, la codificación, el JSON o
            el proyecto no son válidos.
        OSError: Si el archivo no puede abrirse (por ejemplo, porque no
            existe).
    """
    project_path = Path(path)
    return OpenedProject(path=project_path, project=load_project(project_path))
