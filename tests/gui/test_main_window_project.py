"""Apertura de proyectos desde `MainWindow` (offscreen, sin capturas).

`QFileDialog` y `QMessageBox` se reemplazan con monkeypatch: ninguna
prueba abre un diálogo modal real.
"""

import hashlib
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("PySide6.QtWidgets")
pytest.importorskip("matplotlib")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

import yaas.gui.window as window_module  # noqa: E402
from yaas.gui import texts  # noqa: E402
from yaas.gui.widgets.radiation_pattern_plot import EMPTY_MESSAGE  # noqa: E402
from yaas.gui.window import MainWindow  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
EXAMPLES = REPO / "examples"
V1 = EXAMPLES / "dipole-20m.yaas"
V2 = EXAMPLES / "monopole-20m-perfect-ground.yaas"
V3 = EXAMPLES / "dipole-20m-real-ground.yaas"
V4 = EXAMPLES / "dipole-20m-radiation-pattern.yaas"


@pytest.fixture(scope="module", autouse=True)
def application():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def dialogs(monkeypatch):
    """Diálogos falsos: archivo a devolver y errores mostrados."""

    class Dialogs:
        selected = ""
        open_calls: list[tuple] = []
        errors: list[tuple[str, str]] = []

    fake = Dialogs()
    fake.open_calls = []
    fake.errors = []

    def get_open_file_name(parent, caption, directory, file_filter):
        fake.open_calls.append((parent, caption, directory, file_filter))
        return fake.selected, file_filter

    def critical(parent, title, message):
        fake.errors.append((title, message))

    monkeypatch.setattr(
        window_module.QFileDialog, "getOpenFileName", get_open_file_name
    )
    monkeypatch.setattr(window_module.QMessageBox, "critical", critical)
    return fake


@pytest.fixture
def window(dialogs):
    main_window = MainWindow()
    yield main_window
    main_window.close()


def assert_empty(window):
    assert window.windowTitle() == "YAAS"
    assert window.project_summary.is_empty
    assert window.project_summary.empty_text == "No project loaded"
    assert window.project_summary.displayed_fields() == {}
    assert not window.close_project_action.isEnabled()
    assert window.radiation_pattern_plot.adapter.axes is None
    assert window.radiation_pattern_plot.status_text == EMPTY_MESSAGE


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_initial_state_is_empty(window):
    assert_empty(window)
    assert window.controller.opened_project is None


def test_file_menu_actions(window):
    actions = [action.text() for action in window.file_menu.actions()]

    assert window.file_menu.title() == "&File"
    assert actions == ["&Open…", "&Close project", "", "E&xit"]
    assert window.open_action.isEnabled()
    assert window.exit_action.isEnabled()
    assert not window.close_project_action.isEnabled()
    # Ninguna acción de simulación existe todavía.
    menus = [action.text() for action in window.menuBar().actions()]
    assert menus == ["&File"]


COMMON_V1 = {
    "name": "Dipolo de 20 metros",
    "path": str(V1),
    "schema_version": "1",
    "conductors": "1",
    "frequency": "14.15 MHz",
    "reference_impedance": "50 ohm",
    "environment": "Free space",
    "sweep": "Yes",
    "radiation_pattern": "No",
}


def test_panel_for_schema_1(window):
    assert window.open_project_path(V1)

    assert window.project_summary.displayed_fields() == COMMON_V1
    assert window.windowTitle() == "YAAS — Dipolo de 20 metros"
    assert window.close_project_action.isEnabled()


@pytest.mark.parametrize(
    ("path", "schema_version", "environment", "name"),
    [
        (V2, "2", "Perfect ground", "Monopolo de 20 metros sobre tierra perfecta"),
        (
            V3,
            "3",
            "Real ground — Sommerfeld-Norton",
            "Dipolo de 20 metros sobre tierra real",
        ),
    ],
    ids=["v2", "v3"],
)
def test_panel_for_ground_projects(window, path, schema_version, environment, name):
    assert window.open_project_path(path)

    fields = window.project_summary.displayed_fields()
    assert fields["schema_version"] == schema_version
    assert fields["environment"] == environment
    assert fields["name"] == name
    assert fields["radiation_pattern"] == "No"
    assert "theta" not in fields and "phi" not in fields
    assert window.windowTitle() == f"YAAS — {name}"


