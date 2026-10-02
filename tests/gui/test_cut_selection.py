"""Selector de cortes: controlador, controles y gráfico (offscreen).

Motores falsos con grillas irregulares: así se comprueba que se usan
los ángulos reales del resultado. Cambiar de corte nunca debe volver a
ejecutar el motor. Los gráficos se verifican por estructura (tipo de
ejes, datos de la línea, título), nunca por capturas.
"""

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
from yaas.domain import AngularSweep, RadiationPatternResult  # noqa: E402
from yaas.gui import texts  # noqa: E402
from yaas.gui.controllers.pattern import PatternCalculationState as State  # noqa: E402
from yaas.gui.controllers.pattern_cut import CutKind, CutSelection  # noqa: E402
from yaas.gui.window import MainWindow  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
V1 = REPO / "examples" / "dipole-20m.yaas"
V4 = REPO / "examples" / "dipole-20m-radiation-pattern.yaas"

# Grilla irregular devuelta por el motor falso: si la GUI reconstruyera
# los ángulos desde inicio y paso, no coincidirían con estos.
THETA = (0.0, 7.5, 30.0, 90.0)
PHI = (0.0, 45.0, 100.0, 270.0, 359.0)


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


def irregular_result(theta, phi):
    """Resultado con los ángulos dados; la ganancia identifica la celda."""

    def build(request):
        return RadiationPatternResult(
            frequency_mhz=request.frequency_mhz,
            theta_angles_deg=theta,
            phi_angles_deg=phi,
            gain_db=tuple(
                tuple(float(10 * i + j) for j in range(len(phi)))
                for i in range(len(theta))
            ),
        )

    return build


class Gui:
    def __init__(self, theta=THETA, phi=PHI, gate=None) -> None:
        self.errors: list[tuple[str, str]] = []
        self.engine = FakeEngine(gate=gate, result=irregular_result(theta, phi))
        self.factory = EngineFactory(self.engine)
        self.window = MainWindow(
            engine_factory=self.factory,
            error_presenter=lambda title, message: self.errors.append(
                (title, message)
            ),
        )
        self.selections: list[CutSelection | None] = []
        self.patterns.selection_changed.connect(self.selections.append)

    @property
    def patterns(self):
        return self.window.pattern_controller

    @property
    def selector(self):
        return self.window.cut_selector

    @property
    def axes(self):
        return self.window.radiation_pattern_plot.adapter.axes

    def calculate(self, path) -> None:
        self.window.open_project_path(path)
        assert self.patterns.calculate()
        wait(lambda: not self.patterns.is_busy)

    def kind_items(self) -> list[str]:
        combo = self.selector.kind_combo
        return [combo.itemText(i) for i in range(combo.count())]

    def angle_items(self) -> list[str]:
        combo = self.selector.angle_combo
        return [combo.itemText(i) for i in range(combo.count())]

    def choose_kind(self, kind: CutKind) -> None:
        combo = self.selector.kind_combo
        combo_index = self.patterns.selection.available_kinds.index(kind)
        combo.setCurrentIndex(combo_index)
        combo.activated.emit(combo_index)

    def choose_angle(self, index: int) -> None:
        combo = self.selector.angle_combo
        combo.setCurrentIndex(index)
        combo.activated.emit(index)

    def line_data(self):
        (line,) = self.axes.get_lines()
        return list(line.get_xdata()), list(line.get_ydata())

    def close(self) -> None:
        self.window.close()
        assert self.patterns.runner.thread_count == 0


@pytest.fixture
def full_grid(tmp_path):
    # La grilla del proyecto solo define cuántos ángulos pide; el motor
    # falso devuelve THETA x PHI.
    path = project_with_pattern(
        tmp_path, AngularSweep(0.0, 4, 30.0), AngularSweep(0.0, 5, 90.0)
    )
    gui = Gui()
    gui.calculate(path)
    assert gui.patterns.state is State.RESULT
    yield gui
    gui.close()


# -- Formas de la matriz -----------------------------------------------------


