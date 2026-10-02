"""`RadiationPatternController` con motores falsos (offscreen).

El motor falso se crea dentro del worker, como el real; cuando se pasa
un ``gate``, su "llamada nativa" bloquea hasta que la prueba lo libere,
para ejercitar la cancelación durante una llamada en curso.
"""

import os
import subprocess
import sys
import textwrap
import threading
from pathlib import Path

import pytest

pytest.importorskip("PySide6.QtWidgets")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QThread  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import yaas.gui.controllers.pattern as pattern_module  # noqa: E402
from pattern_fakes import (  # noqa: E402
    WAIT_TIMEOUT_S,
    EngineFactory,
    FakeEngine,
    pattern_result,
    wait_until,
)
from yaas.application import summarize_radiation_pattern  # noqa: E402
from yaas.gui import texts  # noqa: E402
from yaas.gui.controllers.pattern import (  # noqa: E402
    PatternCalculationState as State,
    RadiationPatternController,
)
from yaas.gui.controllers.project import ProjectController  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
EXAMPLES = REPO / "examples"
V1 = EXAMPLES / "dipole-20m.yaas"
V4 = EXAMPLES / "dipole-20m-radiation-pattern.yaas"
MAIN_THREAD = threading.get_ident()


@pytest.fixture(scope="module", autouse=True)
def application():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def forbid_terminate(monkeypatch):
    def terminate(self):
        raise AssertionError("QThread.terminate() must never be used")

    monkeypatch.setattr(QThread, "terminate", terminate)


def wait(predicate):
    wait_until(predicate, QApplication.processEvents)


class Harness:
    """Proyecto, controlador de patrones y registro de señales."""

    def __init__(self, engine: FakeEngine | None = None) -> None:
        self.factory = EngineFactory(engine)
        self.projects = ProjectController()
        self.patterns = RadiationPatternController(
            self.projects, engine_factory=self.factory
        )
        self.states: list[State] = []
        self.results: list[object] = []
        self.errors: list[tuple[str, str]] = []
        self.patterns.state_changed.connect(self.states.append)
        self.patterns.result_ready.connect(self.results.append)
        self.patterns.error_occurred.connect(
            lambda title, message: self.errors.append((title, message))
        )

    @property
    def engine(self) -> FakeEngine:
        return self.factory.engine

    def finish(self) -> None:
        self.patterns.shutdown()
        assert self.patterns.runner.thread_count == 0


@pytest.fixture
def harness():
    harness = Harness()
    yield harness
    harness.finish()


@pytest.fixture
def blocked():
    gate = threading.Event()
    harness = Harness(FakeEngine(gate=gate))
    harness.gate = gate
    yield harness
    gate.set()
    harness.finish()


def test_states_follow_the_open_project(harness):
    assert harness.patterns.state is State.EMPTY

    harness.projects.open_project(V1)
    assert harness.patterns.state is State.EMPTY  # sin patrón

    harness.projects.open_project(V4)
    assert harness.patterns.state is State.READY

    harness.projects.close_project()
    assert harness.patterns.state is State.EMPTY
    assert harness.states == [State.READY, State.EMPTY]


def test_successful_calculation(harness):
    harness.projects.open_project(V4)

    assert harness.patterns.calculate() is True
    assert harness.patterns.state is State.CALCULATING
    wait(lambda: harness.patterns.state is State.RESULT)

    (analysis,) = harness.results
    request = harness.projects.opened_project.project.to_radiation_pattern_request()
    # Resultado y resumen vienen de calculate_radiation_pattern.
    assert analysis.result == pattern_result(request)
    assert analysis.summary == summarize_radiation_pattern(analysis.result)
    assert harness.patterns.analysis is analysis
    assert harness.states == [State.READY, State.CALCULATING, State.RESULT]
    assert harness.engine.calls == [request]
    assert harness.errors == []


def test_engine_is_created_and_run_in_the_worker_thread(harness):
    harness.projects.open_project(V4)
    harness.patterns.calculate()
    wait(lambda: harness.patterns.state is State.RESULT)

    (created_in,) = harness.factory.created_in
    assert created_in != MAIN_THREAD
    assert harness.engine.call_threads == [created_in]


