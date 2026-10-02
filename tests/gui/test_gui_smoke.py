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
    # Se concatena (no se interpola dentro de un dedent): extra_code puede
    # tener varias líneas.
    code = (
        "import sys\n"
        + extra_code
        + f"\nfrom yaas.gui.main import main\nsys.exit(main({arguments!r}))\n"
    )
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


# Diagnóstico benigno que el plugin offscreen de Qt escribe en algunas
# plataformas (por ejemplo, en CI) al mostrar la ventana. Es el único
# texto que se tolera, y solo como línea completa y exacta.
QT_OFFSCREEN_SIZE_HINTS_WARNING = (
    "This plugin does not support propagateSizeHints()"
)


def assert_only_benign_qt_stderr(stderr):
    """Falla ante cualquier línea de stderr que no sea el aviso benigno.

    Las líneas vacías se ignoran; el aviso puede repetirse.
    """
    unexpected = [
        line
        for line in stderr.splitlines()
        if line.strip() and line != QT_OFFSCREEN_SIZE_HINTS_WARNING
    ]
    assert not unexpected, "unexpected stderr:\n" + "\n".join(unexpected)


@pytest.mark.parametrize(
    "stderr",
    [
        "",
        "\n\n",
        QT_OFFSCREEN_SIZE_HINTS_WARNING,
        f"{QT_OFFSCREEN_SIZE_HINTS_WARNING}\n",
        f"{QT_OFFSCREEN_SIZE_HINTS_WARNING}\r\n\r\n"
        f"{QT_OFFSCREEN_SIZE_HINTS_WARNING}\n{QT_OFFSCREEN_SIZE_HINTS_WARNING}\n",
    ],
    ids=["empty", "blank-lines", "warning", "warning-newline", "repeated"],
)
def test_benign_qt_stderr_helper_accepts(stderr):
    assert_only_benign_qt_stderr(stderr)


@pytest.mark.parametrize(
    "stderr",
    [
        "yaas-gui: smoke test failed: boom\n",
        f"{QT_OFFSCREEN_SIZE_HINTS_WARNING}\n"
        "Traceback (most recent call last):\n"
        '  File "x.py", line 1, in <module>\n'
        "ValueError: boom\n",
        f"qpa: {QT_OFFSCREEN_SIZE_HINTS_WARNING}\n",
        f"{QT_OFFSCREEN_SIZE_HINTS_WARNING} (extra)\n",
        "This plugin does not support propagateSizeHints\n",
        "Warning: something else\n",
    ],
    ids=[
        "unexpected-message",
        "traceback-after-warning",
        "prefixed-warning",
        "suffixed-warning",
        "partial-warning",
        "other-warning",
    ],
)
def test_benign_qt_stderr_helper_rejects(stderr):
    with pytest.raises(AssertionError, match="unexpected stderr"):
        assert_only_benign_qt_stderr(stderr)


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
    # La pestaña contiene el selector de cortes y el gráfico.
    tab = window.tabs.widget(0)
    assert tab is window.radiation_pattern_tab
    assert window.radiation_pattern_plot.parent() is tab
    assert window.cut_selector.parent() is tab
    # Vacío al iniciar: ningún dato sintético, y el estado lo explica.
    assert window.radiation_pattern_plot.adapter.axes is None
    assert (
        window.radiation_pattern_plot.status_text
        == "No radiation pattern to show yet."
    )
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


EXAMPLE_PROJECTS = [
    "examples/dipole-20m.yaas",
    "examples/monopole-20m-perfect-ground.yaas",
    "examples/dipole-20m-real-ground.yaas",
    "examples/dipole-20m-radiation-pattern.yaas",
]


@pytest.mark.parametrize("project", EXAMPLE_PROJECTS, ids=["v1", "v2", "v3", "v4"])
def test_smoke_test_opens_each_example_project(project):
    before = (REPO / project).read_bytes()

    result = run_gui(["--smoke-test", project])

    assert result.returncode == 0, result.stderr
    assert_only_benign_qt_stderr(result.stderr)
    assert (REPO / project).read_bytes() == before


@pytest.mark.parametrize("damaged", [False, True], ids=["missing", "damaged"])
def test_smoke_test_fails_when_the_project_cannot_be_opened(tmp_path, damaged):
    project = tmp_path / "project.yaas"
    if damaged:
        project.write_text("{", encoding="utf-8")

    result = run_gui(["--smoke-test", str(project)])

    assert result.returncode == 1
    assert "Could not open project" in result.stderr
    assert "project.yaas" in result.stderr
    assert "Traceback" not in result.stderr


def test_smoke_test_with_project_and_export(tmp_path):
    image = tmp_path / "smoke.png"

    result = run_gui(
        [
            "--smoke-test",
            "--smoke-export",
            str(image),
            "examples/dipole-20m-radiation-pattern.yaas",
        ]
    )

    assert result.returncode == 0, result.stderr
    assert image.stat().st_size > 0


