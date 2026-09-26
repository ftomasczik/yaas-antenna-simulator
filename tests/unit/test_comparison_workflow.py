import pytest

from antsim.application import (
    ComparisonRequestError,
    compare_project_measurement,
)
from antsim.domain import (
    MeasurementPoint,
    MeasurementSweep,
    Point3D,
    SweepPoint,
    SweepResult,
    VoltageSource,
    Wire,
)
from antsim.projects import AntennaProject, ProjectMetadata, SweepSettings


def _project() -> AntennaProject:
    wire = Wire(
        tag=1,
        start=Point3D(-5.0, 0.0, 0.0),
        end=Point3D(5.0, 0.0, 0.0),
        radius_m=0.001,
        segments=11,
    )
    return AntennaProject(
        metadata=ProjectMetadata(name="Test dipole"),
        wires=(wire,),
        source=VoltageSource(wire_tag=1, segment=6),
        frequency_mhz=14.0,
        reference_impedance=50.0,
        sweep=SweepSettings(
            start_frequency_mhz=14.0,
            stop_frequency_mhz=15.0,
            points=2,
        ),
    )


class _FakeEngine:
    """Motor de prueba que no depende de PyNEC."""

    def __init__(self, result=None, error=None):
        self._result = result
        self._error = error

    def simulate(self, request):
        raise NotImplementedError

    def simulate_sweep(self, request):
        if self._error is not None:
            raise self._error
        return self._result


def test_compare_project_measurement_delegates_to_compare_sweeps():
    project = _project()
    simulated = SweepResult(
        (
            SweepPoint(14.0, complex(50, 0), 1.0),
            SweepPoint(15.0, complex(60, 10), 1.3),
        )
    )
    measurement = MeasurementSweep(
        (
            MeasurementPoint(
                14.0,
                (complex(55, 0) - 50) / (complex(55, 0) + 50),
                50.0,
            ),
        )
    )

    comparison = compare_project_measurement(
        project=project,
        measurement=measurement,
        reference_impedance=50.0,
        engine=_FakeEngine(result=simulated),
    )

    assert comparison.reference_impedance == 50.0
    assert len(comparison.points) == 1
    assert comparison.points[0].simulated_impedance == pytest.approx(
        50 + 0j
    )
    assert comparison.points[0].measured_impedance == pytest.approx(
        55 + 0j
    )


def test_compare_project_measurement_propagates_runtime_engine_errors_undisguised():
    """Un RuntimeError del motor no debe convertirse en ComparisonRequestError."""
    project = _project()
    measurement = MeasurementSweep(
        (MeasurementPoint(14.0, complex(0.1, 0.0), 50.0),)
    )

    with pytest.raises(RuntimeError, match="native failure"):
        compare_project_measurement(
            project=project,
            measurement=measurement,
            reference_impedance=50.0,
            engine=_FakeEngine(
                error=RuntimeError("native failure")
            ),
        )


def test_compare_project_measurement_propagates_engine_value_errors_undisguised():
    """Un ValueError del propio motor tampoco debe reclasificarse."""
    project = _project()
    measurement = MeasurementSweep(
        (MeasurementPoint(14.0, complex(0.1, 0.0), 50.0),)
    )

    with pytest.raises(ValueError, match="fallo del motor") as exc_info:
        compare_project_measurement(
            project=project,
            measurement=measurement,
            reference_impedance=50.0,
            engine=_FakeEngine(
                error=ValueError("fallo del motor")
            ),
        )

    assert not isinstance(exc_info.value, ComparisonRequestError)


def test_compare_project_measurement_wraps_compare_sweeps_value_error():
    """Solo el ValueError de compare_sweeps se convierte en ComparisonRequestError."""
    project = _project()
    simulated = SweepResult(
        (SweepPoint(14.0, complex(50, 0), 1.0),)
    )
    # Frecuencia medida fuera del rango simulado: compare_sweeps
    # rechaza la solicitud por falta de solapamiento.
    measurement = MeasurementSweep(
        (MeasurementPoint(20.0, complex(0.1, 0.0), 50.0),)
    )

    with pytest.raises(
        ComparisonRequestError, match="No hay frecuencias"
    ) as exc_info:
        compare_project_measurement(
            project=project,
            measurement=measurement,
            reference_impedance=50.0,
            engine=_FakeEngine(result=simulated),
        )

    assert isinstance(exc_info.value.__cause__, ValueError)
    assert not isinstance(
        exc_info.value.__cause__, ComparisonRequestError
    )
