"""Elección del corte inicial que la GUI dibuja de un patrón calculado.

Regla (todavía no hay selector de cortes):

- ``n_theta > 1`` y ``n_phi == 1``: corte vertical (theta vs dBi);
- ``n_theta == 1`` y ``n_phi > 1``: corte de azimut (polar);
- ambos mayores que uno: corte vertical en el primer ``phi``. Es una
  elección inicial: los demás cortes necesitarán un selector futuro;
- ambos iguales a uno (una sola dirección): corte vertical de un punto.

El piso del gráfico se fija ``PLOT_RANGE_DB`` por debajo del máximo que
ya informa `summarize_radiation_pattern`; no se recalcula aquí. El piso
solo afecta la representación: el adaptador dibuja sobre él los valores
menores, pero `RadiationPatternAnalysis` (resultado y resumen) no se
modifica y conserva todos los valores originales para CSV, resumen y
futuras herramientas. Este módulo no importa Qt.
"""

import math
from dataclasses import dataclass
from enum import Enum

from yaas.application import RadiationPatternAnalysis

# Rango visible del gráfico, debajo de la ganancia máxima.
PLOT_RANGE_DB = 40.0
# Piso cuando todas las muestras son nulas (no hay máximo).
DEFAULT_FLOOR_DB = -40.0


class CutKind(str, Enum):
    VERTICAL = "vertical"
    AZIMUTH = "azimuth"


@dataclass(frozen=True)
class PatternCut:
    """Corte a dibujar: tipo, índice del ángulo fijo y piso."""

    kind: CutKind
    index: int
    floor_db: float
    # True cuando el patrón tiene más cortes que el dibujado (hará
    # falta un selector para verlos).
    has_more_cuts: bool

    def __post_init__(self) -> None:
        if not isinstance(self.kind, CutKind):
            raise ValueError("kind debe ser un CutKind.")
        if (
            not isinstance(self.index, int)
            or isinstance(self.index, bool)
            or self.index < 0
        ):
            raise ValueError("index debe ser un entero no negativo.")
        if not math.isfinite(self.floor_db):
            raise ValueError("floor_db debe ser finito.")


def plot_floor_db(analysis: RadiationPatternAnalysis) -> float:
    """Piso del gráfico a partir del máximo del resumen."""
    maximum = analysis.summary.maximum
    if maximum is None:
        return DEFAULT_FLOOR_DB
    return math.floor(maximum.gain_db) - PLOT_RANGE_DB


def choose_initial_cut(analysis: RadiationPatternAnalysis) -> PatternCut:
    """Primer corte disponible según la forma de la grilla."""
    result = analysis.result
    n_theta = len(result.theta_angles_deg)
    n_phi = len(result.phi_angles_deg)
    floor_db = plot_floor_db(analysis)

    if n_theta == 1 and n_phi > 1:
        return PatternCut(
            kind=CutKind.AZIMUTH,
            index=0,
            floor_db=floor_db,
            has_more_cuts=False,
        )

    # PROVISIONAL: con varios theta y varios phi se dibuja siempre el
    # corte vertical de phi_index=0, hasta que exista un selector de
    # cortes; has_more_cuts lo deja explícito para la vista.
    return PatternCut(
        kind=CutKind.VERTICAL,
        index=0,
        floor_db=floor_db,
        has_more_cuts=n_theta > 1 and n_phi > 1,
    )
