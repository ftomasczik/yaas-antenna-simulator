import pytest

from antsim.domain import (
    Point3D,
    VoltageSource,
    Wire,
)
from antsim.projects import (
    AntennaProject,
    ProjectMetadata,
    SweepSettings,
)


def create_project() -> AntennaProject:
    wire = Wire(
        tag=1,
        start=Point3D(-5.03, 0.0, 0.0),
        end=Point3D(5.03, 0.0, 0.0),
        radius_m=0.001,
        segments=101,
    )

    return AntennaProject(
        metadata=ProjectMetadata(
            name="Dipolo de 20 metros",
            description="Dipolo de referencia.",
        ),
        wires=(wire,),
        source=VoltageSource(
            wire_tag=1,
            segment=51,
        ),
        frequency_mhz=14.15,
        reference_impedance=50.0,
        sweep=SweepSettings(
            start_frequency_mhz=13.5,
            stop_frequency_mhz=15.5,
            points=81,
            swr_limit=2.0,
        ),
    )


def test_project_creates_single_frequency_request():
    project = create_project()

    request = project.to_simulation_request()

    assert request.frequency_mhz == 14.15
    assert request.reference_impedance == 50.0
    assert len(request.wires) == 1
    assert request.source.segment == 51


def test_project_creates_sweep_request():
    project = create_project()

    request = project.to_sweep_request()

    assert request.start_frequency_mhz == 13.5
    assert request.stop_frequency_mhz == 15.5
    assert request.points == 81


def test_project_requires_name():
    with pytest.raises(ValueError):
        ProjectMetadata(name="   ")


def test_project_rejects_unsupported_schema():
    project = create_project()

    with pytest.raises(ValueError):
        AntennaProject(
            metadata=project.metadata,
            wires=project.wires,
            source=project.source,
            frequency_mhz=project.frequency_mhz,
            reference_impedance=(
                project.reference_impedance
            ),
            sweep=project.sweep,
            schema_version=99,
        )


def test_sweep_settings_reject_invalid_limit():
    with pytest.raises(ValueError):
        SweepSettings(
            start_frequency_mhz=13.5,
            stop_frequency_mhz=15.5,
            points=81,
            swr_limit=0.5,
        )
        