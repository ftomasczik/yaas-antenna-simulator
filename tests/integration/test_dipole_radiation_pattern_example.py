"""Ejemplo examples/dipole-20m-radiation-pattern.yaas (schema v4).

Mismo dipolo de referencia que examples/dipole-20m.yaas (v1), con un
corte vertical del patrón de radiación. Valores de referencia:
docs/validation/radiation-patterns-4nec2.md.
"""

from pathlib import Path

import pytest

from yaas.domain import AngularSweep, FreeSpaceEnvironment
from yaas.engines import PyNecEngine
from yaas.projects import load_project, save_project

EXAMPLE = Path("examples/dipole-20m-radiation-pattern.yaas")
HISTORICAL_DIPOLE = Path("examples/dipole-20m.yaas")


@pytest.fixture(scope="module")
def project():
    return load_project(EXAMPLE)


@pytest.fixture(scope="module")
def result(project):
    return PyNecEngine().simulate_radiation_pattern(
        project.to_radiation_pattern_request()
    )


def test_example_is_schema_4_with_a_vertical_cut(project):
    assert project.schema_version == 4
    assert project.environment == FreeSpaceEnvironment()
    assert project.radiation_pattern.theta == AngularSweep(
        start_deg=0.0, count=181, step_deg=1.0
    )
    assert project.radiation_pattern.phi == AngularSweep(
        start_deg=0.0, count=1, step_deg=0.0
    )


def test_example_reuses_the_historical_dipole(project):
    historical = load_project(HISTORICAL_DIPOLE)

    assert project.wires == historical.wires
    assert project.source == historical.source
    assert project.frequency_mhz == historical.frequency_mhz == 14.15
    assert project.reference_impedance == historical.reference_impedance
    assert project.sweep == historical.sweep


def test_example_file_matches_the_current_writer(project, tmp_path):
    # El ejemplo se generó con save_project(): volver a guardarlo
    # produce exactamente el mismo archivo.
    destination = tmp_path / "copia.yaas"
    save_project(project, destination)

    assert destination.read_bytes() == EXAMPLE.read_bytes()


def test_example_pattern_matches_documented_values(result):
    gains = [row[0] for row in result.gain_db]
    finite_gains = [gain for gain in gains if gain is not None]

    assert result.shape == (181, 1)
    assert max(finite_gains) == pytest.approx(2.1233, abs=1e-3)
    assert gains[0] == max(finite_gains)
    assert gains[90] is None
    assert gains.count(None) == 1
    assert gains[180] == pytest.approx(gains[0], abs=1e-6)
