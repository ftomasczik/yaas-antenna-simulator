"""Lectura de proyectos YAAS."""

import json
import math
from pathlib import Path
from typing import Any

from yaas.domain import (
    Environment,
    FreeSpaceEnvironment,
    PerfectGroundEnvironment,
    Point3D,
    RealGroundEnvironment,
    RealGroundModel,
    VoltageSource,
    Wire,
)
from yaas.projects.errors import ProjectFormatError
from yaas.projects.models import (
    SUPPORTED_SCHEMA_VERSIONS,
    AntennaProject,
    ProjectMetadata,
    SweepSettings,
)

# Campos adicionales (más allá de "kind") que exige cada valor de
# "kind" en simulation.environment, con su tipo JSON esperado.
# free_space y perfect_ground no declaran ningún campo adicional;
# real_ground exige permitividad, conductividad y el método.
_ENVIRONMENT_EXTRA_FIELDS: dict[str, dict[str, type]] = {
    "free_space": {},
    "perfect_ground": {},
    "real_ground": {
        "model": str,
        "relative_permittivity": float,
        "conductivity_s_per_m": float,
    },
}

# "kind" admitidos según schema_version: real_ground solo existe
# desde la versión 3 (ver docs/research/nec-real-ground.md); en la
# versión 2 sigue rechazado, exactamente como antes.
_ENVIRONMENT_KINDS_BY_SCHEMA: dict[int, frozenset[str]] = {
    2: frozenset({"free_space", "perfect_ground"}),
    3: frozenset({"free_space", "perfect_ground", "real_ground"}),
}

# Valores admitidos para simulation.environment.model (solo aplica a
# "real_ground") y su enum de dominio correspondiente.
_REAL_GROUND_MODELS = {
    "sommerfeld_norton": RealGroundModel.SOMMERFELD_NORTON,
}


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


def _validate_environment_value(
    data: dict,
    context: str,
    schema_version: int,
) -> None:
    """Valida el contenido exacto de simulation.environment.

    Ya se garantizó (vía ``_validate_fields``) que ``data`` es un
    objeto JSON. ``schema_version`` determina qué valores de ``kind``
    se admiten: ``real_ground`` solo existe desde la versión 3 (en la
    versión 2 se rechaza igual que cualquier otro ``kind``
    desconocido). Según el ``kind``, se valida su forma exacta: sin
    claves adicionales, sin campos faltantes, y (para ``real_ground``)
    un ``model`` reconocido.
    """
    if "kind" not in data:
        raise ProjectFormatError(
            f"{context}.kind: falta el campo obligatorio."
        )

    kind = data["kind"]
    allowed_kinds = _ENVIRONMENT_KINDS_BY_SCHEMA[schema_version]
    if type(kind) is not str or kind not in allowed_kinds:
        raise ProjectFormatError(
            f"{context}.kind: valor no soportado: {kind!r}."
        )

    extra_fields = _ENVIRONMENT_EXTRA_FIELDS[kind]
    allowed_keys = {"kind", *extra_fields}
    extra_keys = sorted(set(data) - allowed_keys)
    if extra_keys:
        raise ProjectFormatError(
            f"{context}: no se admiten claves adicionales "
            f"({', '.join(extra_keys)})."
        )

    _validate_fields(data, context, extra_fields)

    if kind == "real_ground" and data["model"] not in _REAL_GROUND_MODELS:
        raise ProjectFormatError(
            f"{context}.model: valor no soportado: {data['model']!r}."
        )


def _environment_from_dict(data: dict) -> Environment:
    """Construye un ``Environment`` ya validado por ``_validate_environment_value``.

    Para ``real_ground``, cualquier ``ValueError`` que levante
    ``RealGroundEnvironment.__post_init__`` (permitividad no positiva,
    conductividad negativa, valores no finitos) se propaga tal cual:
    ``project_from_dict`` ya traduce cualquier ``ValueError`` de este
    tipo a ``ProjectFormatError``, el mismo mecanismo ya usado para el
    resto de las validaciones de dominio (conductores, fuente, etc.).
    """
    kind = data["kind"]

    if kind == "free_space":
        return FreeSpaceEnvironment()

    if kind == "perfect_ground":
        return PerfectGroundEnvironment()

    return RealGroundEnvironment(
        relative_permittivity=data["relative_permittivity"],
        conductivity_s_per_m=data["conductivity_s_per_m"],
        model=_REAL_GROUND_MODELS[data["model"]],
    )


def _validate_structure(data: Any) -> None:
    """Comprueba la estructura del esquema (1, 2 o 3) sin coerciones de tipos."""
    _validate_fields(data, "raíz", {
        "schema_version": int, "project": dict, "geometry": dict,
        "source": dict, "simulation": dict,
    })

    schema_version = data["schema_version"]
    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        raise ProjectFormatError(
            f"schema_version: versión no soportada: {schema_version}."
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

    if schema_version == 1:
        _validate_fields(data["simulation"], "simulation", {
            "frequency_mhz": float, "reference_impedance_ohm": float, "sweep": dict,
        })
        if "environment" in data["simulation"]:
            raise ProjectFormatError(
                "simulation.environment: no se admite en "
                "schema_version=1."
            )
    else:
        # schema_version 2 o 3 (las únicas otras opciones ya
        # admitidas arriba): ambas exigen simulation.environment.
        _validate_fields(data["simulation"], "simulation", {
            "frequency_mhz": float, "reference_impedance_ohm": float,
            "environment": dict, "sweep": dict,
        })
        _validate_environment_value(
            data["simulation"]["environment"],
            "simulation.environment",
            schema_version,
        )

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

        if schema_version == 1:
            # v1 no contiene simulation.environment: se interpreta
            # siempre como espacio libre (ver _validate_structure,
            # que ya rechazó cualquier environment presente en v1).
            environment = FreeSpaceEnvironment()
        else:
            environment = _environment_from_dict(
                simulation_data["environment"]
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
            environment=environment,
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
    """Carga y valida un archivo `.yaas`.

    Raises:
        ProjectFormatError: Si la extensión, codificación, JSON o proyecto
            no son válidos. Incluye el archivo y el contexto del error.
        OSError: Si el archivo no puede abrirse.
    """
    input_path = Path(source)

    if input_path.suffix.lower() != ".yaas":
        raise ProjectFormatError(
            f"{input_path}: el archivo del proyecto debe utilizar "
            "la extensión .yaas."
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
