"""Ventana principal de YAAS.

Este módulo importa PySide6 y solo se carga desde `yaas.gui.main`
cuando la ventana va a mostrarse. Abre proyectos a través de
`ProjectController` (la ventana solo elige el archivo con `QFileDialog`
y presenta los errores con `QMessageBox`) y calcula el patrón del
proyecto abierto a través de `RadiationPatternController`, que lo
ejecuta fuera del hilo principal. La ventana nunca crea ni importa el
motor: solo dibuja el corte que elige el controlador (`CutSelection`)
con `RadiationPatternPlotWidget`, y reenvía al controlador lo que el
usuario elige en `CutSelectorWidget`. Cambiar de corte nunca recalcula.
"""

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent, QFont, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

import yaas
from yaas.gui import texts
from yaas.gui.controllers.pattern import (
    EngineFactory,
    PatternCalculationState,
    RadiationPatternController,
    create_pynec_engine,
)
from yaas.gui.controllers.pattern_cut import CutKind, CutSelection
from yaas.gui.controllers.project import ProjectController
from yaas.gui.controllers.project_state import ProjectViewState
from yaas.gui.widgets.cut_selector import CutSelectorWidget
from yaas.gui.widgets.project_summary import ProjectSummaryWidget
from yaas.gui.widgets.radiation_pattern_plot import RadiationPatternPlotWidget

INITIAL_SIZE = (900, 780)

ErrorPresenter = Callable[[str, str], None]


