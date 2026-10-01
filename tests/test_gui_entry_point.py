"""Entry point `yaas-gui` y separación de dependencias, sin requerir Qt.

Cada caso corre en un proceso nuevo. Cuando hace falta demostrar la
ausencia real de Qt, un buscador de imports hace fallar `PySide6` y
`shiboken6` como si no estuvieran instalados, sin depender del estado
del entorno local ni desinstalar nada.
"""

import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

import yaas

REPO = Path(__file__).resolve().parents[1]

QT_BLOCKER = '''
import importlib.abc
import sys
class MissingQt(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        root = fullname.split(".")[0]
        if root in ("PySide6", "shiboken6"):
            raise ModuleNotFoundError(
                f"No module named {fullname!r}", name=fullname
            )
sys.meta_path.insert(0, MissingQt())
'''


def run_python(code, *, block_qt=False):
    return subprocess.run(
        [sys.executable, "-B", "-c", (QT_BLOCKER if block_qt else "") + code],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )


QT_LIBRARIES = ("PySide6", "shiboken6", "matplotlib")


@pytest.mark.parametrize(
    "module",
    [
        "yaas",
        "yaas.application",
        "yaas.application.project",
        "yaas.cli.main",
        "yaas.domain",
        "yaas.projects",
        "yaas.exporters",
        "yaas.engines",
        "yaas.gui",
        "yaas.gui.main",
        "yaas.gui.texts",
        "yaas.gui.controllers",
        "yaas.gui.controllers.project_state",
    ],
)
def test_importing_does_not_load_qt(module):
    # Sin bloquear: aunque Qt estuviera instalado, importar estas capas
    # (incluido el punto de entrada de la GUI) no lo carga.
    result = run_python(f'''
import sys
import {module}
loaded = [name for name in {QT_LIBRARIES!r} if name in sys.modules]
assert not loaded, loaded
''')
    assert result.returncode == 0, result.stderr


def test_cli_works_and_does_not_load_qt():
    result = run_python('''
import sys
from yaas.cli.main import main
code = main(["--language", "en", "validate", "examples/dipole-20m.yaas"])
loaded = [name for name in ("PySide6", "shiboken6", "matplotlib") if name in sys.modules]
assert not loaded, loaded
sys.exit(code)
''', block_qt=True)
    assert result.returncode == 0, result.stderr
    assert "Valid project:" in result.stdout


def test_opening_a_project_from_the_application_loads_no_qt_or_engine():
    # Con Qt bloqueado: abrir un proyecto no depende del extra gui, y
    # tampoco crea ni importa el motor.
    result = run_python('''
import sys
from yaas.application import open_project
opened = open_project("examples/dipole-20m-radiation-pattern.yaas")
assert opened.project.schema_version == 4
blocked = ("PySide6", "shiboken6", "matplotlib", "PyNEC", "yaas.engines.pynec")
loaded = [name for name in blocked if name in sys.modules]
assert not loaded, loaded
''', block_qt=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "arguments",
    [[], ["--smoke-test"], ["--smoke-test", "examples/dipole-20m.yaas"]],
)
def test_gui_without_qt_fails_cleanly(arguments):
    result = run_python(f'''
import sys
from yaas.gui.main import main
sys.exit(main({arguments!r}))
''', block_qt=True)

    assert result.returncode == 1
    assert result.stdout == ""
    assert "yet-another-antenna-simulator[gui]" in result.stderr
    assert "Traceback" not in result.stderr


MATPLOTLIB_BLOCKER = '''
import importlib.abc
import sys
class MissingMatplotlib(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] == "matplotlib":
            raise ModuleNotFoundError(
                f"No module named {fullname!r}", name=fullname
            )
sys.meta_path.insert(0, MissingMatplotlib())
'''


def test_gui_without_matplotlib_fails_cleanly():
    # Instalación parcial (Qt presente, Matplotlib ausente): mismo
    # mensaje que sin el extra, sin traceback. Si Qt tampoco está
    # instalado, el resultado es el mismo.
    result = run_python(MATPLOTLIB_BLOCKER + '''
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from yaas.gui.main import main
sys.exit(main(["--smoke-test"]))
''')

    assert result.returncode == 1
    assert "yet-another-antenna-simulator[gui]" in result.stderr
    assert "Traceback" not in result.stderr


def test_gui_version_and_help_do_not_need_qt():
    for arguments, expected in (
        (["--version"], f"yaas-gui {yaas.__version__}"),
        (["--help"], "--smoke-test"),
    ):
        result = run_python(f'''
import sys
from yaas.gui.main import main
try:
    main({arguments!r})
except SystemExit as exit_info:
    loaded = [name for name in ("PySide6", "shiboken6", "matplotlib") if name in sys.modules]
    assert not loaded, loaded
    sys.exit(exit_info.code)
''', block_qt=True)

        assert result.returncode == 0, result.stderr
        assert expected in result.stdout


def test_unrelated_import_errors_are_not_hidden():
    # Un ImportError que no proviene de Qt no se disfraza de
    # "instale el extra gui".
    result = run_python('''
import sys
import yaas.gui.main as gui_main
def broken(**kwargs):
    raise ModuleNotFoundError("No module named 'yaas.missing'", name="yaas.missing")
gui_main._run_window = broken
sys.exit(gui_main.main(["--smoke-test"]))
''')
    assert result.returncode != 0
    assert "yaas.missing" in result.stderr
    assert "yet-another-antenna-simulator[gui]" not in result.stderr


# ---------------------------------------------------------------------------
# Declaración de dependencias y entry points
# ---------------------------------------------------------------------------


def load_pyproject():
    with (REPO / "pyproject.toml").open("rb") as file:
        return tomllib.load(file)


def test_entry_points_are_declared():
    scripts = load_pyproject()["project"]["scripts"]

    assert scripts["yaas"] == "yaas.cli.main:main"
    assert scripts["yaas-gui"] == "yaas.gui.main:main"


def test_qt_is_only_in_the_optional_gui_extra():
    project = load_pyproject()["project"]
    extras = project["optional-dependencies"]

    def names(requirements):
        return {re.split(r"[<>=!~;\[ ]", r, maxsplit=1)[0].lower() for r in requirements}

    assert names(extras["gui"]) == {"pyside6-essentials", "matplotlib"}
    for group in (project["dependencies"], extras["dev"]):
        assert not names(group) & {
            "pyside6", "pyside6-essentials", "pyside6-addons",
            "shiboken6", "matplotlib",
        }


# ---------------------------------------------------------------------------
# CI: los jobs base no instalan el extra gui
# ---------------------------------------------------------------------------


def workflow_installs():
    """Extras instalados con `pip install -e` en cada job del workflow."""
    installs: dict[str, list[str]] = {}
    job = None
    in_jobs = False
    for line in (REPO / ".github/workflows/tests.yml").read_text(
        encoding="utf-8"
    ).splitlines():
        if line.startswith("jobs:"):
            in_jobs = True
            continue
        match = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", line)
        if in_jobs and match:
            job = match.group(1)
            installs[job] = []
            continue
        install = re.search(r'pip install -e "(\.\[[^\]]*\])"', line)
        if job and install:
            installs[job].append(install.group(1))
    return installs


def test_base_jobs_do_not_install_gui_and_gui_jobs_do():
    installs = workflow_installs()

    for job in ("test-windows", "test-ubuntu", "test-ubuntu-24", "build-linux"):
        assert installs[job] == [".[dev]"], (job, installs[job])
    for job in ("test-gui-windows", "test-gui-ubuntu-24"):
        assert installs[job] == [".[dev,gui]"], (job, installs[job])
