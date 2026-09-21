"""Escritura de proyectos AntSim."""

import json
from pathlib import Path
from typing import Any

from antsim.projects.models import AntennaProject


def project_to_dict(
    project: AntennaProject,
) -> dict[str, Any]:
    """Convierte un proyecto a su representación serializable."""
    return {
        "schema_version": project.schema_version,
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
