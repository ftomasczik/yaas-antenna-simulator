"""Controlador del proyecto abierto en la GUI.

Conserva el `OpenedProject` actual y avisa los cambios con señales Qt.
Abre proyectos únicamente a través de `yaas.application.open_project`
(inyectable para pruebas): nunca lee JSON, nunca guarda, nunca ejecuta
un motor y nunca muestra diálogos; elegir el archivo y presentar los
errores es tarea de la ventana.
"""

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from yaas.application import OpenedProject, open_project
from yaas.gui import texts
from yaas.gui.controllers.project_state import ProjectViewState
from yaas.projects import ProjectFormatError

ProjectOpener = Callable[[str | Path], OpenedProject]


class ProjectController(QObject):
    """Estado del documento: el proyecto abierto o ninguno.

    Señales:

    - ``project_opened(ProjectViewState)``: se abrió un proyecto (y
      reemplazó al anterior, si había uno);
    - ``project_closed()``: se cerró el proyecto abierto;
    - ``error_occurred(title, message)``: no se pudo abrir un archivo;
      el proyecto anterior, si había uno, se conserva.
    """

    project_opened = Signal(object)
    project_closed = Signal()
    error_occurred = Signal(str, str)

    def __init__(
        self,
        opener: ProjectOpener = open_project,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._opener = opener
        self._opened: OpenedProject | None = None
        self._state: ProjectViewState | None = None

    @property
    def opened_project(self) -> OpenedProject | None:
        return self._opened

    @property
    def state(self) -> ProjectViewState | None:
        return self._state

    @property
    def has_project(self) -> bool:
        return self._opened is not None

    def open_project(self, path: str | Path) -> bool:
        """Abre ``path`` y reemplaza el proyecto actual.

        Solo se capturan los errores esperables de apertura y formato
        (`ProjectFormatError` y `OSError`); cualquier otro error se
        propaga, para no ocultar fallos de programación.

        Returns:
            True si el proyecto se abrió; False si falló (y se emitió
            ``error_occurred``).
        """
        try:
            opened = self._opener(path)
        except (ProjectFormatError, OSError) as error:
            self.error_occurred.emit(texts.OPEN_ERROR_TITLE, str(error))
            return False

        state = ProjectViewState.from_opened_project(opened)
        self._opened = opened
        self._state = state
        self.project_opened.emit(state)
        return True

    def close_project(self) -> bool:
        """Cierra el proyecto actual; sin proyecto, no hace nada.

        Returns:
            True si había un proyecto y se cerró.
        """
        if self._opened is None:
            return False

        self._opened = None
        self._state = None
        self.project_closed.emit()
        return True
