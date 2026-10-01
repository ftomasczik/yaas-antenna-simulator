"""Ventana principal mínima de YAAS.

Este módulo importa PySide6 y solo se carga desde `yaas.gui.main`
cuando la ventana va a mostrarse. No usa motores, proyectos ni
exportadores: muestra la identidad de la aplicación y un área de
patrón de radiación vacía (todavía no hay ningún proyecto cargado).
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

import yaas
from yaas.gui.widgets.radiation_pattern_plot import RadiationPatternPlotWidget

WINDOW_TITLE = "YAAS"
FULL_NAME = "Yet Another Antenna Simulator"
RADIATION_PATTERN_TAB = "Radiation pattern"
INITIAL_SIZE = (900, 700)


class MainWindow(QMainWindow):
    """Ventana principal: por ahora solo identifica la aplicación."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(*INITIAL_SIZE)

        title = QLabel(WINDOW_TITLE)
        title.setObjectName("titleLabel")
        title_font = QFont(title.font())
        title_font.setPointSize(title_font.pointSize() * 2)
        title_font.setBold(True)
        title.setFont(title_font)

        name = QLabel(FULL_NAME)
        name.setObjectName("nameLabel")

        version = QLabel(f"Version {yaas.__version__}")
        version.setObjectName("versionLabel")

        self.radiation_pattern_plot = RadiationPatternPlotWidget()

        self.tabs = QTabWidget()
        self.tabs.setObjectName("mainTabs")
        self.tabs.addTab(self.radiation_pattern_plot, RADIATION_PATTERN_TAB)

        layout = QVBoxLayout()
        for label in (title, name, version):
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label)
        layout.addWidget(self.tabs, stretch=1)

        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)
