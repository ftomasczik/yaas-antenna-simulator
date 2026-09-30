"""Escritura de proyectos YAAS."""

import json
from pathlib import Path
from typing import Any

from yaas.domain import (
    AngularSweep,
    FreeSpaceEnvironment,
    PerfectGroundEnvironment,
    RealGroundEnvironment,
    RealGroundModel,
)
from yaas.projects.models import (
    CURRENT_SCHEMA_VERSION,
    AntennaProject,
    RadiationPatternSettings,
)


def _angular_sweep_to_dict(sweep: AngularSweep) -> dict[str, Any]:
    """Serializa un eje angular sin campos derivados (sin stop_deg)."""
    return {
        "start_deg": float(sweep.start_deg),
        "count": sweep.count,
        "step_deg": float(sweep.step_deg),
    }


def _radiation_pattern_to_dict(
    settings: RadiationPatternSettings,
) -> dict[str, Any]:
    """Serializa la configuración de patrón: theta antes que phi."""
    return {
        "theta": _angular_sweep_to_dict(settings.theta),
        "phi": _angular_sweep_to_dict(settings.phi),
    }


def _environment_to_dict(environment: Any) -> dict[str, Any]:
    """Serializa un Environment de dominio a su forma exacta (schema 3 y 4).

    Selección exhaustiva por tipo: un tipo de entorno no reconocido
    produce un error claro, nunca una caída silenciosa a espacio
    libre (por ejemplo, si en el futuro se agrega un nuevo tipo de
    entorno al dominio sin actualizar este escritor). Lo mismo aplica
    al ``model`` de ``RealGroundEnvironment``: solo se serializa un
    ``RealGroundModel`` reconocido, vía su propio ``.value`` (nunca un
    valor inventado por este escritor).
    """
    if isinstance(environment, FreeSpaceEnvironment):
        return {"kind": "free_space"}

    if isinstance(environment, PerfectGroundEnvironment):
        return {"kind": "perfect_ground"}

    if isinstance(environment, RealGroundEnvironment):
        if not isinstance(environment.model, RealGroundModel):
            raise ValueError(
                "No se sabe serializar este RealGroundModel: "
                f"{environment.model!r}."
            )

        return {
            "kind": "real_ground",
            "model": environment.model.value,
            "relative_permittivity": environment.relative_permittivity,
            "conductivity_s_per_m": environment.conductivity_s_per_m,
        }

    raise ValueError(
        f"No se sabe serializar este tipo de entorno: {environment!r}."
    )


def project_to_dict(
    project: AntennaProject,
) -> dict[str, Any]:
    """Convierte un proyecto a su representación serializable.

    Siempre escribe schema_version=4 y siempre incluye
    simulation.environment, sin importar con qué schema_version se
    haya construido `project` en memoria (por ejemplo, uno recién
    leído de un archivo v1, v2 o v3): un proyecto de una versión
    anterior leído y vuelto a guardar queda migrado a v4.
    simulation.radiation_pattern solo se escribe si el proyecto define
    uno. No se modifica `project` (es un dataclass inmutable); esta
    función solo lee sus campos.
    """
    data: dict[str, Any] = {
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

    if project.radiation_pattern is not None:
        data["simulation"]["radiation_pattern"] = (
            _radiation_pattern_to_dict(project.radiation_pattern)
        )

    return data


def save_project(
    project: AntennaProject,
    destination: str | Path,
) -> Path:
    """Guarda un proyecto como JSON con extensión `.yaas`.

    Args:
        project: Proyecto que se desea guardar.
        destination: Archivo de salida.

    Returns:
        Ruta del archivo creado.

    Raises:
        ValueError: Si el archivo no utiliza `.yaas`.
    """
    output_path = Path(destination)

    if output_path.suffix.lower() != ".yaas":
        raise ValueError(
            "El archivo del proyecto debe utilizar "
            "la extensión .yaas."
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