def test_theta_sweep_offers_only_the_vertical_cut():
    gui = Gui(theta=THETA, phi=(0.0,))
    try:
        gui.calculate(V4)

        assert gui.kind_items() == [texts.CUT_KIND_VERTICAL]
        assert gui.angle_items() == ["0"]
        assert gui.selector.angle_label == "phi (deg)"
        assert not gui.selector.kind_combo.isEnabled()
        assert not gui.selector.angle_combo.isEnabled()
        assert gui.axes.name == "rectilinear"
        assert gui.line_data()[0] == list(THETA)
    finally:
        gui.close()


def test_phi_sweep_offers_only_the_azimuth_cut(tmp_path):
    path = project_with_pattern(
        tmp_path, AngularSweep(90.0, 1, 0.0), AngularSweep(0.0, 5, 90.0)
    )
    gui = Gui(theta=(90.0,), phi=PHI)
    try:
        gui.calculate(path)

        assert gui.kind_items() == [texts.CUT_KIND_AZIMUTH]
        assert gui.angle_items() == ["90"]
        assert gui.selector.angle_label == "theta (deg)"
        assert not gui.selector.kind_combo.isEnabled()
        assert not gui.selector.angle_combo.isEnabled()
        assert gui.axes.name == "polar"
        assert "Azimuth cut (theta = 90 deg)" in gui.axes.get_title()
    finally:
        gui.close()


def test_full_grid_offers_both_modes(full_grid):
    gui = full_grid

    assert gui.kind_items() == [texts.CUT_KIND_VERTICAL, texts.CUT_KIND_AZIMUTH]
    assert gui.selector.kind_combo.isEnabled()
    assert gui.selector.angle_combo.isEnabled()
    # Determinista: vertical en el primer phi.
    assert gui.selector.kind_combo.currentIndex() == 0
    assert gui.selector.angle_combo.currentIndex() == 0
    assert gui.axes.name == "rectilinear"


def test_single_direction_is_a_stable_one_point_vertical_plot(tmp_path):
    path = project_with_pattern(
        tmp_path, AngularSweep(90.0, 1, 0.0), AngularSweep(0.0, 1, 0.0)
    )
    gui = Gui(theta=(90.0,), phi=(0.0,))
    try:
        gui.calculate(path)

        assert gui.kind_items() == [texts.CUT_KIND_VERTICAL]
        assert gui.angle_items() == ["0"]
        assert not gui.selector.kind_combo.isEnabled()
        assert not gui.selector.angle_combo.isEnabled()
        assert gui.axes.name == "rectilinear"
        assert gui.line_data() == ([90.0], [0.0])
    finally:
        gui.close()


# -- Ángulos reales, índices y modos -----------------------------------------


def test_selectors_list_the_real_angles(full_grid):
    gui = full_grid

    assert gui.angle_items() == ["0", "45", "100", "270", "359"]
    gui.choose_kind(CutKind.AZIMUTH)
    assert gui.angle_items() == ["0", "7.5", "30", "90"]
    assert gui.selector.angle_label == "theta (deg)"


@pytest.mark.parametrize("index", [0, len(PHI) - 1])
def test_vertical_extreme_phi_indices(full_grid, index):
    gui = full_grid

    gui.choose_angle(index)

    assert gui.patterns.selection.phi_index == index
    xdata, ydata = gui.line_data()
    # Vertical: theta en X, columna ``index`` de la matriz (phi fijo).
    assert xdata == list(THETA)
    assert ydata == [float(10 * i + index) for i in range(len(THETA))]
    assert f"phi = {PHI[index]:g} deg" in gui.axes.get_title()


@pytest.mark.parametrize("index", [0, len(THETA) - 1])
def test_azimuth_extreme_theta_indices(full_grid, index):
    gui = full_grid
    gui.choose_kind(CutKind.AZIMUTH)

    gui.choose_angle(index)

    assert gui.patterns.selection.theta_index == index
    assert gui.axes.name == "polar"
    _, ydata = gui.line_data()
    # Azimut: fila ``index`` de la matriz (theta fijo).
    assert ydata == [float(10 * index + j) for j in range(len(PHI))]
    assert f"theta = {THETA[index]:g} deg" in gui.axes.get_title()