def test_reuses_the_application_workflow(harness, monkeypatch):
    calls = []
    prepare = pattern_module.prepare_radiation_pattern_request
    calculate = pattern_module.calculate_radiation_pattern

    def spy_prepare(project):
        calls.append(("prepare", threading.get_ident()))
        return prepare(project)

    def spy_calculate(request, *, engine):
        calls.append(("calculate", threading.get_ident()))
        return calculate(request, engine=engine)

    monkeypatch.setattr(pattern_module, "prepare_radiation_pattern_request", spy_prepare)
    monkeypatch.setattr(pattern_module, "calculate_radiation_pattern", spy_calculate)
    harness.projects.open_project(V4)

    harness.patterns.calculate()
    wait(lambda: harness.patterns.state is State.RESULT)

    assert [name for name, _ in calls] == ["prepare", "calculate"]
    # La validación corre en el hilo principal; el cálculo, en el worker.
    assert calls[0][1] == MAIN_THREAD
    assert calls[1][1] != MAIN_THREAD


def test_calculate_without_project_does_nothing(harness):
    assert harness.patterns.calculate() is False
    assert harness.factory.created_in == []
    assert harness.states == []


def test_project_without_pattern_is_rejected_without_engine(harness):
    harness.projects.open_project(V1)

    assert harness.patterns.calculate() is False

    assert harness.patterns.state is State.ERROR
    ((title, message),) = harness.errors
    assert title == texts.CALCULATION_ERROR_TITLE
    assert message == harness.patterns.last_error
    assert harness.factory.created_in == []
    assert harness.patterns.runner.thread_count == 0


def test_engine_errors_reach_the_error_state():
    harness = Harness(FakeEngine(error=RuntimeError("NEC2++ failed")))
    try:
        harness.projects.open_project(V4)
        harness.patterns.calculate()
        wait(lambda: harness.patterns.state is State.ERROR)

        assert harness.errors == [
            (texts.CALCULATION_ERROR_TITLE, "RuntimeError: NEC2++ failed")
        ]
        assert "Traceback" in harness.patterns.last_error_details
        assert harness.patterns.analysis is None
        assert harness.results == []
    finally:
        harness.finish()


def test_recalculating_after_an_error_works():
    engine = FakeEngine(error=RuntimeError("first"))
    harness = Harness(engine)
    try:
        harness.projects.open_project(V4)
        harness.patterns.calculate()
        wait(lambda: harness.patterns.state is State.ERROR)

        engine.error = None
        assert harness.patterns.calculate()
        wait(lambda: harness.patterns.state is State.RESULT)
        assert harness.patterns.last_error is None
    finally:
        harness.finish()


def test_second_calculation_is_rejected_while_running(blocked):
    blocked.projects.open_project(V4)

    assert blocked.patterns.calculate() is True
    assert blocked.patterns.calculate() is False
    assert blocked.engine.started.wait(WAIT_TIMEOUT_S)
    assert blocked.patterns.calculate() is False

    blocked.gate.set()
    wait(lambda: blocked.patterns.state is State.RESULT)
    assert len(blocked.factory.created_in) == 1
    assert len(blocked.results) == 1


def test_cancel_during_the_native_call_discards_the_result(blocked):
    blocked.projects.open_project(V4)
    blocked.patterns.calculate()
    assert blocked.engine.started.wait(WAIT_TIMEOUT_S)

    assert blocked.patterns.cancel() is True
    assert blocked.patterns.state is State.CANCELLING
    assert blocked.patterns.cancel() is False

    blocked.gate.set()
    wait(lambda: blocked.patterns.state is State.READY)

    assert blocked.results == []
    assert blocked.patterns.analysis is None
    assert blocked.engine.calls  # la llamada terminó, pero se descartó
    assert blocked.states[-3:] == [State.CALCULATING, State.CANCELLING, State.READY]


def test_cancel_keeps_the_previous_result():
    gate = threading.Event()
    gate.set()
    harness = Harness(FakeEngine(gate=gate))
    try:
        harness.projects.open_project(V4)
        harness.patterns.calculate()
        wait(lambda: harness.patterns.state is State.RESULT)
        previous = harness.patterns.analysis

        gate.clear()
        harness.engine.started.clear()
        harness.patterns.calculate()
        assert harness.engine.started.wait(WAIT_TIMEOUT_S)
        harness.patterns.cancel()
        gate.set()
        wait(lambda: not harness.patterns.is_busy)

        assert harness.patterns.state is State.RESULT
        assert harness.patterns.analysis is previous
        assert len(harness.results) == 1
    finally:
        gate.set()
        harness.finish()


def test_cancel_without_calculation(harness):
    harness.projects.open_project(V4)

    assert harness.patterns.cancel() is False
    assert harness.patterns.state is State.READY


def test_closing_the_project_during_calculation_discards_the_result(blocked):
    blocked.projects.open_project(V4)
    blocked.patterns.calculate()
    assert blocked.engine.started.wait(WAIT_TIMEOUT_S)

    blocked.projects.close_project()
    assert blocked.patterns.state is State.CANCELLING

    blocked.gate.set()
    wait(lambda: not blocked.patterns.is_busy)
    assert blocked.patterns.state is State.EMPTY
    assert blocked.results == []


