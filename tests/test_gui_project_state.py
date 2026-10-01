"""`ProjectViewState`: estado de presentación sin Qt.

Corre también en la instalación base: el módulo no importa PySide6.
"""

import dataclasses
import subprocess
import sys
from pathlib import Path

import pytest

from yaas.application import OpenedProject, open_project
from yaas.domain import (
    AngularSweep,
    FreeSpaceEnvironment,
    PerfectGroundEnvironment,
    RealGroundEnvironment,
)
from yaas.gui.controllers.project_state import ProjectViewState

REPO = Path(__file__).resolve().parents[1]
EXAMPLES = REPO / "examples"


def state_for(name: str) -> ProjectViewState:
    return ProjectViewState.from_opened_project(open_project(EXAMPLES / name))


def test_state_from_schema_1_project():
    state = state_for("dipole-20m.yaas")

    assert state == ProjectViewState(
        path=EXAMPLES / "dipole-20m.yaas",
        name="Dipolo de 20 metros",
        schema_version=1,
        conductor_count=1,
        frequency_mhz=14.15,
        reference_impedance_ohm=50.0,
        environment=FreeSpaceEnvironment(),
        has_sweep=True,
        theta=None,
        phi=None,
    )
    assert not state.has_radiation_pattern


@pytest.mark.parametrize(
    ("name", "schema_version", "environment_type"),
    [
        ("monopole-20m-perfect-ground.yaas", 2, PerfectGroundEnvironment),
        ("dipole-20m-real-ground.yaas", 3, RealGroundEnvironment),
    ],
)
def test_state_keeps_schema_and_environment(name, schema_version, environment_type):
    state = state_for(name)

    assert state.schema_version == schema_version
    assert type(state.environment) is environment_type
    assert state.has_sweep
    assert not state.has_radiation_pattern
    assert state.theta is None and state.phi is None


def test_state_from_schema_4_project_with_pattern():
    state = state_for("dipole-20m-radiation-pattern.yaas")

    assert state.schema_version == 4
    assert state.has_radiation_pattern
    # theta se conserva tal como lo define el proyecto, sin pasar a
    # elevación.
    assert state.theta == AngularSweep(start_deg=0.0, count=181, step_deg=1.0)
    assert state.theta.stop_deg == 180.0
    assert state.phi == AngularSweep(start_deg=0.0, count=1, step_deg=0.0)


def test_state_reuses_the_project_values_without_copying_the_project():
    opened = open_project(EXAMPLES / "dipole-20m-real-ground.yaas")

    state = ProjectViewState.from_opened_project(opened)

    assert state.path is opened.path
    assert state.environment is opened.project.environment
    assert not any(
        isinstance(getattr(state, field.name), OpenedProject)
        for field in dataclasses.fields(state)
    )


def test_state_is_immutable():
    state = state_for("dipole-20m.yaas")

    with pytest.raises(dataclasses.FrozenInstanceError):
        state.name = "other"


def valid_fields(**changes):
    fields = dataclasses.asdict(state_for("dipole-20m.yaas"))
    fields["environment"] = FreeSpaceEnvironment()
    fields.update(changes)
    return fields


@pytest.mark.parametrize(
    ("changes", "error"),
    [
        ({"path": "dipole-20m.yaas"}, TypeError),
        ({"environment": "free_space"}, TypeError),
        ({"theta": AngularSweep(0.0, 1, 0.0)}, ValueError),
        ({"phi": AngularSweep(0.0, 1, 0.0)}, ValueError),
    ],
)
def test_state_validates_invariants(changes, error):
    with pytest.raises(error):
        ProjectViewState(**valid_fields(**changes))


def test_state_module_does_not_load_qt():
    code = (
        "import sys\n"
        "import yaas.gui.controllers.project_state\n"
        "import yaas.gui.texts\n"
        "loaded = [name for name in ('PySide6', 'shiboken6', 'matplotlib',\n"
        "          'PyNEC', 'yaas.engines.pynec') if name in sys.modules]\n"
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
