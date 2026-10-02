"""`SimulationRunner`: QThread + worker, un trabajo por vez, cancelación.

Offscreen y sin pytest-qt: las señales se registran con conexiones a
métodos de un `QObject` del hilo principal y se espera procesando
eventos explícitamente. `QThread.terminate()` queda prohibido en todas
las pruebas de este módulo.
"""

import gc
import subprocess
import sys
import textwrap
import threading

import pytest

pytest.importorskip("PySide6.QtWidgets")

from qt_offscreen import configure_offscreen, offscreen_environment  # noqa: E402

configure_offscreen()

import shiboken6  # noqa: E402
from PySide6.QtCore import QCoreApplication, QEvent, QObject, QThread, Slot  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import yaas.gui.runner as runner_module  # noqa: E402
from pattern_fakes import WAIT_TIMEOUT_S, wait_until  # noqa: E402
from yaas.gui.runner import (  # noqa: E402
    CancellationToken,
    JobCancelled,
    SimulationRunner,
)

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


class Events(QObject):
    """Registra las señales del runner y el hilo donde llegaron."""

    def __init__(self, runner: SimulationRunner) -> None:
        super().__init__()
        self.items: list[tuple] = []
        self.threads: set[int] = set()
        runner.succeeded.connect(self.on_succeeded)
        runner.failed.connect(self.on_failed)
        runner.cancelled.connect(self.on_cancelled)
        runner.busy_changed.connect(self.on_busy)

    def _record(self, item):
        self.threads.add(threading.get_ident())
        self.items.append(item)

    @Slot(int, object)
    def on_succeeded(self, job_id, result):
        self._record(("succeeded", job_id, result))

    @Slot(int, str, str)
    def on_failed(self, job_id, message, details):
        self._record(("failed", job_id, message, details))

    @Slot(int)
    def on_cancelled(self, job_id):
        self._record(("cancelled", job_id))

    @Slot(bool)
    def on_busy(self, busy):
        self._record(("busy", busy))

    def outcomes(self):
        return [item for item in self.items if item[0] != "busy"]


@pytest.fixture
def runner():
    runner = SimulationRunner()
    yield runner
    runner.shutdown()
    assert runner.thread_count == 0


@pytest.fixture
def events(runner):
    return Events(runner)


def test_job_runs_in_a_worker_thread_and_reports_in_the_main_thread(
    runner, events
):
    job_threads = []

    def job(token):
        job_threads.append(threading.get_ident())
        return "result"

    job_id = runner.submit(job)

    assert job_id is not None
    assert runner.is_busy
    wait(lambda: events.outcomes())
    assert events.outcomes() == [("succeeded", job_id, "result")]
    assert job_threads and job_threads[0] != MAIN_THREAD
    assert events.threads == {MAIN_THREAD}
    assert not runner.is_busy
    assert [item for item in events.items if item[0] == "busy"] == [
        ("busy", True),
        ("busy", False),
    ]
    wait(lambda: runner.thread_count == 0)


def test_only_one_job_at_a_time(runner, events):
    gate = threading.Event()
    calls = []

    def job(token):
        calls.append(1)
        gate.wait(WAIT_TIMEOUT_S)
        return 1

    first = runner.submit(job)
    second = runner.submit(job)
    gate.set()
    wait(lambda: events.outcomes())

    assert first is not None
    assert second is None
    assert events.outcomes() == [("succeeded", first, 1)]
    assert calls == [1]


def test_a_new_job_can_start_after_the_previous_one_finished(runner, events):
    first = runner.submit(lambda token: "a")
    wait(lambda: len(events.outcomes()) == 1)
    second = runner.submit(lambda token: "b")
    wait(lambda: len(events.outcomes()) == 2)

    assert second != first
    assert events.outcomes()[1] == ("succeeded", second, "b")


def test_errors_are_reported_with_message_and_traceback(runner, events):
    def job(token):
        raise RuntimeError("engine exploded")

    job_id = runner.submit(job)
    wait(lambda: events.outcomes())

    ((kind, failed_id, message, details),) = events.outcomes()
    assert (kind, failed_id) == ("failed", job_id)
    assert message == "RuntimeError: engine exploded"
    assert "Traceback" in details and "engine exploded" in details


