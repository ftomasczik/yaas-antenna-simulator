"""Integración mínima: el controlador de la GUI con el motor PyNEC real.

El resto de las pruebas del cálculo usa motores falsos; esta comprueba
una sola vez el camino real (fábrica por defecto, worker, PyNEC) y que
el resultado coincide con el del caso de uso que usa la CLI.
"""

from pathlib import Path

import pytest

pytest.importorskip("PySide6.QtWidgets")
pytest.importorskip("PyNEC")

from qt_offscreen import configure_offscreen  # noqa: E402

configure_offscreen()

from PySide6.QtWidgets import QApplication  # noqa: E402

from pattern_fakes import wait_until  # noqa: E402
from yaas.application import (  # noqa: E402
    calculate_radiation_pattern,
    prepare_radiation_pattern_request,
)
from yaas.engines.pynec import PyNecEngine  # noqa: E402
from yaas.gui.controllers.pattern import (  # noqa: E402
    PatternCalculationState as State,
    RadiationPatternController,
)
from yaas.gui.controllers.project import ProjectController  # noqa: E402

V4 = Path(__file__).resolve().parents[2] / "examples" / "dipole-20m-radiation-pattern.yaas"


@pytest.fixture(scope="module", autouse=True)
def application():
    return QApplication.instance() or QApplication([])


def test_real_engine_matches_the_application_workflow():
    projects = ProjectController()
    patterns = RadiationPatternController(projects)
    try:
        projects.open_project(V4)

        assert patterns.calculate()
        wait_until(
            lambda: not patterns.is_busy, QApplication.processEvents, timeout_s=60
        )

        assert patterns.state is State.RESULT, patterns.last_error
        expected = calculate_radiation_pattern(
            prepare_radiation_pattern_request(projects.opened_project.project),
            engine=PyNecEngine(),
        )
        assert patterns.analysis == expected
        assert len(patterns.analysis.result.theta_angles_deg) == 181
    finally:
        patterns.shutdown()
        assert patterns.runner.thread_count == 0
