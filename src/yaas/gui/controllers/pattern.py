"""Controlador del cálculo de patrones de radiación en la GUI.

Calcula el patrón del proyecto abierto en `ProjectController` sin
bloquear el hilo principal:

- `prepare_radiation_pattern_request` corre en el hilo principal (no
  usa motor) y rechaza un proyecto sin patrón;
- el motor se crea y `calculate_radiation_pattern` se ejecuta dentro
  del worker de `SimulationRunner`; PyNEC recién se importa ahí;
- un solo cálculo a la vez; la cancelación es cooperativa y una llamada
  nativa en curso no puede interrumpirse: su resultado se descarta al
  terminar.

No dibuja ni muestra diálogos: emite estados, resultados y errores.
"""

import traceback
from collections.abc import Callable
from enum import Enum

from PySide6.QtCore import QObject, Signal

from yaas.application import (
    MissingRadiationPatternError,
    RadiationPatternAnalysis,
    calculate_radiation_pattern,
    prepare_radiation_pattern_request,
)
from yaas.domain import RadiationPatternRequest
from yaas.engines import SimulationEngine
from yaas.gui import texts
from yaas.gui.controllers.project import ProjectController
from yaas.gui.controllers.project_state import ProjectViewState
from yaas.gui.runner import CancellationToken, SimulationRunner

EngineFactory = Callable[[], SimulationEngine]


def create_pynec_engine() -> SimulationEngine:
    """Crea el motor real; solo se llama dentro del worker."""
    from yaas.engines.pynec import PyNecEngine

    return PyNecEngine()


class PatternCalculationState(str, Enum):
    """Estados del cálculo de patrones."""

    # Sin proyecto, o con un proyecto que no define un patrón.
    EMPTY = "empty"
    # Proyecto con patrón, todavía sin calcular.
    READY = "ready"
    CALCULATING = "calculating"
    # Se pidió cancelar; se espera a que termine la llamada en curso.
    CANCELLING = "cancelling"
    RESULT = "result"
    ERROR = "error"


BUSY_STATES = frozenset(
    {PatternCalculationState.CALCULATING, PatternCalculationState.CANCELLING}
)


def _run_pattern_job(
    request: RadiationPatternRequest,
    engine_factory: EngineFactory,
    token: CancellationToken,
) -> RadiationPatternAnalysis:
    """Trabajo del worker: crea el motor y calcula (hilo secundario)."""
    engine = engine_factory()
    token.raise_if_cancelled()
    # Llamada nativa: no puede interrumpirse una vez iniciada.
    return calculate_radiation_pattern(request, engine=engine)


