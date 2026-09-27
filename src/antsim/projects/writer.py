"""Escritura de proyectos AntSim."""

import json
from pathlib import Path
from typing import Any

from antsim.domain import FreeSpaceEnvironment, PerfectGroundEnvironment
from antsim.projects.models import CURRENT_SCHEMA_VERSION, AntennaProject


def _environment_to_dict(environment: Any) -> dict[str, Any]:
    """Serializa un Environment de dominio a su forma exacta (schema 2).

    Selección exhaustiva por tipo: un tipo de entorno no reconocido
    produce un error claro, nunca una caída silenciosa a espacio
    libre (por ejemplo, si en el futuro se agrega un nuevo tipo de
    entorno al dominio sin actualizar este escritor).
    """
    if isinstance(environment, FreeSpaceEnvironment):
        return {"kind": "free_space"}

    if isinstance(environment, PerfectGroundEnvironment):
        return {"kind": "perfect_ground"}

    raise ValueError(
        f"No se sabe serializar este tipo de entorno: {environment!r}."
    )


def project_to_dict(
    project: AntennaProject,
) -> dict[str, Any]:
    """Convierte un proyecto a su representación serializable.

    Siempre escribe schema_version=2 y siempre incluye
    simulation.environment, sin importar con qué schema_version se
    haya construido `project` en memoria (por ejemplo, uno recién
    leído de un archivo v1): un proyecto v1 leído y vuelto a guardar
    queda migrado a v2. No se modifica `project` (es un dataclass
    inmutable); esta función solo lee sus campos.
    """
    return {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "project": {
            "name": project.metadata.name,
            "description": project.metadata.description,
        },
        "geometry": {
            "wires": [
                {
                    "tag": wire.tag,
                    "start_m": [
                        wire.start.x,
                        wire.start.y,
                        wire.start.z,
                    ],
                    "end_m": [
                        wire.end.x,
                        wire.end.y,
                        wire.end.z,
                    ],
                    "radius_m": wire.radius_m,
                    "segments": wire.segments,
                }
                for wire in project.wires
            ]
        },
        "source": {
            "type": "voltage",
            "wire_tag": project.source.wire_tag,
            "segment": project.source.segment,
            "voltage_real": project.source.voltage.real,
            "voltage_imag": project.source.voltage.imag,
        },
        "simulation": {
            "frequency_mhz": project.frequency_mhz,
            "reference_impedance_ohm": (
                project.reference_impedance
            ),
            "environment": _environment_to_dict(
                project.environment
            ),
            "sweep": {
                "start_mhz": (
                    project.sweep.start_frequency_mhz
                ),
                "stop_mhz": (
                    project.sweep.stop_frequency_mhz
                ),
                "points": project.sweep.points,
                "swr_limit": project.sweep.swr_limit,
            },
        },
    }


def save_project(
    project: AntennaProject,
    destination: str | Path,
) -> Path:
    """Guarda un proyecto como JSON con extensión `.antsim`.

    Args:
        project: Proyecto que se desea guardar.
        destination: Archivo de salida.

    Returns:
        Ruta del archivo creado.

    Raises:
        ValueError: Si el archivo no utiliza `.antsim`.
    """
    output_path = Path(destination)

    if output_path.suffix.lower() != ".antsim":
        raise ValueError(
            "El archivo del proyecto debe utilizar "
            "la extensión .antsim."
        )

    data = project_to_dict(project)

    with output_path.open(
        mode="w",
        encoding="utf-8",
        newline="\n",
    ) as project_file:
        json.dump(
            data,
            project_file,
            ensure_ascii=False,
            indent=2,
        )

        # Termina el archivo con una nueva línea.
        project_file.write("\n")

    return output_path
