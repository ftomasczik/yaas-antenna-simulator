"""`ProjectController` con Qt real en modo offscreen.

Las señales se prueban con conexiones directas (síncronas), sin
pytest-qt. La función que abre proyectos se inyecta cuando hace falta
un doble.
"""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("PySide6.QtWidgets")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QThreadPool  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from yaas.application import OpenedProject, open_project  # noqa: E402
from yaas.domain import (  # noqa: E402
    FreeSpaceEnvironment,
    PerfectGroundEnvironment,
    RealGroundEnvironment,
)
from yaas.gui import texts  # noqa: E402
from yaas.gui.controllers.project import ProjectController  # noqa: E402
from yaas.gui.controllers.project_state import ProjectViewState  # noqa: E402
from yaas.projects import ProjectFormatError  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
EXAMPLES = REPO / "examples"
V1 = EXAMPLES / "dipole-20m.yaas"
V2 = EXAMPLES / "monopole-20m-perfect-ground.yaas"
V3 = EXAMPLES / "dipole-20m-real-ground.yaas"
V4 = EXAMPLES / "dipole-20m-radiation-pattern.yaas"


@pytest.fixture(scope="module", autouse=True)
def application():
    return QApplication.instance() or QApplication([])


class Recorder:
    """Registra cada señal del controlador, en orden."""

    def __init__(self, controller: ProjectController) -> None:
        self.events: list[tuple] = []
        controller.project_opened.connect(
            lambda state: self.events.append(("opened", state))
        )
        controller.project_closed.connect(
            lambda: self.events.append(("closed",))
        )
        controller.error_occurred.connect(
            lambda title, message: self.events.append(("error", title, message))
        )


@pytest.fixture
def controller():
    return ProjectController()


@pytest.fixture
def recorder(controller):
    return Recorder(controller)


def test_initial_state_is_empty(controller, recorder):
    assert controller.opened_project is None
    assert controller.state is None
    assert not controller.has_project
    assert recorder.events == []


@pytest.mark.parametrize(
    ("path", "schema_version", "environment_type", "has_pattern"),
    [
        (V1, 1, FreeSpaceEnvironment, False),
        (V2, 2, PerfectGroundEnvironment, False),
        (V3, 3, RealGroundEnvironment, False),
        (V4, 4, FreeSpaceEnvironment, True),
    ],
    ids=["v1", "v2", "v3", "v4"],
)
def test_open_each_schema_version(
    controller, recorder, path, schema_version, environment_type, has_pattern
):
    assert controller.open_project(path) is True

    state = controller.state
    assert recorder.events == [("opened", state)]
    assert controller.has_project
    assert controller.opened_project.path == path
    assert state == ProjectViewState.from_opened_project(open_project(path))
    assert state.schema_version == schema_version
    assert type(state.environment) is environment_type
    assert state.has_radiation_pattern is has_pattern


def test_open_accepts_a_string_path(controller):
    assert controller.open_project(str(V1))
    assert controller.opened_project.path == V1


def test_opening_another_project_replaces_the_current_one(controller, recorder):
    controller.open_project(V1)
    controller.open_project(V4)

    assert controller.opened_project.path == V4
    assert controller.state.schema_version == 4
    assert [event[0] for event in recorder.events] == ["opened", "opened"]


def test_close_returns_to_the_empty_state(controller, recorder):
    controller.open_project(V3)

    assert controller.close_project() is True

    assert controller.opened_project is None
    assert controller.state is None
    assert recorder.events[-1] == ("closed",)


def test_close_without_project_does_nothing(controller, recorder):
    assert controller.close_project() is False
    assert recorder.events == []


def test_failure_keeps_the_previous_project(controller, recorder, tmp_path):
    controller.open_project(V4)
    previous = controller.opened_project

    assert controller.open_project(tmp_path / "missing.yaas") is False

    assert controller.opened_project is previous
    assert controller.state.schema_version == 4
    kind, title, message = recorder.events[-1]
    assert (kind, title) == ("error", texts.OPEN_ERROR_TITLE)
    assert "missing.yaas" in message


def test_initial_failure_stays_empty(controller, recorder, tmp_path):
    broken = tmp_path / "broken.yaas"
    broken.write_text("{", encoding="utf-8")

    assert controller.open_project(broken) is False

    assert controller.opened_project is None
    assert [event[0] for event in recorder.events] == ["error"]
    assert "broken.yaas" in recorder.events[0][2]


@pytest.mark.parametrize(
    "error",
    [
        ProjectFormatError("bad project"),
        FileNotFoundError("no such file"),
        PermissionError("denied"),
    ],
)
def test_expected_errors_are_reported(error):
    def failing(path):
        raise error

    controller = ProjectController(opener=failing)
    recorder = Recorder(controller)

    assert controller.open_project("x.yaas") is False
    assert recorder.events == [("error", texts.OPEN_ERROR_TITLE, str(error))]


def test_programming_errors_are_not_hidden():
    def buggy(path):
        raise KeyError("bug")

    controller = ProjectController(opener=buggy)
    recorder = Recorder(controller)

    with pytest.raises(KeyError):
        controller.open_project("x.yaas")
    assert recorder.events == []
    assert controller.opened_project is None


def test_uses_the_injected_opener():
    opened = open_project(V1)
    calls = []

    def opener(path):
        calls.append(path)
        return opened

    controller = ProjectController(opener=opener)

    assert controller.open_project("chosen.yaas")
    assert calls == ["chosen.yaas"]
    assert controller.opened_project is opened


def test_opened_project_is_the_application_result(controller):
    controller.open_project(V2)

    assert isinstance(controller.opened_project, OpenedProject)


def test_properties_are_read_only(controller):
    for name in ("opened_project", "state", "has_project"):
        with pytest.raises(AttributeError):
            setattr(controller, name, None)


def test_controller_is_destroyed_without_threads(controller):
    controller.open_project(V1)
    controller.deleteLater()
    QApplication.processEvents()

    assert QThreadPool.globalInstance().activeThreadCount() == 0


def test_controller_never_loads_the_engine_or_dialogs():
    # PyNEC se bloquea; además, si el controlador intentara mostrar un
    # diálogo, fallaría en vez de bloquear la prueba.
    code = textwrap.dedent("""
        import importlib.abc, sys, threading
        class NoEngine(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname.split(".")[0] == "PyNEC":
                    raise ImportError(f"{fullname} blocked for test")
        sys.meta_path.insert(0, NoEngine())
        from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
        def forbidden(*args, **kwargs):
            raise AssertionError("dialog used by the controller")
        QFileDialog.getOpenFileName = forbidden
        QMessageBox.critical = forbidden
        application = QApplication([])
        from yaas.gui.controllers.project import ProjectController
        controller = ProjectController()
        for name in ("dipole-20m", "monopole-20m-perfect-ground",
                     "dipole-20m-real-ground", "dipole-20m-radiation-pattern"):
            assert controller.open_project(f"examples/{name}.yaas")
        assert not controller.open_project("examples/missing.yaas")
        controller.close_project()
        blocked = ("PyNEC", "yaas.engines.pynec", "yaas.gui.window")
        loaded = [name for name in blocked if name in sys.modules]
        assert not loaded, loaded
        assert threading.active_count() == 1, threading.enumerate()
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
