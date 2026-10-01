"""Caso de uso `open_project`: abre sin migrar, guardar ni cargar motor."""

import dataclasses
import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

import yaas.application.project as project_module
from yaas.application import OpenedProject, open_project
from yaas.domain import (
    AngularSweep,
    FreeSpaceEnvironment,
    PerfectGroundEnvironment,
    RealGroundEnvironment,
    RealGroundModel,
)
from yaas.projects import AntennaProject, ProjectFormatError, load_project

REPO = Path(__file__).resolve().parents[2]
EXAMPLES = REPO / "examples"

# (archivo, schema_version, tipo de entorno, ¿define patrón?)
EXAMPLE_PROJECTS = [
    ("dipole-20m.yaas", 1, FreeSpaceEnvironment, False),
    ("monopole-20m-perfect-ground.yaas", 2, PerfectGroundEnvironment, False),
    ("dipole-20m-real-ground.yaas", 3, RealGroundEnvironment, False),
    ("dipole-20m-radiation-pattern.yaas", 4, FreeSpaceEnvironment, True),
]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("as_string", [False, True], ids=["path", "str"])
def test_open_project_accepts_str_and_path(as_string):
    source = EXAMPLES / "dipole-20m.yaas"

    opened = open_project(str(source) if as_string else source)

    assert isinstance(opened, OpenedProject)
    assert opened.path == source
    assert isinstance(opened.path, Path)
    assert isinstance(opened.project, AntennaProject)


def test_open_project_keeps_relative_paths_as_given(monkeypatch):
    monkeypatch.chdir(REPO)

    opened = open_project("examples/dipole-20m.yaas")

    # Sin resolver ni volver absoluta: la misma ruta que recibió.
    assert opened.path == Path("examples/dipole-20m.yaas")


@pytest.mark.parametrize(
    ("name", "schema_version", "environment_type", "has_pattern"),
    EXAMPLE_PROJECTS,
)
def test_open_project_examples_keep_their_schema(
    name, schema_version, environment_type, has_pattern
):
    path = EXAMPLES / name
    before = digest(path)

    opened = open_project(path)

    assert opened.project.schema_version == schema_version
    assert type(opened.project.environment) is environment_type
    assert (opened.project.radiation_pattern is not None) is has_pattern
    # Mismo contenido que load_project, y el archivo no cambia.
    assert opened.project == load_project(path)
    assert digest(path) == before


def test_real_ground_example_details():
    opened = open_project(EXAMPLES / "dipole-20m-real-ground.yaas")

    environment = opened.project.environment
    assert environment.model is RealGroundModel.SOMMERFELD_NORTON
    assert environment.relative_permittivity == 13.0
    assert environment.conductivity_s_per_m == 0.005


def test_radiation_pattern_example_axes():
    opened = open_project(EXAMPLES / "dipole-20m-radiation-pattern.yaas")

    pattern = opened.project.radiation_pattern
    assert pattern.theta == AngularSweep(start_deg=0.0, count=181, step_deg=1.0)
    assert pattern.phi == AngularSweep(start_deg=0.0, count=1, step_deg=0.0)


def test_open_project_delegates_only_to_load_project(monkeypatch):
    loaded = load_project(EXAMPLES / "dipole-20m.yaas")
    calls = []

    def fake_load_project(source):
        calls.append(source)
        return loaded

    monkeypatch.setattr(project_module, "load_project", fake_load_project)

    opened = open_project("any/where.yaas")

    assert calls == [Path("any/where.yaas")]
    # La misma instancia, sin copiarla ni modificarla.
    assert opened.project is loaded


def test_open_project_does_not_write(tmp_path):
    copy = tmp_path / "project.yaas"
    copy.write_bytes((EXAMPLES / "dipole-20m.yaas").read_bytes())
    before = (copy.read_bytes(), copy.stat().st_mtime_ns)

    open_project(copy)

    assert (copy.read_bytes(), copy.stat().st_mtime_ns) == before
    assert sorted(tmp_path.iterdir()) == [copy]


def test_missing_file_raises_os_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        open_project(tmp_path / "missing.yaas")


def test_directory_raises_os_error(tmp_path):
    directory = tmp_path / "folder.yaas"
    directory.mkdir()

    with pytest.raises(OSError):
        open_project(directory)


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("broken.yaas", b"{"),
        ("empty.yaas", b""),
        ("latin1.yaas", b'{"name": "\xe9"}'),
        ("version.yaas", b'{"schema_version": 99}'),
        ("project.json", b"{}"),
    ],
)
def test_invalid_files_raise_project_format_error(tmp_path, name, content):
    path = tmp_path / name
    path.write_bytes(content)

    with pytest.raises(ProjectFormatError):
        open_project(path)


def test_opened_project_is_immutable():
    opened = open_project(EXAMPLES / "dipole-20m.yaas")

    with pytest.raises(dataclasses.FrozenInstanceError):
        opened.path = Path("other.yaas")


@pytest.mark.parametrize(
    "fields",
    [
        {"path": "dipole-20m.yaas"},
        {"project": object()},
    ],
)
def test_opened_project_validates_types(fields):
    valid = open_project(EXAMPLES / "dipole-20m.yaas")
    arguments = {"path": valid.path, "project": valid.project, **fields}

    with pytest.raises(TypeError):
        OpenedProject(**arguments)


def test_open_project_loads_no_gui_engine_or_numpy():
    code = (
        "import sys\n"
        "from yaas.application.project import open_project\n"
        "opened = open_project('examples/dipole-20m-radiation-pattern.yaas')\n"
        "assert opened.project.schema_version == 4\n"
        "blocked = ('PySide6', 'shiboken6', 'matplotlib', 'PyNEC',\n"
        "           'yaas.engines.pynec', 'numpy', 'yaas.gui')\n"
        "loaded = [name for name in blocked if name in sys.modules]\n"
        "assert not loaded, loaded\n"
    )
    result = subprocess.run(
        [sys.executable, "-B", "-c", code],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )

    assert result.returncode == 0, result.stderr
