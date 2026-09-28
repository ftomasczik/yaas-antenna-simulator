"""Caso de uso: comparar el barrido simulado de un proyecto con una medición.

Este módulo depende únicamente de modelos del dominio, de
`compare_sweeps`, del protocolo `SimulationEngine` y de los modelos de
proyecto. No conoce argparse, gettext ni ningún motor de simulación
concreto, para poder reutilizarse desde la CLI y desde una futura
interfaz gráfica.
"""

from yaas.domain import (
    MeasurementSweep,
    SweepComparison,
    compare_sweeps,
)
from yaas.engines.base import SimulationEngine
from yaas.projects import AntennaProject


class ComparisonRequestError(ValueError):
    """Indica que la comparación solicitada no es válida.

    Se produce únicamente a partir de un ValueError de compare_sweeps
    (impedancia de referencia inválida, sin solapamiento medido,
    valores no finitos). Nunca envuelve un error propio del motor de
    simulación.
    """


def compare_project_measurement(
    project: AntennaProject,
    measurement: MeasurementSweep,
    *,
    reference_impedance: float,
    engine: SimulationEngine,
) -> SweepComparison:
    """Simula el barrido de un proyecto y lo compara con una medición.

    Args:
        project: Proyecto ya cargado y validado.
        measurement: Medición Touchstone ya cargada.
        reference_impedance: Impedancia de referencia común exigida
            por compare_sweeps.
        engine: Motor de simulación ya construido.

    Returns:
        La comparación resultante.

    Raises:
        ComparisonRequestError: Si compare_sweeps rechaza la
            solicitud. La causa original queda disponible en
            `__cause__`.
        Exception: Cualquier excepción propia de
            `engine.simulate_sweep` se propaga sin modificarse; no
            se clasifica como un error de la solicitud de comparación.
    """
    simulation = engine.simulate_sweep(
        project.to_sweep_request()
    )

    try:
        return compare_sweeps(
            simulation=simulation,
            measurement=measurement,
            reference_impedance=reference_impedance,
        )
    except ValueError as error:
        raise ComparisonRequestError(str(error)) from error
