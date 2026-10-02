"""Cálculo de patrones desde `MainWindow` con motores falsos (offscreen).

Ningún diálogo real: los errores van a un presentador falso. Los
gráficos se verifican por estructura (tipo de ejes, datos), nunca por
capturas.
"""

import math
import os
import threading
from pathlib import Path

import pytest

pytest.importorskip("PySide6.QtWidgets")
pytest.importorskip("matplotlib")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QThread  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from pattern_fakes import (  # noqa: E402
    WAIT_TIMEOUT_S,
    EngineFactory,
    FakeEngine,
    project_with_pattern,
    wait_until,
)
from yaas.application import summarize_radiation_pattern  # noqa: E402
from yaas.domain import AngularSweep, RadiationPatternResult  # noqa: E402
from yaas.gui import texts  # noqa: E402
from yaas.gui.controllers.pattern import PatternCalculationState as State  # noqa: E402
from yaas.gui.widgets.radiation_pattern_plot import EMPTY_MESSAGE  # noqa: E402
from yaas.gui.window import MainWindow  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
EXAMPLES = REPO / "examples"
V1 = EXAMPLES / "dipole-20m.yaas"
V4 = EXAMPLES / "dipole-20m-radiation-pattern.yaas"


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


class Gui:
    def __init__(self, engine: FakeEngine | None = None) -> None:
        self.errors: list[tuple[str, str]] = []
        self.factory = EngineFactory(engine)
        self.window = MainWindow(
            engine_factory=self.factory,
            error_presenter=lambda title, message: self.errors.append(
                (title, message)
            ),
        )

    @property
    def patterns(self):
        return self.window.pattern_controller

    def actions(self) -> dict[str, bool]:
        window = self.window
        return {
            "open": window.open_action.isEnabled(),
            "close": window.close_project_action.isEnabled(),
            "calculate": window.calculate_pattern_action.isEnabled(),
            "cancel": window.cancel_calculation_action.isEnabled(),
            "exit": window.exit_action.isEnabled(),
        }

    def engine_started(self) -> bool:
        return self.factory.engine.started.wait(WAIT_TIMEOUT_S)

    def status(self) -> str:
        return self.window.calculation_status.text()

    def close(self) -> None:
        self.window.close()
        assert self.patterns.runner.thread_count == 0


@pytest.fixture
def gui():
    gui = Gui()
    yield gui
    gui.close()


@pytest.fixture
def blocked():
    gate = threading.Event()
    gui = Gui(FakeEngine(gate=gate))
    gui.gate = gate
    yield gui
    gate.set()
    gui.close()


def test_calculate_menu(gui):
    actions = [action.text() for action in gui.window.calculate_menu.actions()]
    menus = [action.text() for action in gui.window.menuBar().actions()]

    assert menus == ["&File", "&Calculate"]
    assert actions == ["Radiation &pattern", "&Cancel calculation"]


def test_empty_state(gui):
    assert gui.patterns.state is State.EMPTY
    assert gui.actions() == {
        "open": True,
        "close": False,
        "calculate": False,
        "cancel": False,
        "exit": True,
    }
    assert gui.status() == texts.CALCULATION_STATUS_EMPTY


def test_project_without_pattern_cannot_be_calculated(gui):
    gui.window.open_project_path(V1)

    assert gui.patterns.state is State.EMPTY
    assert not gui.actions()["calculate"]
    assert gui.status() == texts.CALCULATION_STATUS_EMPTY


def test_ready_state(gui):
    gui.window.open_project_path(V4)

    assert gui.patterns.state is State.READY
    assert gui.actions() == {
        "open": True,
        "close": True,
        "calculate": True,
        "cancel": False,
        "exit": True,
    }
    assert gui.status() == texts.CALCULATION_STATUS_READY
    assert gui.window.radiation_pattern_plot.adapter.axes is None


def test_calculating_disables_incompatible_actions(blocked):
    blocked.window.open_project_path(V4)

    blocked.window.calculate_pattern_action.trigger()

    assert blocked.patterns.state is State.CALCULATING
    assert blocked.actions() == {
        "open": False,
        "close": False,
        "calculate": False,
        "cancel": True,
        "exit": True,
    }
    assert blocked.status() == texts.CALCULATION_STATUS_CALCULATING
    # Abrir otro proyecto por el diálogo tampoco es posible.
    assert blocked.window.choose_and_open_project() is False

    blocked.gate.set()
    wait(lambda: blocked.patterns.state is State.RESULT)
    assert blocked.actions()["calculate"]
    assert blocked.actions()["open"]


