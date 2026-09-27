import json

import pytest

from antsim.domain import (
    PerfectGroundEnvironment,
    Point3D,
    VoltageSource,
    Wire,
)
from antsim.projects import (
    AntennaProject,
    ProjectMetadata,
    SweepSettings,
    project_to_dict,
    save_project,
)


def create_project() -> AntennaProject:
    return AntennaProject(
        metadata=ProjectMetadata(
            name="Dipolo de 20 metros",
            description="Proyecto de referencia.",
        ),
        wires=(
            Wire(
                tag=1,
                start=Point3D(-5.03, 0.0, 0.0),
                end=Point3D(5.03, 0.0, 0.0),
                radius_m=0.001,
                segments=101,
            ),
        ),
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


def test_project_to_dict_uses_schema_version():
    data = project_to_dict(create_project())

    # Todo proyecto escrito por la versión actual usa schema 2, sin
    # importar el schema_version en memoria del objeto (ver
    # test_writing_migrates_v1_in_memory_project_to_v2 más abajo).
    assert data["schema_version"] == 2
    assert data["project"]["name"] == (
        "Dipolo de 20 metros"
    )
    assert data["geometry"]["wires"][0]["tag"] == 1
    assert data["simulation"]["frequency_mhz"] == 14.15
    assert data["simulation"]["environment"] == {"kind": "free_space"}


def test_save_project_creates_readable_json(tmp_path):
    destination = tmp_path / "dipolo.antsim"

    created_path = save_project(
        project=create_project(),
        destination=destination,
    )

    assert created_path == destination
    assert destination.exists()

    with destination.open(encoding="utf-8") as file:
        data = json.load(file)

    assert data["schema_version"] == 2
    assert data["source"]["type"] == "voltage"
    assert data["simulation"]["sweep"]["points"] == 81


def test_save_project_preserves_unicode(tmp_path):
    destination = tmp_path / "dipolo.antsim"

    save_project(
        project=create_project(),
        destination=destination,
    )

    contents = destination.read_text(encoding="utf-8")

    assert "Dipolo de 20 metros" in contents


def test_save_project_requires_antsim_extension(tmp_path):
    destination = tmp_path / "dipolo.json"

    with pytest.raises(ValueError):
        save_project(
            project=create_project(),
            destination=destination,
        )


# ---------------------------------------------------------------------------
# environment (fase 7A)
# ---------------------------------------------------------------------------


def create_ground_compatible_project(environment) -> AntennaProject:
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
        ),
        environment=environment,
    )


def test_project_to_dict_writes_perfect_ground_as_schema_2():
    project = create_ground_compatible_project(PerfectGroundEnvironment())

    data = project_to_dict(project)

    assert data["schema_version"] == 2
    assert data["simulation"]["environment"] == {"kind": "perfect_ground"}


def test_unknown_environment_type_does_not_serialize_silently():
    class _UnknownEnvironment:
        pass

    project = create_ground_compatible_project(_UnknownEnvironment())

    with pytest.raises(ValueError):
        project_to_dict(project)