class RadiationPatternController(QObject):
    """Estado del cálculo del patrón del proyecto abierto.

    Señales:

    - ``state_changed(PatternCalculationState)``;
    - ``result_ready(RadiationPatternAnalysis)``: nuevo resultado
      vigente;
    - ``error_occurred(title, message)``: el cálculo falló.
    """

    state_changed = Signal(object)
    result_ready = Signal(object)
    error_occurred = Signal(str, str)

    def __init__(
        self,
        project_controller: ProjectController,
        *,
        runner: SimulationRunner | None = None,
        engine_factory: EngineFactory = create_pynec_engine,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._projects = project_controller
        self._runner = runner or SimulationRunner(parent=self)
        self._engine_factory = engine_factory
        self._state = PatternCalculationState.EMPTY
        self._analysis: RadiationPatternAnalysis | None = None
        self._last_error: str | None = None
        self._last_error_details: str | None = None
        self._job_id: int | None = None

        project_controller.project_opened.connect(self._on_project_opened)
        project_controller.project_closed.connect(self._on_project_closed)
        self._runner.succeeded.connect(self._on_succeeded)
        self._runner.failed.connect(self._on_failed)
        self._runner.cancelled.connect(self._on_cancelled)

    @property
    def state(self) -> PatternCalculationState:
        return self._state

    @property
    def is_busy(self) -> bool:
        return self._state in BUSY_STATES

    @property
    def analysis(self) -> RadiationPatternAnalysis | None:
        """Resultado vigente (solo en el estado RESULT)."""
        return self._analysis

    @property
    def last_error(self) -> str | None:
        return self._last_error

    @property
    def last_error_details(self) -> str | None:
        """Traceback del último error del worker, si lo hubo."""
        return self._last_error_details

    @property
    def runner(self) -> SimulationRunner:
        return self._runner

    def calculate(self) -> bool:
        """Inicia el cálculo del patrón del proyecto abierto.

        Returns:
            True si el cálculo empezó; False si no hay proyecto, ya hay
            un cálculo activo o el proyecto no define un patrón (en ese
            caso se emite ``error_occurred``).
        """
        opened = self._projects.opened_project
        if opened is None or self.is_busy or self._runner.is_busy:
            return False

        try:
            request = prepare_radiation_pattern_request(opened.project)
        except MissingRadiationPatternError as error:
            self._fail(str(error), None)
            return False

        engine_factory = self._engine_factory
        try:
            job_id = self._runner.submit(
                lambda token: _run_pattern_job(request, engine_factory, token)
            )
        except RuntimeError as error:
            # No se pudo iniciar el hilo: el runner no quedó ocupado y el
            # controlador pasa a ERROR, desde donde se puede reintentar.
            self._fail(f"{type(error).__name__}: {error}", traceback.format_exc())
            return False
        if job_id is None:
            return False

        self._job_id = job_id
        self._set_state(PatternCalculationState.CALCULATING)
        return True

    def cancel(self) -> bool:
        """Pide cancelar el cálculo activo (cooperativo).

        Returns:
            True si había un cálculo activo.
        """
        if self._state != PatternCalculationState.CALCULATING:
            return False
        self._runner.request_cancel()
        self._set_state(PatternCalculationState.CANCELLING)
        return True

    def shutdown(self) -> None:
        """Cancela y espera al worker (al cerrar la ventana).

        Bloquea hasta que termine la llamada nativa en curso, si la hay.
        """
        if self.is_busy:
            self._set_state(PatternCalculationState.CANCELLING)
        self._runner.shutdown()

    # -- Proyecto ---------------------------------------------------------

    def _on_project_opened(self, state: ProjectViewState) -> None:
        self._reset_for_new_project()

    def _on_project_closed(self) -> None:
        self._reset_for_new_project()

    def _reset_for_new_project(self) -> None:
        # El resultado y el error eran del proyecto anterior.
        self._analysis = None
        self._clear_error()
        if self.is_busy:
            # Su cálculo, si sigue activo, se descartará al terminar.
            self.cancel()
            return
        self._set_state(self._idle_state())

    # -- Runner -----------------------------------------------------------

    def _on_succeeded(self, job_id: int, analysis: object) -> None:
        if job_id != self._job_id:
            return
        self._job_id = None
        self._analysis = analysis
        self._clear_error()
        # Primero el resultado (la vista lo dibuja) y después el estado:
        # quien reaccione a RESULT ya encuentra el gráfico actualizado.
        self.result_ready.emit(analysis)
        self._set_state(PatternCalculationState.RESULT)

    def _on_failed(self, job_id: int, message: str, details: str) -> None:
        if job_id != self._job_id:
            return
        self._job_id = None
        self._fail(message, details)

    def _on_cancelled(self, job_id: int) -> None:
        if job_id != self._job_id:
            return
        self._job_id = None
        # El resultado vigente (si lo había) no se reemplaza.
        self._set_state(self._idle_state())

    # -- Auxiliares -------------------------------------------------------

    def _idle_state(self) -> PatternCalculationState:
        if self._analysis is not None:
            return PatternCalculationState.RESULT
        state = self._projects.state
        if state is not None and state.has_radiation_pattern:
            return PatternCalculationState.READY
        return PatternCalculationState.EMPTY

    def _fail(self, message: str, details: str | None) -> None:
        self._analysis = None
        self._last_error = message
        self._last_error_details = details
        self._set_state(PatternCalculationState.ERROR)
        self.error_occurred.emit(texts.CALCULATION_ERROR_TITLE, message)

    def _clear_error(self) -> None:
        self._last_error = None
        self._last_error_details = None

    def _set_state(self, state: PatternCalculationState) -> None:
        if state == self._state:
            return
        self._state = state
        self.state_changed.emit(state)