def test_result_draws_the_vertical_cut(gui):
    gui.window.open_project_path(V4)

    gui.window.calculate_pattern_action.trigger()
    wait(lambda: gui.patterns.state is State.RESULT)

    plot = gui.window.radiation_pattern_plot
    axes = plot.adapter.axes
    assert axes is not None and axes.name == "rectilinear"
    (line,) = axes.get_lines()
    assert list(line.get_xdata()) == [float(theta) for theta in range(181)]
    assert "Vertical cut (phi = 0 deg)" in axes.get_title()
    maximum = gui.patterns.analysis.summary.maximum
    assert gui.status() == (
        texts.CALCULATION_STATUS_RESULT.format(
            gain=maximum.gain_db, theta=maximum.theta_deg, phi=maximum.phi_deg
        )
        + " "
        + texts.CALCULATION_STATUS_VERTICAL_CUT.format(angle=0.0)
    )
    assert plot.status_text.startswith("181 points, 0 null")
    assert gui.errors == []


def test_result_draws_the_azimuth_cut(gui, tmp_path):
    path = project_with_pattern(
        tmp_path, AngularSweep(90.0, 1, 0.0), AngularSweep(0.0, 37, 10.0)
    )
    gui.window.open_project_path(path)

    gui.patterns.calculate()
    wait(lambda: gui.patterns.state is State.RESULT)

    axes = gui.window.radiation_pattern_plot.adapter.axes
    assert axes.name == "polar"
    assert "Azimuth cut (theta = 90 deg)" in axes.get_title()


def test_full_grid_starts_with_the_first_vertical_cut(gui, tmp_path):
    path = project_with_pattern(
        tmp_path, AngularSweep(0.0, 19, 10.0), AngularSweep(0.0, 4, 90.0)
    )
    gui.window.open_project_path(path)

    gui.patterns.calculate()
    wait(lambda: gui.patterns.state is State.RESULT)

    axes = gui.window.radiation_pattern_plot.adapter.axes
    assert axes.name == "rectilinear"
    assert "phi = 0 deg" in axes.get_title()
    assert gui.status().endswith(
        texts.CALCULATION_STATUS_VERTICAL_CUT.format(angle=0.0)
    )


def test_engine_error_is_presented_and_clears_the_plot():
    gui = Gui(FakeEngine(error=RuntimeError("NEC2++ failed")))
    try:
        gui.window.open_project_path(V4)
        gui.patterns.calculate()
        wait(lambda: gui.patterns.state is State.ERROR)

        assert gui.errors == [
            (texts.CALCULATION_ERROR_TITLE, "RuntimeError: NEC2++ failed")
        ]
        assert gui.status() == "Calculation failed: RuntimeError: NEC2++ failed"
        assert gui.window.radiation_pattern_plot.adapter.axes is None
        assert gui.window.radiation_pattern_plot.status_text == EMPTY_MESSAGE
        # Se puede reintentar.
        assert gui.actions()["calculate"]
    finally:
        gui.close()


def test_cancel_action_shows_cancelling_and_discards_the_result(blocked):
    blocked.window.open_project_path(V4)
    blocked.patterns.calculate()
    assert blocked.engine_started()

    blocked.window.cancel_calculation_action.trigger()

    assert blocked.patterns.state is State.CANCELLING
    assert "cannot be interrupted" in blocked.status()
    assert blocked.actions() == {
        "open": False,
        "close": False,
        "calculate": False,
        "cancel": False,
        "exit": True,
    }

    blocked.gate.set()
    wait(lambda: blocked.patterns.state is State.READY)
    assert blocked.window.radiation_pattern_plot.adapter.axes is None
    assert blocked.status() == texts.CALCULATION_STATUS_READY


def test_closing_the_project_clears_the_result(gui):
    gui.window.open_project_path(V4)
    gui.patterns.calculate()
    wait(lambda: gui.patterns.state is State.RESULT)

    gui.window.close_project_action.trigger()

    assert gui.patterns.state is State.EMPTY
    assert gui.patterns.analysis is None
    assert gui.window.radiation_pattern_plot.adapter.axes is None


def test_closing_the_window_during_calculation_finishes_cleanly(blocked):
    blocked.window.open_project_path(V4)
    blocked.window.show()
    blocked.patterns.calculate()
    assert blocked.engine_started()
    # La "llamada nativa" termina poco después: el cierre debe esperarla.
    threading.Timer(0.1, blocked.gate.set).start()

    blocked.window.close()

    assert not blocked.window.isVisible()
    assert blocked.patterns.runner.thread_count == 0
    assert not blocked.patterns.is_busy
    assert blocked.patterns.analysis is None
    for _ in range(20):
        QApplication.processEvents()
    # El resultado tardío se descartó.
    assert blocked.window.radiation_pattern_plot.adapter.axes is None


