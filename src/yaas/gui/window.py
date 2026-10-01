"""Ventana principal de YAAS.

Este módulo importa PySide6 y solo se carga desde `yaas.gui.main`
cuando la ventana va a mostrarse. Abre proyectos a través de
`ProjectController` (la ventana solo elige el archivo con `QFileDialog`
y presenta los errores con `QMessageBox`); no usa motores ni
exportadores, y el área de patrón de radiación permanece vacía porque
todavía no se calcula ningún patrón.
"""

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QFont, QKeySequence
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
from yaas.gui.controllers.project import ProjectController
from yaas.gui.controllers.project_state import ProjectViewState
from yaas.gui.widgets.project_summary import ProjectSummaryWidget
from yaas.gui.widgets.radiation_pattern_plot import RadiationPatternPlotWidget

INITIAL_SIZE = (900, 750)

ErrorPresenter = Callable[[str, str], None]


class MainWindow(QMainWindow):
    """Ventana principal: identidad, menú File y resumen del proyecto."""

    def __init__(
        self,
        controller: ProjectController | None = None,
        *,
        error_presenter: ErrorPresenter | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle(texts.window_title(None))
        self.resize(*INITIAL_SIZE)

        self.controller = controller or ProjectController(parent=self)
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
        self.radiation_pattern_plot = RadiationPatternPlotWidget()

        self.tabs = QTabWidget()
        self.tabs.setObjectName("mainTabs")
        self.tabs.addTab(
            self.radiation_pattern_plot, texts.RADIATION_PATTERN_TAB
        )

        layout = QVBoxLayout()
        for label in (title, name, version):
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label)
        layout.addWidget(self.project_summary)
        layout.addWidget(self.tabs, stretch=1)

        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

        self._create_menu()

        self.controller.project_opened.connect(self._on_project_opened)
        self.controller.project_closed.connect(self._on_project_closed)
        self.controller.error_occurred.connect(self._present_error)

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

    def choose_and_open_project(self) -> bool:
        """Pide un archivo `.yaas` y lo abre; cancelar no cambia nada.

        Returns:
            True si se eligió un archivo y se abrió.
        """
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

    def _on_project_opened(self, state: ProjectViewState) -> None:
        self.setWindowTitle(texts.window_title(state.name))
        self.project_summary.show_project(state)
        # Todavía no hay resultados: el gráfico queda vacío.
        self.radiation_pattern_plot.clear()
        self.close_project_action.setEnabled(True)

    def _on_project_closed(self) -> None:
        self.setWindowTitle(texts.window_title(None))
        self.project_summary.clear()
        self.radiation_pattern_plot.clear()
        self.close_project_action.setEnabled(False)

    def _show_error_dialog(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)
