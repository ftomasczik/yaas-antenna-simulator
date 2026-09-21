"""Lectura de proyectos AntSim."""

import json
from pathlib import Path
from typing import Any

from antsim.domain import (
    Point3D,
    VoltageSource,
    Wire,
)
from antsim.projects.errors import ProjectFormatError
from antsim.projects.models import (
    AntennaProject,
    ProjectMetadata,
    SweepSettings,
)


def project_from_dict(
    data: dict[str, Any],
) -> AntennaProject:
    """Convierte un diccionario en un proyecto validado.

    Raises:
        ProjectFormatError: Si falta un campo, un tipo es inválido
        o el proyecto no supera las validaciones.
    """
    try:
        schema_version = data["schema_version"]

        project_data = data["project"]
        geometry_data = data["geometry"]
        source_data = data["source"]
        simulation_data = data["simulation"]
        sweep_data = simulation_data["sweep"]

        if source_data["type"] != "voltage":
            raise ProjectFormatError(
                "Sólo se admiten fuentes de tipo voltage."
            )

        wires = tuple(
            Wire(
                tag=wire_data["tag"],
                start=Point3D(
                    *wire_data["start_m"]
                ),
                end=Point3D(
                    *wire_data["end_m"]
                ),
                radius_m=wire_data["radius_m"],
                segments=wire_data["segments"],
            )
            for wire_data in geometry_data["wires"]
        )

        voltage = complex(
            source_data["voltage_real"],
            source_data["voltage_imag"],
        )

        return AntennaProject(
            metadata=ProjectMetadata(
                name=project_data["name"],
                description=project_data.get(
                    "description",
                    "",
                ),
            ),
            wires=wires,
            source=VoltageSource(
                wire_tag=source_data["wire_tag"],
                segment=source_data["segment"],
                voltage=voltage,
            ),
            frequency_mhz=(
                simulation_data["frequency_mhz"]
            ),
            reference_impedance=(
                simulation_data[
                    "reference_impedance_ohm"
                ]
            ),
            sweep=SweepSettings(
                start_frequency_mhz=(
                    sweep_data["start_mhz"]
                ),
                stop_frequency_mhz=(
                    sweep_data["stop_mhz"]
                ),
                points=sweep_data["points"],
                swr_limit=sweep_data.get(
                    "swr_limit",
                    2.0,
                ),
            ),
            schema_version=schema_version,
        )

    except ProjectFormatError:
        raise

    except (
        KeyError,
        TypeError,
        ValueError,
        IndexError,
    ) as error:
        raise ProjectFormatError(
            f"El proyecto no es válido: {error}"
        ) from error


def load_project(
    source: str | Path,
) -> AntennaProject:
    """Carga y valida un archivo `.antsim`.

    Raises:
        ValueError: Si la extensión no es `.antsim`.
        ProjectFormatError: Si el JSON o el proyecto no son válidos.
        OSError: Si el archivo no puede abrirse.
    """
    input_path = Path(source)

    if input_path.suffix.lower() != ".antsim":
        raise ValueError(
            "El archivo del proyecto debe utilizar "
            "la extensión .antsim."
        )

    try:
        with input_path.open(encoding="utf-8") as project_file:
            data = json.load(project_file)
    except json.JSONDecodeError as error:
        raise ProjectFormatError(
            "El archivo no contiene JSON válido: "
            f"{error.msg}."
        ) from error

    if not isinstance(data, dict):
        raise ProjectFormatError(
            "La raíz del proyecto debe ser un objeto JSON."
        )

    return project_from_dict(data)