MAIN_THREAD = threading.get_ident()


def test_window_and_plot_are_updated_only_in_the_main_thread(gui, monkeypatch):
    plot = gui.window.radiation_pattern_plot
    seen = []
    for name in ("show_vertical", "show_azimuth", "clear"):
        original = getattr(plot, name)

        def record(*args, _original=original, _name=name, **kwargs):
            seen.append((_name, threading.get_ident()))
            return _original(*args, **kwargs)

        monkeypatch.setattr(plot, name, record)
    status = gui.window.calculation_status
    original_set_text = status.setText

    def record_status(text):
        seen.append(("status", threading.get_ident()))
        return original_set_text(text)

    monkeypatch.setattr(status, "setText", record_status)

    gui.window.open_project_path(V4)
    gui.patterns.calculate()
    wait(lambda: gui.patterns.state is State.RESULT)

    assert ("show_vertical", MAIN_THREAD) in seen
    assert {thread for _, thread in seen} == {MAIN_THREAD}
    # El motor, en cambio, corrió en el worker.
    assert gui.factory.engine.call_threads[0] != MAIN_THREAD


def plotted_line(gui):
    (line,) = gui.window.radiation_pattern_plot.adapter.axes.get_lines()
    return list(line.get_xdata()), list(line.get_ydata())


def test_cancelled_recalculation_keeps_the_previous_result_and_plot():
    gate = threading.Event()
    gate.set()
    gui = Gui(FakeEngine(gate=gate))
    try:
        gui.window.open_project_path(V4)
        gui.patterns.calculate()
        wait(lambda: gui.patterns.state is State.RESULT)
        previous = gui.patterns.analysis
        previous_line = plotted_line(gui)
        previous_status = gui.status()
        previous_plot_status = gui.window.radiation_pattern_plot.status_text

        gate.clear()
        gui.factory.engine.started.clear()
        gui.patterns.calculate()
        assert gui.engine_started()
        gui.window.cancel_calculation_action.trigger()
        gate.set()
        wait(lambda: not gui.patterns.is_busy)

        assert gui.patterns.state is State.RESULT
        assert gui.patterns.analysis is previous
        assert plotted_line(gui) == previous_line
        assert gui.status() == previous_status
        assert gui.window.radiation_pattern_plot.status_text == previous_plot_status
    finally:
        gate.set()
        gui.close()


def test_plot_floor_changes_only_the_drawing_not_the_result():
    def result_with_low_and_null_gains(request):
        theta = request.theta.angles_deg
        gains = [5.0, -80.0, None] + [1.0] * (len(theta) - 3)
        return RadiationPatternResult(
            frequency_mhz=request.frequency_mhz,
            theta_angles_deg=theta,
            phi_angles_deg=request.phi.angles_deg,
            gain_db=tuple((gain,) for gain in gains),
        )

    gui = Gui(FakeEngine(result=result_with_low_and_null_gains))
    try:
        gui.window.open_project_path(V4)
        gui.patterns.calculate()
        wait(lambda: gui.patterns.state is State.RESULT)

        analysis = gui.patterns.analysis
        # Los valores originales siguen intactos (CSV, resumen, etc.).
        assert analysis.result.gain_db[1] == (-80.0,)
        assert analysis.result.gain_db[2] == (None,)
        assert analysis.summary == summarize_radiation_pattern(analysis.result)
        assert analysis.summary.null_points == 1
        # Solo el dibujo usa el piso: máximo 5 dBi -> piso -35 dBi.
        _, drawn = plotted_line(gui)
        assert drawn[1] == 5.0 - 40.0
        assert math.isnan(drawn[2])
        assert gui.window.radiation_pattern_plot.status_text == (
            "181 points, 1 null, 1 drawn at the -35 dBi floor."
        )
    finally:
        gui.close()


def test_closing_the_window_twice_is_harmless(blocked):
    blocked.window.open_project_path(V4)
    blocked.window.show()
    blocked.patterns.calculate()
    assert blocked.engine_started()
    threading.Timer(0.05, blocked.gate.set).start()

    blocked.window.close()
    blocked.window.close()

    assert blocked.patterns.runner.thread_count == 0
    assert not blocked.patterns.is_busy
