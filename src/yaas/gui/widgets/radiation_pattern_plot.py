"""Widget que muestra un corte de patrón de radiación.

Solo contiene el canvas de `RadiationPatternPlotAdapter` y una línea de
estado. No conoce proyectos ni motores, no calcula máximos físicos y no
prepara datos por su cuenta: todo eso lo resuelve el adaptador.
"""

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from yaas.domain import RadiationPatternResult
from yaas.gui.plots.radiation_pattern import (
    RadiationPatternPlotAdapter,
    RadiationPatternPlotSummary,
)

EMPTY_MESSAGE = (
    "No radiation pattern to show: the GUI cannot calculate patterns yet."
)


class RadiationPatternPlotWidget(QWidget):
    """Canvas del adaptador más un estado textual."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._adapter = RadiationPatternPlotAdapter()

        self._status = QLabel(EMPTY_MESSAGE)
        self._status.setObjectName("radiationPatternStatus")
        self._status.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(self._status)
        layout.addWidget(self._adapter.canvas, stretch=1)

    @property
    def adapter(self) -> RadiationPatternPlotAdapter:
        return self._adapter

    @property
    def status_text(self) -> str:
        return self._status.text()

    def show_azimuth(
        self,
        result: RadiationPatternResult,
        *,
        theta_index: int,
        floor_db: float,
    ) -> RadiationPatternPlotSummary:
        summary = self._adapter.plot_azimuth(
            result, theta_index=theta_index, floor_db=floor_db
        )
        self._show_summary(summary)
        return summary

    def show_vertical(
        self,
        result: RadiationPatternResult,
        *,
        phi_index: int,
        floor_db: float,
    ) -> RadiationPatternPlotSummary:
        summary = self._adapter.plot_vertical(
            result, phi_index=phi_index, floor_db=floor_db
        )
        self._show_summary(summary)
        return summary

    def clear(self) -> None:
        self._adapter.clear()
        self._status.setText(EMPTY_MESSAGE)

    def _show_summary(self, summary: RadiationPatternPlotSummary) -> None:
        self._status.setText(
            f"{summary.total_points} points, {summary.null_points} null, "
            f"{summary.clipped_points} drawn at the "
            f"{summary.floor_db:g} dBi floor."
        )