def test_switching_modes_keeps_each_selection(full_grid):
    gui = full_grid

    gui.choose_angle(3)  # phi = 270
    gui.choose_kind(CutKind.AZIMUTH)
    assert gui.selector.angle_combo.currentIndex() == 0
    gui.choose_angle(2)  # theta = 30
    gui.choose_kind(CutKind.VERTICAL)

    assert gui.selector.angle_combo.currentIndex() == 3
    assert "phi = 270 deg" in gui.axes.get_title()
    gui.choose_kind(CutKind.AZIMUTH)
    assert gui.selector.angle_combo.currentIndex() == 2
    assert "theta = 30 deg" in gui.axes.get_title()


def test_changing_the_cut_never_runs_the_engine_again(full_grid):
    gui = full_grid
    calls = list(gui.engine.calls)
    created = list(gui.factory.created_in)
    states = []
    gui.patterns.state_changed.connect(states.append)
    analysis = gui.patterns.analysis

    for index in range(len(PHI)):
        gui.choose_angle(index)
    gui.choose_kind(CutKind.AZIMUTH)
    for index in range(len(THETA)):
        gui.choose_angle(index)
    gui.choose_kind(CutKind.VERTICAL)

    assert gui.engine.calls == calls
    assert gui.factory.created_in == created
    assert states == []
    assert gui.patterns.runner.thread_count == 0
    assert gui.patterns.analysis is analysis


def test_status_text_names_the_cut_shown(full_grid):
    gui = full_grid
    status = gui.window.calculation_status

    assert status.text().endswith("Showing the vertical cut at phi = 0 deg.")
    gui.choose_angle(4)
    assert status.text().endswith("Showing the vertical cut at phi = 359 deg.")
    gui.choose_kind(CutKind.AZIMUTH)
    gui.choose_angle(1)
    assert status.text().endswith("Showing the azimuth cut at theta = 7.5 deg.")
    assert "elevation" not in status.text().lower()


def test_floor_is_the_same_for_every_cut(full_grid):
    gui = full_grid
    # Máximo 34 dBi (celda 3,4): piso 34 - 40 = -6 dBi.
    expected = "drawn at the -6 dBi floor."

    assert gui.window.radiation_pattern_plot.status_text.endswith(expected)
    gui.choose_kind(CutKind.AZIMUTH)
    assert gui.window.radiation_pattern_plot.status_text.endswith(expected)


def test_selector_signals_are_not_emitted_when_the_controls_are_updated(full_grid):
    gui = full_grid
    emitted = []
    gui.selector.kind_selected.connect(emitted.append)
    gui.selector.index_selected.connect(emitted.append)

    gui.selector.show_selection(gui.patterns.selection.with_index(2), enabled=True)

    assert emitted == []


# -- Estados -----------------------------------------------------------------


def test_empty_state_has_empty_disabled_controls():
    gui = Gui()
    try:
        assert gui.kind_items() == []
        assert gui.angle_items() == []
        assert not gui.selector.kind_combo.isEnabled()
        assert not gui.selector.angle_combo.isEnabled()
        assert gui.selector.angle_label == "Angle (deg)"
        gui.window.open_project_path(V4)
        assert gui.kind_items() == []
        assert gui.patterns.select_cut_index(0) is False
    finally:
        gui.close()


def test_new_calculation_resets_the_selection(full_grid):
    gui = full_grid
    gui.choose_angle(4)
    gui.choose_kind(CutKind.AZIMUTH)
    gui.choose_angle(3)

    assert gui.patterns.calculate()
    wait(lambda: gui.patterns.state is State.RESULT)

    selection = gui.patterns.selection
    assert (selection.kind, selection.phi_index, selection.theta_index) == (
        CutKind.VERTICAL, 0, 0,
    )
    assert gui.selector.kind_combo.currentIndex() == 0
    assert gui.selector.angle_combo.currentIndex() == 0


