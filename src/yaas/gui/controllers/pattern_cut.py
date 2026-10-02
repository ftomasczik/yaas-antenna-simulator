"""Selección del corte que la GUI dibuja de un patrón calculado.

`CutSelection` es un modelo inmutable y sin Qt: decide qué cortes admite
la forma de la grilla, cuál se muestra y con qué piso, sin dibujar.

Modos según la forma ``(n_theta, n_phi)`` del resultado:

- ``n_theta > 1`` y ``n_phi == 1``: solo vertical (theta vs dBi), con el
  único ``phi``;
- ``n_theta == 1`` y ``n_phi > 1``: solo azimut (polar), con el único
  ``theta``;
- ambos mayores que uno: vertical y azimut;
- ``1 x 1``: solo vertical, un gráfico cartesiano de un único punto.

La selección se guarda como índices de ``theta_angles_deg`` /
``phi_angles_deg`` (nunca se buscan ángulos por igualdad de floats), y
cada modo conserva su propio índice al cambiar de modo. La selección
inicial es determinista: vertical si la forma lo admite, y el índice 0
de cada eje.

El piso del gráfico se fija ``PLOT_RANGE_DB`` por debajo del máximo que
ya informa `summarize_radiation_pattern`; no se recalcula aquí. El piso
solo afecta la representación: el adaptador dibuja sobre él los valores
menores, pero `RadiationPatternAnalysis` (resultado y resumen) no se
modifica y conserva todos los valores originales para CSV, resumen y
futuras herramientas. Este módulo no importa Qt.
"""

import dataclasses
import math
from dataclasses import dataclass
from enum import Enum

from yaas.application import RadiationPatternAnalysis

# Rango visible del gráfico, debajo de la ganancia máxima.
PLOT_RANGE_DB = 40.0
# Piso cuando todas las muestras son nulas (no hay máximo).
DEFAULT_FLOOR_DB = -40.0


class CutKind(str, Enum):
    # Vertical: phi fijo, theta en el eje X.
    VERTICAL = "vertical"
    # Azimut: theta fijo, phi en el eje angular.
    AZIMUTH = "azimuth"


def plot_floor_db(analysis: RadiationPatternAnalysis) -> float:
    """Piso del gráfico a partir del máximo del resumen."""
    maximum = analysis.summary.maximum
    if maximum is None:
        return DEFAULT_FLOOR_DB
    return math.floor(maximum.gain_db) - PLOT_RANGE_DB


def available_cut_kinds(
    analysis: RadiationPatternAnalysis,
) -> tuple[CutKind, ...]:
    """Modos que admite la forma de la grilla, en orden estable."""
    n_theta = len(analysis.result.theta_angles_deg)
    n_phi = len(analysis.result.phi_angles_deg)
    if n_theta == 1 and n_phi > 1:
        return (CutKind.AZIMUTH,)
    if n_theta > 1 and n_phi > 1:
        return (CutKind.VERTICAL, CutKind.AZIMUTH)
    # n_theta > 1 y n_phi == 1, o una sola dirección (1 x 1).
    return (CutKind.VERTICAL,)


def _validate_index(value: object, name: str, size: int) -> None:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or not 0 <= value < size
    ):
        raise ValueError(f"{name} debe ser un índice entre 0 y {size - 1}.")


@dataclass(frozen=True)
class CutSelection:
    """Corte elegido de un patrón: modo e índice de cada modo.

    ``phi_index`` es el ``phi`` fijo del corte vertical y
    ``theta_index`` el ``theta`` fijo del corte de azimut; ambos se
    conservan aunque el modo activo sea el otro.
    """

    analysis: RadiationPatternAnalysis
    kind: CutKind
    phi_index: int = 0
    theta_index: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.analysis, RadiationPatternAnalysis):
            raise ValueError("analysis debe ser un RadiationPatternAnalysis.")
        if not isinstance(self.kind, CutKind):
            raise ValueError("kind debe ser un CutKind.")
        if self.kind not in available_cut_kinds(self.analysis):
            raise ValueError(
                f"El corte {self.kind.value} no está disponible para esta grilla."
            )
        result = self.analysis.result
        _validate_index(self.phi_index, "phi_index", len(result.phi_angles_deg))
        _validate_index(
            self.theta_index, "theta_index", len(result.theta_angles_deg)
        )

    @classmethod
    def initial(cls, analysis: RadiationPatternAnalysis) -> "CutSelection":
        """Selección determinista para un resultado nuevo."""
        return cls(analysis=analysis, kind=available_cut_kinds(analysis)[0])

    @property
    def available_kinds(self) -> tuple[CutKind, ...]:
        return available_cut_kinds(self.analysis)

    @property
    def angles_deg(self) -> tuple[float, ...]:
        """Ángulos reales del eje fijo del modo activo."""
        result = self.analysis.result
        if self.kind is CutKind.VERTICAL:
            return result.phi_angles_deg
        return result.theta_angles_deg

    @property
    def index(self) -> int:
        """Índice del ángulo fijo del modo activo."""
        if self.kind is CutKind.VERTICAL:
            return self.phi_index
        return self.theta_index

    @property
    def fixed_angle_deg(self) -> float:
        return self.angles_deg[self.index]

    @property
    def floor_db(self) -> float:
        return plot_floor_db(self.analysis)

    @property
    def can_change_kind(self) -> bool:
        return len(self.available_kinds) > 1

    @property
    def can_change_angle(self) -> bool:
        return len(self.angles_deg) > 1

    def with_kind(self, kind: CutKind) -> "CutSelection":
        """Cambia de modo conservando el índice de cada modo."""
        return dataclasses.replace(self, kind=kind)

    def with_index(self, index: int) -> "CutSelection":
        """Cambia el ángulo fijo del modo activo."""
        if self.kind is CutKind.VERTICAL:
            return dataclasses.replace(self, phi_index=index)
        return dataclasses.replace(self, theta_index=index)
