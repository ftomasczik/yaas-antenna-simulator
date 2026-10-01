"""Panel con el resumen del proyecto abierto.

Solo presenta un `ProjectViewState`: no abre archivos, no conoce el
controlador ni el motor. Los textos provienen de `yaas.gui.texts`.
"""

from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QLabel,
    QStackedLayout,
    QWidget,
)

from yaas.domain import (
    AngularSweep,
    Environment,
    FreeSpaceEnvironment,
    PerfectGroundEnvironment,
    RealGroundEnvironment,
    RealGroundModel,
)
from yaas.gui import texts
from yaas.gui.controllers.project_state import ProjectViewState

_REAL_GROUND_MODEL_LABELS = {
    RealGroundModel.SOMMERFELD_NORTON: texts.REAL_GROUND_MODEL_SOMMERFELD_NORTON,
}

# Filas del panel, en orden: (clave estable, etiqueta visible).
_FIELDS = (
    ("name", texts.FIELD_NAME),
    ("path", texts.FIELD_PATH),
    ("schema_version", texts.FIELD_SCHEMA_VERSION),
    ("conductors", texts.FIELD_CONDUCTORS),
    ("frequency", texts.FIELD_FREQUENCY),
    ("reference_impedance", texts.FIELD_REFERENCE_IMPEDANCE),
    ("environment", texts.FIELD_ENVIRONMENT),
    ("sweep", texts.FIELD_SWEEP),
    ("radiation_pattern", texts.FIELD_RADIATION_PATTERN),
    ("theta", texts.FIELD_THETA),
    ("phi", texts.FIELD_PHI),
)
# Filas que solo existen cuando el proyecto define un patrón.
_PATTERN_FIELDS = ("theta", "phi")


def environment_text(environment: Environment) -> str:
    """Etiqueta visible de un entorno del dominio."""
    if isinstance(environment, FreeSpaceEnvironment):
        return texts.ENVIRONMENT_FREE_SPACE
    if isinstance(environment, PerfectGroundEnvironment):
        return texts.ENVIRONMENT_PERFECT_GROUND
    if isinstance(environment, RealGroundEnvironment):
        model = _REAL_GROUND_MODEL_LABELS[environment.model]
        return f"{texts.ENVIRONMENT_REAL_GROUND}{texts.TITLE_SEPARATOR}{model}"
    raise TypeError(f"Entorno no soportado: {environment!r}")


def _axis_text(axis: AngularSweep) -> str:
    return texts.angular_axis_text(
        axis.start_deg, axis.stop_deg, axis.count, axis.step_deg
    )


def project_fields(state: ProjectViewState) -> dict[str, str]:
    """Textos de cada fila del panel; theta/phi solo si hay patrón."""
    fields = {
        "name": state.name,
        "path": str(state.path),
        "schema_version": str(state.schema_version),
        "conductors": str(state.conductor_count),
        "frequency": texts.frequency_text(state.frequency_mhz),
        "reference_impedance": texts.impedance_text(
            state.reference_impedance_ohm
        ),
        "environment": environment_text(state.environment),
        "sweep": texts.yes_no(state.has_sweep),
        "radiation_pattern": texts.yes_no(state.has_radiation_pattern),
    }
    if state.theta is not None and state.phi is not None:
        fields["theta"] = _axis_text(state.theta)
        fields["phi"] = _axis_text(state.phi)
    return fields


class ProjectSummaryWidget(QGroupBox):
    """Resumen del proyecto, o "No project loaded" si no hay ninguno."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(texts.PROJECT_PANEL_TITLE, parent)
        self.setObjectName("projectSummary")

        self._empty = QLabel(texts.NO_PROJECT_LOADED)
        self._empty.setObjectName("noProjectLabel")

        self._form = QFormLayout()
        self._values: dict[str, QLabel] = {}
        for key, label in _FIELDS:
            value = QLabel()
            value.setObjectName(f"project_{key}")
            value.setWordWrap(True)
            self._values[key] = value
            self._form.addRow(label, value)

        self._details = QWidget()
        self._details.setLayout(self._form)

        self._stack = QStackedLayout(self)
        self._stack.addWidget(self._empty)
        self._stack.addWidget(self._details)
        self.clear()

    @property
    def is_empty(self) -> bool:
        return self._stack.currentWidget() is self._empty

    @property
    def empty_text(self) -> str:
        return self._empty.text()

    def displayed_fields(self) -> dict[str, str]:
        """Filas visibles y su texto (vacío si no hay proyecto)."""
        if self.is_empty:
            return {}
        return {
            key: value.text()
            for key, value in self._values.items()
            if self._form.isRowVisible(value)
        }

    def show_project(self, state: ProjectViewState) -> None:
        fields = project_fields(state)
        for key, value in self._values.items():
            value.setText(fields.get(key, ""))
            self._form.setRowVisible(value, key in fields)
        self._stack.setCurrentWidget(self._details)

    def clear(self) -> None:
        for key, value in self._values.items():
            value.clear()
            self._form.setRowVisible(value, key not in _PATTERN_FIELDS)
        self._stack.setCurrentWidget(self._empty)