def test_cancel_during_an_uninterruptible_call_discards_its_result(
    runner, events
):
    gate = threading.Event()
    started = threading.Event()

    def job(token):
        # Simula una llamada nativa: no revisa el token mientras corre.
        started.set()
        gate.wait(WAIT_TIMEOUT_S)
        return "late result"

    job_id = runner.submit(job)
    assert started.wait(WAIT_TIMEOUT_S)

    assert runner.request_cancel()
    assert runner.is_cancelling
    # Todavía no terminó: la llamada en curso no se interrumpe.
    QApplication.processEvents()
    assert runner.is_busy
    gate.set()
    wait(lambda: events.outcomes())

    assert events.outcomes() == [("cancelled", job_id)]


def test_cooperative_cancellation_stops_between_calls(runner, events):
    steps = []
    first_step = threading.Event()
    proceed = threading.Event()

    def job(token):
        for step in range(5):
            token.raise_if_cancelled()
            steps.append(step)
            first_step.set()
            proceed.wait(WAIT_TIMEOUT_S)
        return "done"

    job_id = runner.submit(job)
    assert first_step.wait(WAIT_TIMEOUT_S)
    runner.request_cancel()
    proceed.set()
    wait(lambda: events.outcomes())

    assert events.outcomes() == [("cancelled", job_id)]
    assert steps == [0]


def test_an_error_after_cancellation_is_reported_as_cancelled(runner, events):
    gate = threading.Event()
    started = threading.Event()

    def job(token):
        started.set()
        gate.wait(WAIT_TIMEOUT_S)
        raise RuntimeError("after cancel")

    job_id = runner.submit(job)
    assert started.wait(WAIT_TIMEOUT_S)
    runner.request_cancel()
    gate.set()
    wait(lambda: events.outcomes())

    assert events.outcomes() == [("cancelled", job_id)]


def test_request_cancel_without_a_job(runner):
    assert runner.request_cancel() is False
    assert not runner.is_cancelling


def test_shutdown_cancels_waits_and_leaves_no_threads(runner, events):
    started = threading.Event()
    gate = threading.Event()

    def job(token):
        started.set()
        gate.wait(WAIT_TIMEOUT_S)
        return "discarded"

    job_id = runner.submit(job)
    assert started.wait(WAIT_TIMEOUT_S)
    # Libera la "llamada nativa" un poco después: shutdown debe esperar.
    release = threading.Timer(0.1, gate.set)
    release.start()

    runner.shutdown()

    assert runner.thread_count == 0
    assert not runner.is_busy
    assert events.outcomes() == [("cancelled", job_id)]
    # Las señales encoladas del worker llegan después y se ignoran.
    for _ in range(20):
        QApplication.processEvents()
    assert events.outcomes() == [("cancelled", job_id)]
    release.join()


def test_shutdown_without_a_job_is_harmless(runner, events):
    runner.shutdown()
    runner.shutdown()

    assert events.items == []


def test_shutdown_twice_with_an_active_job(runner, events):
    gate = threading.Event()
    started = threading.Event()

    def job(token):
        started.set()
        gate.wait(WAIT_TIMEOUT_S)
        return "discarded"

    job_id = runner.submit(job)
    assert started.wait(WAIT_TIMEOUT_S)
    threading.Timer(0.05, gate.set).start()

    runner.shutdown()
    runner.shutdown()

    assert runner.thread_count == 0
    assert not runner.is_busy
    # Un único cancelled: el segundo shutdown no hace nada.
    assert events.outcomes() == [("cancelled", job_id)]


def live_workers():
    """Workers cuyo objeto C++ sigue vivo.

    Un wrapper de Python puede sobrevivir a su objeto C++ (por ejemplo,
    si lo referencia el traceback de una excepción de otra prueba); lo
    que importa es que Qt haya destruido el objeto.
    """
    gc.collect()
    return [
        obj for obj in gc.get_objects()
        if type(obj) is runner_module._SimulationWorker and shiboken6.isValid(obj)
    ]


