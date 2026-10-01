"""Adaptador Matplotlib para cortes 2D de un patrón de radiación.

Contrato visual (ADR 0010):

- corte de azimut (``theta`` fijo): gráfico polar, ``phi=0`` hacia +X
  (derecha), ``phi=90`` hacia +Y (arriba), sentido antihorario, con los
  ángulos reales del resultado;
- corte vertical (``phi`` fijo): gráfico cartesiano ``theta`` (grados)
  frente a ganancia (dBi), solo con los ``theta`` del resultado, sin
  reflejar datos;
- ``None`` (nulo de NEC) se convierte en NaN **solo aquí**, para cortar
  la curva; nunca en -999.99 ni en el piso;
- una ganancia finita bajo el piso se dibuja en el piso: es un recorte
  visual, no un nulo, y el resultado conserva el valor real.

El adaptador no crea ``QApplication``, no abre ventanas, no ejecuta el
motor, no carga proyectos ni modifica el resultado. Quien lo use debe
haber creado ya la ``QApplication``.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

# PySide6 se importa antes que el backend para que Matplotlib use ese
# binding de Qt (y no busque otro).
import PySide6.QtWidgets  # noqa: F401
from matplotlib.axes import Axes
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from yaas.domain import RadiationPatternResult

# Rango radial/vertical cuando no hay ningún valor por encima del piso
# (todos nulos o todos en el piso): evita un rango degenerado sin
# inventar un máximo.
_DEFAULT_SPAN_DB = 10.0

_IMAGE_FORMATS = {".png": "png", ".svg": "svg", ".pdf": "pdf"}


@dataclass(frozen=True)
class RadiationPatternPlotSummary:
    """Cómo se representó un corte (no describe el resultado físico).

    A diferencia de `yaas.application.RadiationPatternSummary`, que
    resume el resultado calculado, este resumen cuenta lo que se dibujó:
    cuántas muestras del corte eran nulas y cuántas ganancias finitas se
    recortaron al piso visual ``floor_db``.
    """

    total_points: int
    null_points: int
    clipped_points: int
    floor_db: float

    def __post_init__(self) -> None:
        for name in ("total_points", "null_points", "clipped_points"):
            value = getattr(self, name)
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or value < 0
            ):
                raise ValueError(f"{name} debe ser un entero no negativo.")

        if self.null_points > self.total_points:
            raise ValueError("Los nulos no pueden superar el total.")

        if self.clipped_points > self.total_points - self.null_points:
            raise ValueError(
                "Los recortados no pueden superar los valores finitos."
            )

        _validate_floor(self.floor_db)

    @property
    def finite_points(self) -> int:
        """Muestras con ganancia finita (recortadas o no)."""
        return self.total_points - self.null_points


def _validate_floor(floor_db: object) -> None:
    if (
        isinstance(floor_db, bool)
        or not isinstance(floor_db, (int, float))
        or not math.isfinite(floor_db)
    ):
        raise ValueError("El piso del gráfico debe ser un número finito.")


def _validate_index(index: object, count: int, name: str) -> int:
    if (
        not isinstance(index, int)
        or isinstance(index, bool)
        or not 0 <= index < count
    ):
        raise ValueError(
            f"{name} debe ser un entero entre 0 y {count - 1}."
        )
    return index


def _prepare_series(
    gains: Sequence[float | None],
    floor_db: float,
) -> tuple[tuple[float, ...], int, int]:
    """Convierte ganancias del dominio en valores para dibujar.

    ``None`` pasa a NaN (discontinuidad); una ganancia finita bajo el
    piso pasa al piso y se cuenta como recortada; el resto se conserva.
    Devuelve valores nuevos, la cantidad de nulos y la de recortados; no
    modifica ``gains``.
    """
    values = []
    nulls = 0
    clipped = 0

    for gain in gains:
        if gain is None:
            values.append(math.nan)
            nulls += 1
        elif gain < floor_db:
            values.append(float(floor_db))
            clipped += 1
        else:
            values.append(float(gain))

    return tuple(values), nulls, clipped


def _upper_limit(values: Sequence[float], floor_db: float) -> float:
    """Tope de la escala: entero superior al máximo dibujado, o piso + rango."""
    finite = [value for value in values if not math.isnan(value)]
    if finite:
        top = float(math.ceil(max(finite)))
        if top > floor_db:
            return top
    return floor_db + _DEFAULT_SPAN_DB


class RadiationPatternPlotAdapter:
    """Dibuja cortes de un `RadiationPatternResult` en un canvas Qt.

    Reutiliza siempre la misma `Figure` y el mismo `FigureCanvasQTAgg`;
    cada gráfico nuevo reemplaza por completo los ejes anteriores.
    """

    def __init__(self) -> None:
        self._figure = Figure(figsize=(5.0, 4.0), layout="constrained")
        self._canvas = FigureCanvasQTAgg(self._figure)
        self._axes: Axes | None = None

    @property
    def figure(self) -> Figure:
        return self._figure

    @property
    def canvas(self) -> FigureCanvasQTAgg:
        return self._canvas

    @property
    def axes(self) -> Axes | None:
        """Ejes del gráfico actual, o None si no hay ninguno."""
        return self._axes

    def clear(self) -> None:
        """Quita el gráfico actual."""
        self._figure.clear()
        self._axes = None
        self._canvas.draw_idle()

    def plot_azimuth(
        self,
        result: RadiationPatternResult,
        *,
        theta_index: int,
        floor_db: float,
    ) -> RadiationPatternPlotSummary:
        """Dibuja en polar el corte ``theta = theta_angles_deg[theta_index]``."""
        _require_result(result)
        _validate_floor(floor_db)
        index = _validate_index(theta_index, result.n_theta, "theta_index")

        values, nulls, clipped = _prepare_series(
            result.gain_db[index], floor_db
        )

        axes = self._new_axes(projection="polar")
        axes.set_theta_zero_location("E")   # phi=0 hacia +X
        axes.set_theta_direction(1)         # antihorario visto desde +Z
        axes.plot(
            [math.radians(phi) for phi in result.phi_angles_deg],
            values,
        )
        axes.set_ylim(floor_db, _upper_limit(values, floor_db))
        axes.set_ylabel("Gain (dBi)", labelpad=24)
        axes.set_title(
            f"Azimuth cut (theta = {result.theta_angles_deg[index]:g} deg)"
        )
        axes.grid(True)

        return self._finish(len(values), nulls, clipped, floor_db)

    def plot_vertical(
        self,
        result: RadiationPatternResult,
        *,
        phi_index: int,
        floor_db: float,
    ) -> RadiationPatternPlotSummary:
        """Dibuja ``theta`` frente a dBi en el corte ``phi = phi_angles_deg[phi_index]``."""
        _require_result(result)
        _validate_floor(floor_db)
        index = _validate_index(phi_index, result.n_phi, "phi_index")

        values, nulls, clipped = _prepare_series(
            [row[index] for row in result.gain_db], floor_db
        )
        theta = result.theta_angles_deg

        axes = self._new_axes()
        axes.plot(theta, values)
        low, high = min(theta), max(theta)
        if low == high:
            low, high = low - 1.0, high + 1.0
        axes.set_xlim(low, high)
        axes.set_ylim(floor_db, _upper_limit(values, floor_db))
        axes.set_xlabel("theta (deg)")
        axes.set_ylabel("Gain (dBi)")
        axes.set_title(
            f"Vertical cut (phi = {result.phi_angles_deg[index]:g} deg)"
        )
        axes.grid(True)

        return self._finish(len(values), nulls, clipped, floor_db)

    def save_image(self, destination: str | Path) -> Path:
        """Guarda el gráfico actual como PNG, SVG o PDF, según la extensión.

        No crea directorios: si el directorio no existe, se propaga el
        error del sistema de archivos.

        Raises:
            ValueError: Si la extensión falta o no es .png, .svg ni .pdf.
        """
        path = Path(destination)
        image_format = _IMAGE_FORMATS.get(path.suffix.lower())
        if image_format is None:
            raise ValueError(
                "La imagen debe usar la extensión .png, .svg o .pdf: "
                f"{path.name!r}."
            )

        self._figure.savefig(path, format=image_format)
        return path

    def _new_axes(self, projection: str | None = None) -> Axes:
        self._figure.clear()
        self._axes = self._figure.add_subplot(projection=projection)
        return self._axes

    def _finish(
        self,
        total: int,
        nulls: int,
        clipped: int,
        floor_db: float,
    ) -> RadiationPatternPlotSummary:
        self._canvas.draw_idle()
        return RadiationPatternPlotSummary(
            total_points=total,
            null_points=nulls,
            clipped_points=clipped,
            floor_db=float(floor_db),
        )


def _require_result(result: object) -> None:
    if not isinstance(result, RadiationPatternResult):
        raise TypeError(
            "Se esperaba un RadiationPatternResult: "
            f"{type(result).__name__!r}."
        )