def test_opening_another_project_during_calculation(blocked):
    blocked.projects.open_project(V4)
    blocked.patterns.calculate()
    assert blocked.engine.started.wait(WAIT_TIMEOUT_S)

    blocked.projects.open_project(V4)
    blocked.gate.set()
    wait(lambda: not blocked.patterns.is_busy)

    # El resultado era del proyecto anterior: se descarta.
    assert blocked.patterns.state is State.READY
    assert blocked.results == []


def test_shutdown_during_calculation_leaves_no_threads(blocked):
    blocked.projects.open_project(V4)
    blocked.patterns.calculate()
    assert blocked.engine.started.wait(WAIT_TIMEOUT_S)
    threading.Timer(0.1, blocked.gate.set).start()

    blocked.patterns.shutdown()

    assert blocked.patterns.runner.thread_count == 0
    assert not blocked.patterns.is_busy
    assert blocked.results == []


def test_engine_creation_failure_returns_to_a_usable_state():
    harness = Harness()
    harness.factory.error = ImportError("PyNEC is broken")
    try:
        harness.projects.open_project(V4)

        assert harness.patterns.calculate()
        wait(lambda: not harness.patterns.is_busy)

        assert harness.patterns.state is State.ERROR
        assert harness.errors == [
            (texts.CALCULATION_ERROR_TITLE, "ImportError: PyNEC is broken")
        ]
        # La creación ocurrió (y falló) dentro del worker.
        assert harness.factory.created_in[0] != MAIN_THREAD
        harness.factory.error = None
        assert harness.patterns.calculate()
        wait(lambda: harness.patterns.state is State.RESULT)
    finally:
        harness.finish()


class FailingStartThread(QThread):
    def start(self, *args):
        pass


def test_thread_start_failure_returns_to_a_usable_state(harness, monkeypatch):
    import yaas.gui.runner as runner_module

    harness.projects.open_project(V4)
    monkeypatch.setattr(runner_module, "QThread", FailingStartThread)

    assert harness.patterns.calculate() is False

    assert harness.patterns.state is State.ERROR
    assert "Could not start the calculation thread" in harness.patterns.last_error
    assert not harness.patterns.runner.is_busy
    assert harness.factory.created_in == []

    monkeypatch.undo()
    assert harness.patterns.calculate()
    wait(lambda: harness.patterns.state is State.RESULT)


def test_late_error_of_a_cancelled_job_is_discarded():
    gate = threading.Event()
    harness = Harness(FakeEngine(gate=gate, error=RuntimeError("late")))
    try:
        harness.projects.open_project(V4)
        harness.patterns.calculate()
        assert harness.engine.started.wait(WAIT_TIMEOUT_S)
        harness.patterns.cancel()
        gate.set()
        wait(lambda: not harness.patterns.is_busy)

        assert harness.patterns.state is State.READY
        assert harness.errors == []
        assert harness.patterns.last_error is None
    finally:
        gate.set()
        harness.finish()


def test_shutdown_twice_with_an_active_calculation(blocked):
    blocked.projects.open_project(V4)
    blocked.patterns.calculate()
    assert blocked.engine.started.wait(WAIT_TIMEOUT_S)
    threading.Timer(0.05, blocked.gate.set).start()

    blocked.patterns.shutdown()
    states_after_first = list(blocked.states)
    blocked.patterns.shutdown()

    assert blocked.patterns.state is State.READY
    assert blocked.states == states_after_first
    assert blocked.patterns.runner.thread_count == 0
    assert blocked.results == []


def test_shutdown_without_calculation_is_harmless(harness):
    harness.patterns.shutdown()
    harness.patterns.shutdown()

    assert harness.states == []
    assert harness.patterns.state is State.EMPTY


def test_controller_import_and_project_do_not_load_pynec():
    code = textwrap.dedent("""
        import sys, threading
        from PySide6.QtWidgets import QApplication
        application = QApplication([])
        from yaas.gui.controllers.project import ProjectController
        from yaas.gui.controllers.pattern import RadiationPatternController
        projects = ProjectController()
        patterns = RadiationPatternController(projects)
        assert projects.open_project("examples/dipole-20m-radiation-pattern.yaas")
        loaded = [n for n in ("PyNEC", "yaas.engines.pynec") if n in sys.modules]
        assert not loaded, loaded
        assert threading.active_count() == 1
    """)
    result = subprocess.run(
        [sys.executable, "-B", "-c", code],
        cwd=REPO,
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )

    assert result.returncode == 0, result.stdout + result.stderr