def test_controls_are_disabled_while_calculating_and_cancel_keeps_everything(
    tmp_path,
):
    path = project_with_pattern(
        tmp_path, AngularSweep(0.0, 4, 30.0), AngularSweep(0.0, 5, 90.0)
    )
    gate = threading.Event()
    gate.set()
    gui = Gui(gate=gate)
    try:
        gui.calculate(path)
        gui.choose_kind(CutKind.AZIMUTH)
        gui.choose_angle(3)
        before = (
            gui.patterns.analysis,
            gui.patterns.selection,
            gui.line_data(),
            gui.axes.get_title(),
            gui.window.calculation_status.text(),
        )

        gate.clear()
        gui.engine.started.clear()
        assert gui.patterns.calculate()
        assert gui.engine.started.wait(WAIT_TIMEOUT_S)
        # Durante el cálculo: corte visible, controles deshabilitados.
        assert not gui.selector.kind_combo.isEnabled()
        assert not gui.selector.angle_combo.isEnabled()
        assert gui.selector.angle_combo.currentIndex() == 3
        assert gui.patterns.select_cut_index(0) is False
        assert gui.patterns.select_cut_kind(CutKind.VERTICAL) is False

        gui.window.cancel_calculation_action.trigger()
        gate.set()
        wait(lambda: not gui.patterns.is_busy)

        after = (
            gui.patterns.analysis,
            gui.patterns.selection,
            gui.line_data(),
            gui.axes.get_title(),
            gui.window.calculation_status.text(),
        )
        assert gui.patterns.state is State.RESULT
        assert after == before
        assert gui.selector.kind_combo.isEnabled()
        assert gui.selector.angle_combo.currentIndex() == 3
    finally:
        gate.set()
        gui.close()


def test_error_without_previous_result_leaves_empty_controls():
    gui = Gui()
    gui.engine.error = RuntimeError("NEC2++ failed")
    try:
        gui.calculate(V4)

        assert gui.patterns.state is State.ERROR
        assert gui.patterns.selection is None
        assert gui.kind_items() == []
        assert gui.angle_items() == []
        assert gui.axes is None
    finally:
        gui.close()


def test_error_during_a_recalculation_keeps_the_current_behaviour(full_grid):
    # Comportamiento vigente (sin cambios): el error descarta el
    # resultado anterior, su corte y el gráfico.
    gui = full_grid
    gui.choose_angle(2)
    gui.engine.error = RuntimeError("NEC2++ failed")

    gui.patterns.calculate()
    wait(lambda: not gui.patterns.is_busy)

    assert gui.patterns.state is State.ERROR
    assert gui.patterns.analysis is None
    assert gui.patterns.selection is None
    assert gui.kind_items() == []
    assert gui.axes is None
    assert gui.selections[-1] is None


@pytest.mark.parametrize("change", ["open", "close"])
def test_opening_or_closing_a_project_clears_result_and_selectors(full_grid, change):
    gui = full_grid
    gui.choose_kind(CutKind.AZIMUTH)

    if change == "open":
        gui.window.open_project_path(V1)
    else:
        gui.window.close_project_action.trigger()

    assert gui.patterns.analysis is None
    assert gui.patterns.selection is None
    assert gui.kind_items() == []
    assert gui.angle_items() == []
    assert not gui.selector.kind_combo.isEnabled()
    assert gui.axes is None


def test_invalid_selections_are_rejected_by_the_controller(full_grid):
    gui = full_grid

    with pytest.raises(ValueError):
        gui.patterns.select_cut_index(len(PHI))
    single = Gui(theta=THETA, phi=(0.0,))
    try:
        single.calculate(V4)
        with pytest.raises(ValueError):
            single.patterns.select_cut_kind(CutKind.AZIMUTH)
    finally:
        single.close()


