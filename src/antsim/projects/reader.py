"""Lectura de proyectos AntSim."""

import json
import math
from pathlib import Path
from typing import Any

from antsim.domain import (
    Point3D,
    VoltageSource,
    Wire,
)
from antsim.projects.errors import ProjectFormatError
from antsim.projects.models import (
    CURRENT_SCHEMA_VERSION,
    AntennaProject,
    ProjectMetadata,
    SweepSettings,
)


def _validate_fields(
    data: Any,
    context: str,
    required: dict[str, type],
    optional: dict[str, type] | None = None,
) -> None:
    """Valida tipos JSON antes de construir objetos del dominio."""
    if not isinstance(data, dict):
        raise ProjectFormatError(f"{context}: se esperaba un objeto JSON.")

    for name, expected in {**required, **(optional or {})}.items():
        field = f"{context}.{name}" if context != "raíz" else name
        if name not in data:
            if name in required:
                raise ProjectFormatError(f"{field}: falta el campo obligatorio.")
            continue
        value = data[name]
        if expected is float:
            valid = type(value) in (int, float)
            if valid:
                try:
                    valid = math.isfinite(value)
                except OverflowError:
                    valid = False
            description = "un número finito"
        else:
            valid = type(value) is expected
            description = {
                str: "texto", int: "un entero", dict: "un objeto JSON",
                list: "una lista",
            }[expected]
        if not valid:
            raise ProjectFormatError(f"{field}: se esperaba {description}.")


def _validate_structure(data: Any) -> None:
    """Comprueba la estructura del esquema 1 sin coerciones de tipos."""
    _validate_fields(data, "raíz", {
        "schema_version": int, "project": dict, "geometry": dict,
        "source": dict, "simulation": dict,
    })
    if data["schema_version"] != CURRENT_SCHEMA_VERSION:
        raise ProjectFormatError(
            f"schema_version: versión no soportada: {data['schema_version']}."
        )
    _validate_fields(data["project"], "project", {"name": str}, {"description": str})
    _validate_fields(data["geometry"], "geometry", {"wires": list})
    for index, wire in enumerate(data["geometry"]["wires"]):
        context = f"geometry.wires[{index}]"
        _validate_fields(wire, context, {
            "tag": int, "start_m": list, "end_m": list,
            "radius_m": float, "segments": int,
        })
        for endpoint in ("start_m", "end_m"):
            coordinates = wire[endpoint]
            if len(coordinates) != 3:
                raise ProjectFormatError(
                    f"{context}.{endpoint}: se esperaban tres coordenadas."
                )
            for axis, value in enumerate(coordinates):
                _validate_fields(
                    {str(axis): value}, f"{context}.{endpoint}", {str(axis): float}
                )
    _validate_fields(data["source"], "source", {
        "type": str, "wire_tag": int, "segment": int,
        "voltage_real": float, "voltage_imag": float,
    })
    _validate_fields(data["simulation"], "simulation", {
        "frequency_mhz": float, "reference_impedance_ohm": float, "sweep": dict,
    })
    _validate_fields(data["simulation"]["sweep"], "simulation.sweep", {
        "start_mhz": float, "stop_mhz": float, "points": int,
    }, {"swr_limit": float})


def project_from_dict(
    data: dict[str, Any],
) -> AntennaProject:
    """Convierte un diccionario en un proyecto validado.

    Raises:
        ProjectFormatError: Si falta un campo, un tipo es inválido
        o el proyecto no supera las validaciones.
    """
    _validate_structure(data)
    try:
        schema_version = data["schema_version"]

        project_data = data["project"]
        geometry_data = data["geometry"]
        source_data = data["source"]
        simulation_data = data["simulation"]
        sweep_data = simulation_data["sweep"]

        if source_data["type"] != "voltage":
            raise ProjectFormatError(
                "source.type: sólo se admiten fuentes de tipo voltage."
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
        OverflowError,
    ) as error:
        raise ProjectFormatError(
            f"El proyecto no es válido: {error}"
        ) from error


def load_project(
    source: str | Path,
) -> AntennaProject:
    """Carga y valida un archivo `.antsim`.

    Raises:
        ProjectFormatError: Si la extensión, codificación, JSON o proyecto
            no son válidos. Incluye el archivo y el contexto del error.
        OSError: Si el archivo no puede abrirse.
    """
    input_path = Path(source)

    if input_path.suffix.lower() != ".antsim":
        raise ProjectFormatError(
            f"{input_path}: el archivo del proyecto debe utilizar "
            "la extensión .antsim."
        )

    try:
        with input_path.open(encoding="utf-8") as project_file:
            data = json.load(project_file)
        return project_from_dict(data)
    except json.JSONDecodeError as error:
        raise ProjectFormatError(
            f"{input_path}: JSON inválido en línea {error.lineno}, "
            f"columna {error.colno}: {error.msg}."
        ) from error
    except UnicodeError as error:
        raise ProjectFormatError(
            f"{input_path}: codificación UTF-8 inválida: {error}."
        ) from error
    except (ValueError, RecursionError) as error:
        # Incluye ProjectFormatError y límites del decodificador JSON.
        raise ProjectFormatError(f"{input_path}: {error}") from error