def test_smoke_test_with_project_never_loads_the_engine():
    blocker = textwrap.dedent("""
        import importlib.abc
        class NoEngine(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname.split(".")[0] == "PyNEC":
                    raise ImportError(f"{fullname} blocked for test")
        sys.meta_path.insert(0, NoEngine())
    """)
    code = blocker + textwrap.dedent("""
        from yaas.gui.main import main
        exit_code = main(
            ["--smoke-test", "examples/dipole-20m-radiation-pattern.yaas"]
        )
        loaded = [name for name in ("PyNEC", "yaas.engines.pynec") if name in sys.modules]
        assert not loaded, loaded
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

    assert result.returncode == 0, result.stdout + result.stderr


def test_invalid_project_at_startup_shows_an_error_and_keeps_running(tmp_path):
    # Sin --smoke-test, el error se muestra con QMessageBox. El diálogo
    # se reemplaza por uno que informa por stdout y cierra la
    # aplicación, para que la prueba no bloquee.
    patch = textwrap.dedent("""
        from PySide6.QtWidgets import QApplication, QMessageBox
        def critical(parent, title, message):
            print("dialog:", title, "|", message)
            print("window title:", parent.windowTitle())
            print("empty:", parent.project_summary.is_empty)
            QApplication.instance().quit()
        QMessageBox.critical = critical
    """)

    result = run_gui([str(tmp_path / "missing.yaas")], extra_code=patch)

    assert result.returncode == 0, result.stderr
    assert "dialog: Could not open project | " in result.stdout
    assert "missing.yaas" in result.stdout
    assert "window title: YAAS\n" in result.stdout
    assert "empty: True" in result.stdout
    assert "Traceback" not in result.stderr


def test_help_mentions_the_project_argument():
    result = run_gui(["--help"])

    assert result.returncode == 0
    assert "PROJECT" in result.stdout
    assert "--smoke-calculate" in result.stdout


# ---------------------------------------------------------------------------
# --smoke-calculate: cálculo real con PyNEC dentro del worker
# ---------------------------------------------------------------------------


def test_smoke_calculate_draws_the_real_pattern(tmp_path):
    pytest.importorskip("PyNEC")
    image = tmp_path / "pattern.png"

    result = run_gui(
        [
            "--smoke-test",
            "--smoke-calculate",
            "--smoke-export",
            str(image),
            "examples/dipole-20m-radiation-pattern.yaas",
        ]
    )

    assert result.returncode == 0, result.stderr
    assert_only_benign_qt_stderr(result.stderr)
    assert image.stat().st_size > 0


def test_smoke_calculate_engine_runs_outside_the_main_thread():
    pytest.importorskip("PyNEC")
    # PyNEC no está cargado antes del cálculo y se importa en el worker.
    patch = textwrap.dedent("""
        import builtins, threading
        main_thread = threading.get_ident()
        original_import = builtins.__import__
        def tracking_import(name, *args, **kwargs):
            if name.split(".")[0] == "PyNEC" and "PyNEC" not in sys.modules:
                print("PyNEC imported in main thread:",
                      threading.get_ident() == main_thread)
            return original_import(name, *args, **kwargs)
        builtins.__import__ = tracking_import
    """)

    result = run_gui(
        [
            "--smoke-test",
            "--smoke-calculate",
            "examples/dipole-20m-radiation-pattern.yaas",
        ],
        extra_code=patch,
    )

    assert result.returncode == 0, result.stderr
    assert "PyNEC imported in main thread: False" in result.stdout
    assert "PyNEC imported in main thread: True" not in result.stdout


def test_smoke_calculate_walks_both_cut_modes_of_a_full_grid(tmp_path):
    pytest.importorskip("PyNEC")
    import dataclasses

    from yaas.domain import AngularSweep
    from yaas.projects import RadiationPatternSettings, load_project, save_project

    project = load_project(REPO / "examples/dipole-20m-radiation-pattern.yaas")
    path = save_project(
        dataclasses.replace(
            project,
            radiation_pattern=RadiationPatternSettings(
                theta=AngularSweep(0.0, 4, 30.0), phi=AngularSweep(0.0, 4, 90.0)
            ),
        ),
        tmp_path / "full-grid.yaas",
    )
    # Cuenta las simulaciones: recorrer los cortes no debe repetirla.
    patch = textwrap.dedent("""
        import yaas.engines.pynec as pynec
        original = pynec.PyNecEngine.simulate_radiation_pattern
        def counting(self, request):
            print("engine call")
            return original(self, request)
        pynec.PyNecEngine.simulate_radiation_pattern = counting
    """)

    result = run_gui(
        ["--smoke-test", "--smoke-calculate", str(path)], extra_code=patch
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.count("engine call") == 1


def test_smoke_calculate_fails_for_a_project_without_pattern():
    result = run_gui(["--smoke-test", "--smoke-calculate", "examples/dipole-20m.yaas"])

    assert result.returncode == 1
    assert "Radiation pattern calculation failed" in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize(
    "arguments",
    [
        ["--smoke-calculate", "examples/dipole-20m-radiation-pattern.yaas"],
        ["--smoke-test", "--smoke-calculate"],
    ],
    ids=["without-smoke-test", "without-project"],
)
def test_smoke_calculate_requires_smoke_test_and_project(arguments):
    result = run_gui(arguments)

    assert result.returncode == 2
    assert "--smoke-calculate requires --smoke-test and PROJECT" in result.stderr


def test_no_thread_pool_work_in_the_test_process(application):
    assert QThreadPool.globalInstance().activeThreadCount() == 0