def test_changing_the_cut_never_touches_the_runner(full_grid, monkeypatch):
    gui = full_grid

    def forbidden(*args, **kwargs):
        raise AssertionError("the runner must not be used to change the cut")

    monkeypatch.setattr(gui.patterns.runner, "submit", forbidden)
    monkeypatch.setattr(gui.patterns.runner, "request_cancel", forbidden)

    gui.choose_angle(4)
    gui.choose_kind(CutKind.AZIMUTH)
    gui.choose_angle(3)

    assert gui.patterns.selection.theta_index == 3
    # Cerrar la ventana (teardown) sí usa el runner, legítimamente.
    monkeypatch.undo()


def count_draws(gui, monkeypatch):
    plot = gui.window.radiation_pattern_plot
    draws = []
    original = plot.show_cut

    def recording(*args, **kwargs):
        draws.append(kwargs["index"])
        return original(*args, **kwargs)

    monkeypatch.setattr(plot, "show_cut", recording)
    return draws


def test_one_redraw_per_change_and_none_from_refreshing_the_controls(
    full_grid, monkeypatch
):
    gui = full_grid
    draws = count_draws(gui, monkeypatch)
    selects = []
    for name in ("select_cut_kind", "select_cut_index"):
        original = getattr(gui.patterns, name)

        def recording(value, _original=original, _name=name):
            selects.append((_name, value))
            return _original(value)

        monkeypatch.setattr(gui.patterns, name, recording)
    # Las conexiones del selector se hicieron con los métodos originales:
    # se reconectan a los registradores para observar lo que emite.
    gui.selector.kind_selected.disconnect()
    gui.selector.index_selected.disconnect()
    gui.selector.kind_selected.connect(gui.patterns.select_cut_kind)
    gui.selector.index_selected.connect(gui.patterns.select_cut_index)

    # Repoblar los controles (como en cada cambio de estado) no emite nada.
    for _ in range(3):
        gui.window._refresh_calculation()
    assert (draws, selects) == ([], [])

    gui.choose_angle(2)
    assert draws == [2]
    assert selects == [("select_cut_index", 2)]

    gui.choose_kind(CutKind.AZIMUTH)
    assert draws == [2, 0]
    # Elegir el ángulo que ya estaba no redibuja.
    gui.choose_angle(0)
    assert draws == [2, 0]
    assert selects == [
        ("select_cut_index", 2),
        ("select_cut_kind", CutKind.AZIMUTH),
        ("select_cut_index", 0),
    ]


def test_a_new_result_draws_exactly_once(full_grid, monkeypatch):
    gui = full_grid
    draws = count_draws(gui, monkeypatch)

    gui.patterns.calculate()
    wait(lambda: gui.patterns.state is State.RESULT)

    assert draws == [0]


def test_project_change_during_a_calculation_leaves_everything_coherent(tmp_path):
    path = project_with_pattern(
        tmp_path, AngularSweep(0.0, 4, 30.0), AngularSweep(0.0, 5, 90.0)
    )
    gate = threading.Event()
    gate.set()
    gui = Gui(gate=gate)
    try:
        gui.calculate(path)
        gui.choose_kind(CutKind.AZIMUTH)
        gate.clear()
        gui.engine.started.clear()
        gui.patterns.calculate()
        assert gui.engine.started.wait(WAIT_TIMEOUT_S)

        # La ventana deshabilita Open durante el cálculo; el controlador
        # igual debe quedar coherente si el proyecto cambia.
        gui.window.controller.open_project(V4)

        assert gui.patterns.state is State.CANCELLING
        assert gui.patterns.selection is None
        assert gui.kind_items() == [] and gui.angle_items() == []
        assert gui.axes is None

        gate.set()
        wait(lambda: not gui.patterns.is_busy)

        assert gui.patterns.state is State.READY
        assert gui.patterns.analysis is None
        assert gui.patterns.selection is None
        assert gui.kind_items() == []
        assert gui.axes is None
    finally:
        gate.set()
        gui.close()


def test_closing_after_switching_cuts_leaves_no_threads(full_grid):
    gui = full_grid
    gui.choose_kind(CutKind.AZIMUTH)
    gui.choose_angle(3)

    gui.window.close()

    assert gui.patterns.runner.thread_count == 0
    assert threading.active_count() == 1
