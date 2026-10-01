"""Ventana mínima de la GUI, con Qt real en modo offscreen.

Se omite por completo si PySide6 no está instalado (instalación base),
para que los jobs normales sigan probando la CLI sin Qt.
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
from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

import yaas  # noqa: E402
from yaas.gui.window import MainWindow  # noqa: E402

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def application():
    return QApplication.instance() or QApplication([])


def run_gui(arguments, *, extra_code=""):
    environment = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    code = textwrap.dedent(f"""
        import sys
        {extra_code}
        from yaas.gui.main import main
        sys.exit(main({arguments!r}))
    """)
    return subprocess.run(
        [sys.executable, "-B", "-c", code],
        cwd=REPO,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )


def test_platform_is_offscreen(application):
    assert application.platformName() == "offscreen"


def test_main_window_content(application):
    window = MainWindow()

    labels = {
        label.objectName(): label.text()
        for label in window.findChildren(QLabel)
    }

    assert window.windowTitle() == "YAAS"
    assert {
        name: labels[name]
        for name in ("titleLabel", "nameLabel", "versionLabel")
    } == {
        "titleLabel": "YAAS",
        "nameLabel": "Yet Another Antenna Simulator",
        "versionLabel": f"Version {yaas.__version__}",
    }
    assert window.width() > 0 and window.height() > 0
    window.close()


def test_main_window_has_an_empty_radiation_pattern_tab(application):
    window = MainWindow()

    assert window.tabs.count() == 1
    assert window.tabs.tabText(0) == "Radiation pattern"
    assert window.tabs.widget(0) is window.radiation_pattern_plot
    # Vacío al iniciar: ningún dato sintético, y el estado lo explica.
    assert window.radiation_pattern_plot.adapter.axes is None
    assert "cannot open projects" in window.radiation_pattern_plot.status_text
    window.close()


def test_main_window_shows_and_closes(application):
    window = MainWindow()

    window.show()
    application.processEvents()
    assert window.isVisible()

    window.close()
    application.processEvents()
    assert not window.isVisible()


def test_version_and_help():
    version = run_gui(["--version"])
    help_text = run_gui(["--help"])

    assert version.returncode == 0
    assert version.stdout.strip() == f"yaas-gui {yaas.__version__}"
    assert help_text.returncode == 0
    assert "--smoke-test" in help_text.stdout


def test_smoke_test_opens_and_closes_the_window():
    result = run_gui(["--smoke-test"])

    assert result.returncode == 0, result.stderr
    assert "Traceback" not in result.stderr


def test_smoke_test_never_loads_the_engine():
    # PyNEC se bloquea: si la GUI intentara cargarlo, el import
    # fallaría. (numpy no se bloquea: lo usa Matplotlib.) Además, al
    # terminar no queda ningún hilo de Python ni del pool de Qt activo.
    blocker = textwrap.dedent("""
        import importlib.abc
        class NoEngine(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname.split(".")[0] == "PyNEC":
                    raise ImportError(f"{fullname} blocked for test")
        sys.meta_path.insert(0, NoEngine())
    """)
    code = blocker + textwrap.dedent("""
        import threading
        from PySide6.QtCore import QThreadPool
        from yaas.gui.main import main
        exit_code = main(["--smoke-test"])
        loaded = [name for name in ("PyNEC", "yaas.engines.pynec") if name in sys.modules]
        assert not loaded, loaded
        assert threading.active_count() == 1, threading.enumerate()
        assert QThreadPool.globalInstance().activeThreadCount() == 0
        sys.exit(exit_code)
    """)
    result = subprocess.run(
        [sys.executable, "-B", "-c", "import sys\n" + code],
        cwd=REPO,
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )

    # El subprocess terminó dentro del timeout: no quedó un proceso vivo.
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("extension", [".png", ".svg", ".pdf"])
def test_smoke_export_writes_an_image(tmp_path, extension):
    destination = tmp_path / f"smoke{extension}"

    result = run_gui(["--smoke-test", "--smoke-export", str(destination)])

    assert result.returncode == 0, result.stderr
    assert destination.stat().st_size > 0


def test_smoke_export_failure_exits_with_1_without_hanging(tmp_path):
    # Una extensión no admitida falla dentro del event loop: el proceso
    # termina igual (no se cuelga) con código 1.
    result = run_gui(
        ["--smoke-test", "--smoke-export", str(tmp_path / "smoke.bmp")]
    )

    assert result.returncode == 1
    assert "smoke test failed" in result.stderr


def test_smoke_export_requires_smoke_test(tmp_path):
    result = run_gui(["--smoke-export", str(tmp_path / "smoke.png")])

    assert result.returncode == 2
    assert "--smoke-export requires --smoke-test" in result.stderr


def test_no_thread_pool_work_in_the_test_process(application):
    assert QThreadPool.globalInstance().activeThreadCount() == 0