def drain_deferred_deletes():
    for _ in range(5):
        QApplication.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_every_path_releases_thread_and_worker(runner, events):
    def failing(token):
        raise RuntimeError("boom")

    gate = threading.Event()
    started = threading.Event()

    def blocking(token):
        started.set()
        gate.wait(WAIT_TIMEOUT_S)
        return "late"

    runner.submit(lambda token: "ok")
    wait(lambda: len(events.outcomes()) == 1 and runner.thread_count == 0)
    runner.submit(failing)
    wait(lambda: len(events.outcomes()) == 2 and runner.thread_count == 0)
    runner.submit(blocking)
    assert started.wait(WAIT_TIMEOUT_S)
    runner.request_cancel()
    gate.set()
    wait(lambda: len(events.outcomes()) == 3 and runner.thread_count == 0)
    gate.clear()
    started.clear()
    runner.submit(blocking)
    assert started.wait(WAIT_TIMEOUT_S)
    threading.Timer(0.05, gate.set).start()
    runner.shutdown()
    drain_deferred_deletes()

    assert [item[0] for item in events.outcomes()] == [
        "succeeded", "failed", "cancelled", "cancelled",
    ]
    assert runner.thread_count == 0
    assert live_workers() == []
    assert threading.active_count() == 1


class FailingStartThread(QThread):
    """Simula que el sistema no pudo crear el hilo: start() no lo inicia."""

    def start(self, *args):
        pass


def test_thread_that_cannot_start_leaves_the_runner_usable(
    runner, events, monkeypatch
):
    monkeypatch.setattr(runner_module, "QThread", FailingStartThread)

    with pytest.raises(RuntimeError, match="Could not start"):
        runner.submit(lambda token: "never")

    assert not runner.is_busy
    assert runner.thread_count == 0
    assert events.items == []

    monkeypatch.undo()
    job_id = runner.submit(lambda token: "after")
    wait(lambda: events.outcomes())
    assert events.outcomes() == [("succeeded", job_id, "after")]


def test_worker_that_cannot_be_created_leaves_the_runner_usable(
    runner, events, monkeypatch
):
    def broken_worker(*args):
        raise RuntimeError("worker failed")

    monkeypatch.setattr(runner_module, "_SimulationWorker", broken_worker)

    with pytest.raises(RuntimeError, match="worker failed"):
        runner.submit(lambda token: "never")

    assert not runner.is_busy
    assert runner.thread_count == 0
    assert events.items == []


class AbortJob(BaseException):
    """Una BaseException que el worker no captura como Exception."""


def test_worker_ending_without_a_result_is_reported_as_failed(runner, events):
    def job(token):
        raise AbortJob()

    job_id = runner.submit(job)
    wait(lambda: events.outcomes())

    ((kind, failed_id, message, _details),) = events.outcomes()
    assert (kind, failed_id) == ("failed", job_id)
    assert "ended without a result" in message
    assert not runner.is_busy
    wait(lambda: runner.thread_count == 0)


def test_cancellation_token():
    token = CancellationToken()
    token.raise_if_cancelled()

    token.cancel()

    assert token.is_cancelled
    with pytest.raises(JobCancelled):
        token.raise_if_cancelled()


STRESS_JOBS = 1500


def test_many_short_jobs_do_not_crash_the_process():
    # Regresión: soltar el worker/QThread mientras el hilo todavía
    # terminaba (justo después de finished) provocaba access violation o
    # abort al encadenar miles de trabajos cortos. En un subproceso, para
    # que un fallo nativo no tumbe a pytest.
    code = textwrap.dedent(f"""
        import faulthandler, sys
        faulthandler.enable()
        from PySide6.QtWidgets import QApplication
        from yaas.gui.runner import SimulationRunner
        app = QApplication([])
        runner = SimulationRunner()
        done = []
        runner.succeeded.connect(lambda job_id, result: done.append(job_id))
        for index in range({STRESS_JOBS}):
            while runner.submit(lambda token: index) is None:
                app.processEvents()
            while len(done) <= index:
                app.processEvents()
        runner.shutdown()
        assert runner.thread_count == 0, runner.thread_count
        print("ok", len(done))
    """)
    result = subprocess.run(
        [sys.executable, "-B", "-c", code],
        env=offscreen_environment(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert f"ok {STRESS_JOBS}" in result.stdout