def test_panel_for_schema_4_shows_theta_and_phi(window):
    assert window.open_project_path(V4)

    fields = window.project_summary.displayed_fields()
    assert fields["schema_version"] == "4"
    assert fields["radiation_pattern"] == "Yes"
    assert fields["theta"] == "start 0 deg, stop 180 deg, count 181, step 1 deg"
    assert fields["phi"] == "start 0 deg, stop 0 deg, count 1, step 0 deg"
    # Nada se muestra como "None" ni como elevación.
    assert not any("None" in text for text in fields.values())
    assert not any("elevation" in text.lower() for text in fields.values())
    # Todavía no hay resultado: el gráfico sigue vacío.
    assert window.radiation_pattern_plot.adapter.axes is None
    assert window.radiation_pattern_plot.status_text == EMPTY_MESSAGE


def test_pattern_rows_disappear_after_opening_a_project_without_pattern(window):
    window.open_project_path(V4)
    window.open_project_path(V1)

    assert window.project_summary.displayed_fields() == COMMON_V1


def test_cancelled_dialog_changes_nothing(window, dialogs):
    window.open_project_path(V1)
    dialogs.selected = ""

    assert window.choose_and_open_project() is False

    assert window.controller.opened_project.path == V1
    assert dialogs.errors == []
    (parent, caption, directory, file_filter), = dialogs.open_calls
    assert parent is window
    assert caption == "Open project"
    assert file_filter == "YAAS projects (*.yaas)"


def test_cancelled_dialog_from_empty_state(window, dialogs):
    window.open_action.trigger()

    assert len(dialogs.open_calls) == 1
    assert_empty(window)


def test_open_action_opens_the_selected_file(window, dialogs):
    dialogs.selected = str(V4)

    window.open_action.trigger()

    assert window.controller.opened_project.path == V4
    assert window.project_summary.displayed_fields()["path"] == str(V4)


def test_errors_are_shown_with_a_critical_message_box(window, dialogs, tmp_path):
    broken = tmp_path / "broken.yaas"
    broken.write_text("{", encoding="utf-8")
    dialogs.selected = str(broken)

    assert window.choose_and_open_project() is False

    (title, message), = dialogs.errors
    assert title == texts.OPEN_ERROR_TITLE
    assert "broken.yaas" in message
    assert_empty(window)


def test_error_keeps_the_open_project(window, dialogs, tmp_path):
    window.open_project_path(V3)

    assert not window.open_project_path(tmp_path / "missing.yaas")

    assert len(dialogs.errors) == 1
    assert window.project_summary.displayed_fields()["schema_version"] == "3"
    assert window.close_project_action.isEnabled()


def test_close_project_returns_to_the_empty_state(window):
    window.open_project_path(V4)
    window.show()

    window.close_project_action.trigger()

    assert_empty(window)
    assert window.controller.opened_project is None
    # Cerrar el proyecto no cierra la ventana.
    assert window.isVisible()


def test_close_clears_a_plot_drawn_by_someone_else(window):
    from yaas.domain import RadiationPatternResult

    window.open_project_path(V4)
    window.radiation_pattern_plot.show_azimuth(
        RadiationPatternResult(
            frequency_mhz=14.15,
            theta_angles_deg=(90.0,),
            phi_angles_deg=(0.0, 90.0),
            gain_db=((1.0, 2.0),),
        ),
        theta_index=0,
        floor_db=-40.0,
    )

    window.controller.close_project()

    assert window.radiation_pattern_plot.adapter.axes is None


def test_exit_action_closes_the_window(window):
    window.show()

    window.exit_action.trigger()

    assert not window.isVisible()


def test_opening_examples_does_not_modify_them(window):
    before = {path: digest(path) for path in (V1, V2, V3, V4)}

    for path in before:
        assert window.open_project_path(path)
    window.controller.close_project()

    assert {path: digest(path) for path in before} == before


def test_window_never_loads_the_engine():
    code = textwrap.dedent("""
        import importlib.abc, sys
        class NoEngine(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname.split(".")[0] == "PyNEC":
                    raise ImportError(f"{fullname} blocked for test")
        sys.meta_path.insert(0, NoEngine())
        from PySide6.QtWidgets import QApplication
        application = QApplication([])
        from yaas.gui.window import MainWindow
        window = MainWindow(error_presenter=lambda title, message: None)
        for name in ("dipole-20m", "dipole-20m-radiation-pattern"):
            assert window.open_project_path(f"examples/{name}.yaas")
        window.controller.close_project()
        loaded = [n for n in ("PyNEC", "yaas.engines.pynec") if n in sys.modules]
        assert not loaded, loaded
        assert "matplotlib" in sys.modules and "PySide6" in sys.modules
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