class MainWindow(QMainWindow):
    """Ventana principal: menús File y Calculate, proyecto y patrón."""

    def __init__(
        self,
        controller: ProjectController | None = None,
        *,
        pattern_controller: RadiationPatternController | None = None,
        engine_factory: EngineFactory = create_pynec_engine,
        error_presenter: ErrorPresenter | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle(texts.window_title(None))
        self.resize(*INITIAL_SIZE)

        self.controller = controller or ProjectController(parent=self)
        self.pattern_controller = pattern_controller or (
            RadiationPatternController(
                self.controller, engine_factory=engine_factory, parent=self
            )
        )
        self._present_error = error_presenter or self._show_error_dialog

        title = QLabel(texts.WINDOW_TITLE)
        title.setObjectName("titleLabel")
        title_font = QFont(title.font())
        title_font.setPointSize(title_font.pointSize() * 2)
        title_font.setBold(True)
        title.setFont(title_font)

        name = QLabel(texts.FULL_NAME)
        name.setObjectName("nameLabel")

        version = QLabel(f"Version {yaas.__version__}")
        version.setObjectName("versionLabel")

        self.project_summary = ProjectSummaryWidget()
        self.calculation_status = QLabel()
        self.calculation_status.setObjectName("calculationStatus")
        self.calculation_status.setWordWrap(True)
        self.cut_selector = CutSelectorWidget()
        self.radiation_pattern_plot = RadiationPatternPlotWidget()

        # Pestaña del patrón: selector de corte compacto sobre el gráfico.
        self.radiation_pattern_tab = QWidget()
        self.radiation_pattern_tab.setObjectName("radiationPatternTab")
        tab_layout = QVBoxLayout(self.radiation_pattern_tab)
        tab_layout.addWidget(self.cut_selector)
        tab_layout.addWidget(self.radiation_pattern_plot, stretch=1)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("mainTabs")
        self.tabs.addTab(
            self.radiation_pattern_tab, texts.RADIATION_PATTERN_TAB
        )

        layout = QVBoxLayout()
        for label in (title, name, version):
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label)
        layout.addWidget(self.project_summary)
        layout.addWidget(self.calculation_status)
        layout.addWidget(self.tabs, stretch=1)

        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

        self._create_menu()

        self.controller.project_opened.connect(self._on_project_opened)
        self.controller.project_closed.connect(self._on_project_closed)
        self.controller.error_occurred.connect(self._present_error)
        self.pattern_controller.state_changed.connect(
            self._on_calculation_state_changed
        )
        self.pattern_controller.selection_changed.connect(
            self._on_selection_changed
        )
        self.pattern_controller.error_occurred.connect(self._present_error)
        self.cut_selector.kind_selected.connect(self._on_cut_kind_selected)
        self.cut_selector.index_selected.connect(
            self.pattern_controller.select_cut_index
        )
        self._refresh_calculation()

    def _create_menu(self) -> None:
        self.open_action = QAction(texts.OPEN_ACTION, self)
        self.open_action.setShortcut(QKeySequence.StandardKey.Open)
        self.open_action.triggered.connect(self.choose_and_open_project)

        self.close_project_action = QAction(texts.CLOSE_PROJECT_ACTION, self)
        self.close_project_action.setEnabled(False)
        self.close_project_action.triggered.connect(
            self.controller.close_project
        )

        self.exit_action = QAction(texts.EXIT_ACTION, self)
        self.exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        self.exit_action.triggered.connect(self.close)

        self.file_menu = self.menuBar().addMenu(texts.FILE_MENU)
        self.file_menu.addAction(self.open_action)
        self.file_menu.addAction(self.close_project_action)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.exit_action)

        self.calculate_pattern_action = QAction(
            texts.CALCULATE_PATTERN_ACTION, self
        )
        self.calculate_pattern_action.setShortcut(QKeySequence("F5"))
        self.calculate_pattern_action.triggered.connect(
            self.pattern_controller.calculate
        )

        self.cancel_calculation_action = QAction(
            texts.CANCEL_CALCULATION_ACTION, self
        )
        self.cancel_calculation_action.triggered.connect(
            self.pattern_controller.cancel
        )

        self.calculate_menu = self.menuBar().addMenu(texts.CALCULATE_MENU)
        self.calculate_menu.addAction(self.calculate_pattern_action)
        self.calculate_menu.addAction(self.cancel_calculation_action)

    def choose_and_open_project(self) -> bool:
        """Pide un archivo `.yaas` y lo abre; cancelar no cambia nada.

        Returns:
            True si se eligió un archivo y se abrió.
        """
        if self.pattern_controller.is_busy:
            return False
        selected, _ = QFileDialog.getOpenFileName(
            self,
            texts.OPEN_DIALOG_TITLE,
            "",
            texts.PROJECT_FILE_FILTER,
        )
        if not selected:
            return False
        return self.open_project_path(selected)

    def open_project_path(self, path: str | Path) -> bool:
        """Abre ``path`` mediante el controlador."""
        return self.controller.open_project(path)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - API de Qt
        # Decisión explícita: con un cálculo activo se pide la
        # cancelación y se espera (bloqueando) a que termine la llamada
        # nativa en curso, que no puede interrumpirse, para no dejar
        # hilos vivos ni usar QThread.terminate(). Todavía no se pide
        # confirmación al usuario (ver
        # docs/research/gui-radiation-visualization.md, §8).
        self.pattern_controller.shutdown()
        super().closeEvent(event)

    def _on_project_opened(self, state: ProjectViewState) -> None:
        self.setWindowTitle(texts.window_title(state.name))
        self.project_summary.show_project(state)
        # Un proyecto recién abierto todavía no tiene resultado.
        self._clear_plot()
        self._refresh_calculation()

    def _on_project_closed(self) -> None:
        self.setWindowTitle(texts.window_title(None))
        self.project_summary.clear()
        self._clear_plot()
        self._refresh_calculation()

    def _on_selection_changed(self, selection: CutSelection | None) -> None:
        # Redibuja el resultado vigente: nunca vuelve a ejecutar el motor.
        if selection is None:
            self.radiation_pattern_plot.clear()
        else:
            self.radiation_pattern_plot.show_cut(
                selection.analysis.result,
                kind=selection.kind,
                index=selection.index,
                floor_db=selection.floor_db,
            )
        self._refresh_calculation()

    def _on_cut_kind_selected(self, kind: CutKind) -> None:
        self.pattern_controller.select_cut_kind(kind)

    def _on_calculation_state_changed(
        self, state: PatternCalculationState
    ) -> None:
        if state is PatternCalculationState.ERROR:
            self._clear_plot()
        self._refresh_calculation()

    def _clear_plot(self) -> None:
        self.radiation_pattern_plot.clear()

    def _refresh_calculation(self) -> None:
        """Habilita las acciones y actualiza el estado visible."""
        pattern = self.pattern_controller
        state = pattern.state
        busy = pattern.is_busy
        project = self.controller.state

        # Mientras calcula, nada puede cambiar el proyecto ni iniciar
        # otro cálculo.
        self.open_action.setEnabled(not busy)
        self.close_project_action.setEnabled(
            self.controller.has_project and not busy
        )
        self.calculate_pattern_action.setEnabled(
            not busy
            and project is not None
            and project.has_radiation_pattern
        )
        self.cancel_calculation_action.setEnabled(
            state is PatternCalculationState.CALCULATING
        )
        # Durante un cálculo el corte vigente se ve, pero no se cambia.
        self.cut_selector.show_selection(pattern.selection, enabled=not busy)
        self.calculation_status.setText(self._status_text(state))

    def _status_text(self, state: PatternCalculationState) -> str:
        if state is PatternCalculationState.READY:
            return texts.CALCULATION_STATUS_READY
        if state is PatternCalculationState.CALCULATING:
            return texts.CALCULATION_STATUS_CALCULATING
        if state is PatternCalculationState.CANCELLING:
            return texts.CALCULATION_STATUS_CANCELLING
        if state is PatternCalculationState.ERROR:
            return texts.CALCULATION_STATUS_ERROR.format(
                message=self.pattern_controller.last_error
            )
        if state is PatternCalculationState.RESULT:
            return self._result_text()
        return texts.CALCULATION_STATUS_EMPTY

    def _result_text(self) -> str:
        analysis = self.pattern_controller.analysis
        maximum = analysis.summary.maximum
        if maximum is None:
            text = texts.CALCULATION_STATUS_NO_MAXIMUM
        else:
            text = texts.CALCULATION_STATUS_RESULT.format(
                gain=maximum.gain_db,
                theta=maximum.theta_deg,
                phi=maximum.phi_deg,
            )
        selection = self.pattern_controller.selection
        if selection is not None:
            template = (
                texts.CALCULATION_STATUS_AZIMUTH_CUT
                if selection.kind is CutKind.AZIMUTH
                else texts.CALCULATION_STATUS_VERTICAL_CUT
            )
            text += " " + template.format(angle=selection.fixed_angle_deg)
        return text

    def _show_error_dialog(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)
