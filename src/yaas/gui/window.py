"""Ventana principal mínima de YAAS.

Este módulo importa PySide6 y solo se carga desde `yaas.gui.main`
cuando la ventana va a mostrarse. No usa motores, proyectos ni
exportadores: es un esqueleto sin lógica de negocio.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QMainWindow, QVBoxLayout, QWidget

import yaas

WINDOW_TITLE = "YAAS"
FULL_NAME = "Yet Another Antenna Simulator"
INITIAL_SIZE = (800, 500)


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

        layout = QVBoxLayout()
        for label in (title, name, version):
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label)

        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)
