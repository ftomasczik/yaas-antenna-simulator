import pytest

from antsim.domain import (
    FreeSpaceEnvironment,
    PerfectGroundEnvironment,
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


@pytest.mark.parametrize("schema_version", [1, 2])
def test_project_accepts_supported_schema_versions(schema_version):
    project = create_project()

    accepted = AntennaProject(
        metadata=project.metadata,
        wires=project.wires,
        source=project.source,
        frequency_mhz=project.frequency_mhz,
        reference_impedance=project.reference_impedance,
        sweep=project.sweep,
        schema_version=schema_version,
    )

    assert accepted.schema_version == schema_version


@pytest.mark.parametrize("schema_version", [0, 3])
def test_project_rejects_other_unsupported_schema_versions(schema_version):
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
            schema_version=schema_version,
        )


def test_sweep_settings_reject_invalid_limit():
    with pytest.raises(ValueError):
        SweepSettings(
            start_frequency_mhz=13.5,
            stop_frequency_mhz=15.5,
            points=81,
            swr_limit=0.5,
        )


# ---------------------------------------------------------------------------
# Environment en AntennaProject (fase 7A)
# ---------------------------------------------------------------------------


def create_ground_compatible_project(environment) -> AntennaProject:
    """Proyecto con un conductor vertical, compatible con tierra.

    A diferencia de ``create_project()`` (un dipolo horizontal con
    ambos extremos en z=0, válido solo en espacio libre), este
    conductor toca el plano de tierra en un único extremo.
    """
    wire = Wire(
        tag=1,
        start=Point3D(0.0, 0.0, 0.0),
        end=Point3D(0.0, 0.0, 5.03),
        radius_m=0.001,
        segments=38,
    )

    return AntennaProject(
        metadata=ProjectMetadata(name="Monopolo sobre tierra perfecta"),
        wires=(wire,),
        source=VoltageSource(wire_tag=1, segment=1),
        frequency_mhz=14.15,
        reference_impedance=50.0,
        sweep=SweepSettings(
            start_frequency_mhz=13.5,
            stop_frequency_mhz=15.5,
            points=81,
            swr_limit=2.0,
        ),
        environment=environment,
    )


def test_project_defaults_to_free_space():
    project = create_project()

    assert project.environment == FreeSpaceEnvironment()


def test_project_accepts_perfect_ground_explicitly():
    project = create_ground_compatible_project(PerfectGroundEnvironment())

    assert project.environment == PerfectGroundEnvironment()


def test_to_simulation_request_preserves_perfect_ground():
    project = create_ground_compatible_project(PerfectGroundEnvironment())

    request = project.to_simulation_request()

    assert request.environment == PerfectGroundEnvironment()


def test_to_sweep_request_preserves_perfect_ground():
    project = create_ground_compatible_project(PerfectGroundEnvironment())

    request = project.to_sweep_request()

    assert request.environment == PerfectGroundEnvironment()


def test_free_space_project_conversions_keep_free_space():
    project = create_project()

    simulation_request = project.to_simulation_request()
    sweep_request = project.to_sweep_request()

    assert simulation_request.environment == FreeSpaceEnvironment()
    assert sweep_request.environment == FreeSpaceEnvironment()


def test_existing_project_constructors_keep_working_without_environment():
    # Ningún constructor existente menciona environment; deben seguir
    # funcionando igual y obtener espacio libre.
    project = create_project()

    assert project.environment == FreeSpaceEnvironment()
    assert project.to_simulation_request().environment == (
        FreeSpaceEnvironment()
    )
    assert project.to_sweep_request().environment == FreeSpaceEnvironment()
