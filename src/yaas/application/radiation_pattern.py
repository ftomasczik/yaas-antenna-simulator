"""Casos de uso: calcular, resumir y exportar el patrón de un proyecto.

Este módulo depende únicamente del dominio, de los modelos de proyecto,
del protocolo `SimulationEngine` y de los exportadores. No conoce
argparse, gettext ni ningún motor de simulación concreto, para poder
reutilizarse desde la CLI y desde una futura interfaz gráfica.

El flujo tiene dos pasos, como `prepare_mmana_import`/`write_mmana_import`:
`prepare_radiation_pattern_request` valida el proyecto sin tocar ningún
motor (así quien llama puede rechazar un proyecto sin patrón antes de
construir un motor nativo), y `calculate_radiation_pattern` ejecuta el
motor y resume el resultado.

La exportación CSV de un resultado ya calculado no necesita un caso de
uso propio: `yaas.exporters.export_radiation_pattern_csv` ya es la API
reutilizable, y un envoltorio no agregaría más que una llamada idéntica.
"""

import math
from dataclasses import dataclass
from pathlib import Path

from yaas.domain import (
    RadiationPatternRequest,
    RadiationPatternResult,
    RadiationPatternSample,
)
from yaas.engines.base import SimulationEngine
from yaas.exporters import export_radiation_pattern_nec
from yaas.projects import AntennaProject

# Dos ganancias a no más de esta distancia absoluta se consideran
# empatadas al elegir la dirección del máximo. Existe para que la
# dirección informada no dependa del ruido de punto flotante entre
# plataformas (por ejemplo, theta=0 y theta=180 de un dipolo en espacio
# libre difieren en ~4e-15 dB según el sistema); no redondea ni
# modifica ningún valor del resultado.
_PATTERN_GAIN_TIE_TOLERANCE_DB = 1e-9


class MissingRadiationPatternError(ValueError):
    """Indica que el proyecto no define un patrón de radiación.

    Se produce únicamente a partir del ValueError de
    `AntennaProject.to_radiation_pattern_request()`. Nunca envuelve un
    error propio del motor de simulación, que se propaga sin
    modificarse.
    """


@dataclass(frozen=True)
class RadiationPatternSummary:
    """Resumen numérico de un patrón, sin texto ni formato.

    ``maximum`` es la primera muestra theta-major con la mayor ganancia
    válida (ver `summarize_radiation_pattern`), o None si todas las
    muestras son nulas.
    """

    total_points: int
    valid_points: int
    null_points: int
    maximum: RadiationPatternSample | None

    def __post_init__(self) -> None:
        for name in ("total_points", "valid_points", "null_points"):
            value = getattr(self, name)
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or value < 0
            ):
                raise ValueError(
                    f"{name} debe ser un entero no negativo."
                )

        if self.valid_points + self.null_points != self.total_points:
            raise ValueError(
                "Los puntos válidos y nulos deben sumar el total."
            )

        if self.maximum is None:
            if self.valid_points != 0:
                raise ValueError(
                    "Un resumen con puntos válidos debe tener un máximo."
                )
            return

        if self.valid_points == 0:
            raise ValueError(
                "Un resumen sin puntos válidos no puede tener un máximo."
            )

        if (
            not isinstance(self.maximum, RadiationPatternSample)
            or self.maximum.gain_db is None
        ):
            raise ValueError(
                "El máximo debe ser una muestra con ganancia válida."
            )


@dataclass(frozen=True)
class RadiationPatternAnalysis:
    """Resultado del motor junto con su resumen."""

    result: RadiationPatternResult
    summary: RadiationPatternSummary


def summarize_radiation_pattern(
    result: RadiationPatternResult,
) -> RadiationPatternSummary:
    """Cuenta puntos válidos y nulos y busca la ganancia máxima.

    Recorre las muestras en el orden del dominio (theta en el lazo
    externo, phi en el interno). ``None`` cuenta como nulo y nunca es
    candidato a máximo. El candidato solo se reemplaza ante una ganancia
    mayor por más de ``_PATTERN_GAIN_TIE_TOLERANCE_DB`` (comparación
    absoluta, ``rel_tol=0.0``): ante un empate, exacto o numérico, queda
    la primera muestra. No calcula el mínimo.
    """
    maximum: RadiationPatternSample | None = None
    null_points = 0
    total_points = 0

    for sample in result.samples:
        total_points += 1

        if sample.gain_db is None:
            null_points += 1
            continue

        if maximum is None or (
            sample.gain_db > maximum.gain_db
            and not math.isclose(
                sample.gain_db,
                maximum.gain_db,
                rel_tol=0.0,
                abs_tol=_PATTERN_GAIN_TIE_TOLERANCE_DB,
            )
        ):
            maximum = sample

    return RadiationPatternSummary(
        total_points=total_points,
        valid_points=total_points - null_points,
        null_points=null_points,
        maximum=maximum,
    )


def prepare_radiation_pattern_request(
    project: AntennaProject,
) -> RadiationPatternRequest:
    """Obtiene la solicitud de patrón de un proyecto, sin usar un motor.

    Raises:
        MissingRadiationPatternError: Si el proyecto no define
            ``simulation.radiation_pattern``. La causa original queda
            disponible en ``__cause__``.
    """
    try:
        return project.to_radiation_pattern_request()
    except ValueError as error:
        raise MissingRadiationPatternError(str(error)) from error


def calculate_radiation_pattern(
    request: RadiationPatternRequest,
    *,
    engine: SimulationEngine,
) -> RadiationPatternAnalysis:
    """Calcula un patrón con el motor recibido y lo resume.

    El motor se ejecuta exactamente una vez.

    Raises:
        Exception: Cualquier excepción de
            ``engine.simulate_radiation_pattern`` se propaga sin
            modificarse.
    """
    result = engine.simulate_radiation_pattern(request)

    return RadiationPatternAnalysis(
        result=result,
        summary=summarize_radiation_pattern(result),
    )


def export_project_radiation_pattern_nec(
    project: AntennaProject,
    destination: str | Path,
) -> Path:
    """Exporta a NEC (con tarjeta RP) el patrón de un proyecto.

    Usa el nombre del proyecto como título y su impedancia de
    referencia en el comentario informativo, igual que la CLI. No
    ejecuta ningún motor. Un proyecto sin patrón se rechaza antes de
    crear el archivo.

    Raises:
        MissingRadiationPatternError: Si el proyecto no define un
            patrón de radiación.
        OSError: Si el archivo no puede escribirse.
    """
    request = prepare_radiation_pattern_request(project)

    return export_radiation_pattern_nec(
        request=request,
        destination=destination,
        title=project.metadata.name,
        reference_impedance=project.reference_impedance,
    )
