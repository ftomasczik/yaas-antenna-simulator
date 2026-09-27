import json
from pathlib import Path

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
    ProjectFormatError,
    ProjectMetadata,
    SweepSettings,
    load_project,
    project_from_dict,
    save_project,
    project_to_dict,
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


def test_project_round_trip(tmp_path):
    original = create_project()
    destination = tmp_path / "dipolo.antsim"

    save_project(original, destination)
    loaded = load_project(destination)

    assert loaded == original


def test_project_from_dict_loads_project():
    project = create_project()

    data = {
        "schema_version": 1,
        "project": {
            "name": project.metadata.name,
            "description": project.metadata.description,
        },
        "geometry": {
            "wires": [
                {
                    "tag": 1,
                    "start_m": [-5.03, 0.0, 0.0],
                    "end_m": [5.03, 0.0, 0.0],
                    "radius_m": 0.001,
                    "segments": 101,
                }
            ]
        },
        "source": {
            "type": "voltage",
            "wire_tag": 1,
            "segment": 51,
            "voltage_real": 1.0,
            "voltage_imag": 0.0,
        },
        "simulation": {
            "frequency_mhz": 14.15,
            "reference_impedance_ohm": 50.0,
            "sweep": {
                "start_mhz": 13.5,
                "stop_mhz": 15.5,
                "points": 81,
                "swr_limit": 2.0,
            },
        },
    }

    loaded = project_from_dict(data)

    assert loaded.metadata.name == "Dipolo de 20 metros"
    assert loaded.wires[0].segments == 101
    # Item 1: un archivo v1 conserva schema_version=1 en memoria y se
    # interpreta siempre como espacio libre.
    assert loaded.schema_version == 1
    assert loaded.environment == FreeSpaceEnvironment()


def test_load_project_rejects_invalid_json(tmp_path):
    destination = tmp_path / "invalid.antsim"
    destination.write_text(
        "{ invalid json",
        encoding="utf-8",
    )

    with pytest.raises(ProjectFormatError):
        load_project(destination)


def test_project_rejects_missing_required_field():
    data = {
        "schema_version": 1,
        "project": {
            "name": "Proyecto incompleto",
        },
    }

    with pytest.raises(ProjectFormatError):
        project_from_dict(data)


def test_project_rejects_unknown_source_type():
    data = {
        "schema_version": 1,
        "project": {
            "name": "Proyecto",
        },
        "geometry": {
            "wires": [],
        },
        "source": {
            "type": "current",
        },
        "simulation": {
            "frequency_mhz": 14.15,
            "reference_impedance_ohm": 50.0,
            "sweep": {
                "start_mhz": 13.5,
                "stop_mhz": 15.5,
                "points": 81,
            },
        },
    }

    with pytest.raises(ProjectFormatError):
        project_from_dict(data)


def test_load_project_rejects_wrong_extension(tmp_path):
    destination = tmp_path / "project.json"
    destination.write_text(
        json.dumps({}),
        encoding="utf-8",
    )

    with pytest.raises(ProjectFormatError, match="project.json"):
        load_project(destination)


@pytest.mark.parametrize("path,value", [
    (("project", "name"), 123),
    (("project", "description"), []),
    (("project",), []),
    (("geometry", "wires"), {}),
    (("geometry", "wires", 0), None),
    (("geometry", "wires", 0, "start_m"), "123"),
    (("geometry", "wires", 0, "start_m"), [0, 1]),
    (("geometry", "wires", 0, "start_m", 0), True),
    (("geometry", "wires", 0, "tag"), True),
    (("geometry", "wires", 0, "segments"), 2.5),
    (("source", "segment"), 1.5),
    (("source", "voltage_real"), "1"),
    (("simulation", "frequency_mhz"), True),
    (("simulation", "frequency_mhz"), 10 ** 400),
    (("simulation", "frequency_mhz"), float("nan")),
    (("simulation", "sweep"), None),
    (("schema_version",), True),
    (("schema_version",), 1.0),
    (("schema_version",), 999),
])
def test_project_rejects_invalid_fields_with_context(path, value):
    data = project_to_dict(create_project())
    parent = data
    for key in path[:-1]:
        parent = parent[key]
    parent[path[-1]] = value
    with pytest.raises(ProjectFormatError) as error:
        project_from_dict(data)
    assert str(path[0]) in str(error.value)


@pytest.mark.parametrize("data", [None, [], 123, "project", True])
def test_project_rejects_non_object_root(data):
    with pytest.raises(ProjectFormatError, match="raíz"):
        project_from_dict(data)


def test_missing_nested_field_has_full_context():
    data = project_to_dict(create_project())
    del data["simulation"]["sweep"]["points"]
    with pytest.raises(ProjectFormatError, match=r"simulation\.sweep\.points"):
        project_from_dict(data)


@pytest.mark.parametrize("contents", [b'not JSON', b'\xff', b'{"project":'])
def test_load_invalid_content_reports_path(tmp_path, contents):
    source = tmp_path / "invalid.antsim"
    source.write_bytes(contents)
    with pytest.raises(ProjectFormatError) as error:
        load_project(source)
    assert str(source) in str(error.value)


def test_load_invalid_field_reports_path_and_field(tmp_path):
    source = tmp_path / "invalid.antsim"
    data = project_to_dict(create_project())
    data["project"]["name"] = 123
    source.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ProjectFormatError) as error:
        load_project(source)
    assert str(source) in str(error.value)
    assert "project.name" in str(error.value)


def test_optional_fields_keep_existing_defaults():
    data = project_to_dict(create_project())
    del data["project"]["description"]
    del data["simulation"]["sweep"]["swr_limit"]
    result = project_from_dict(data)
    assert result.metadata.description == ""
    assert result.sweep.swr_limit == 2.0


# ---------------------------------------------------------------------------
# environment / schema_version 1<->2 (fase 7A)
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
        ),
        environment=environment,
    )


def test_reads_v2_free_space():
    data = project_to_dict(create_project())
    assert data["schema_version"] == 2

    loaded = project_from_dict(data)

    assert loaded.schema_version == 2
    assert loaded.environment == FreeSpaceEnvironment()


def test_reads_v2_perfect_ground():
    project = create_ground_compatible_project(PerfectGroundEnvironment())
    data = project_to_dict(project)

    loaded = project_from_dict(data)

    assert loaded.schema_version == 2
    assert loaded.environment == PerfectGroundEnvironment()


def test_rejects_v2_without_environment():
    data = project_to_dict(create_project())
    del data["simulation"]["environment"]

    with pytest.raises(ProjectFormatError, match=r"simulation\.environment"):
        project_from_dict(data)


def test_rejects_unknown_environment_kind():
    data = project_to_dict(create_project())
    data["simulation"]["environment"] = {"kind": "underground"}

    with pytest.raises(ProjectFormatError, match="kind"):
        project_from_dict(data)


def test_rejects_environment_with_extra_keys():
    data = project_to_dict(create_project())
    data["simulation"]["environment"] = {
        "kind": "free_space",
        "height_m": 5.0,
    }

    with pytest.raises(ProjectFormatError, match="claves adicionales"):
        project_from_dict(data)


@pytest.mark.parametrize("bad_environment", [None, "free_space", []])
def test_rejects_wrong_type_for_environment(bad_environment):
    data = project_to_dict(create_project())
    data["simulation"]["environment"] = bad_environment

    with pytest.raises(ProjectFormatError, match=r"simulation\.environment"):
        project_from_dict(data)


@pytest.mark.parametrize("bad_version", [0, 3, 999])
def test_rejects_unsupported_schema_versions(bad_version):
    data = project_to_dict(create_project())
    data["schema_version"] = bad_version

    with pytest.raises(ProjectFormatError, match="schema_version"):
        project_from_dict(data)


def test_rejects_v1_with_stray_environment():
    data = project_to_dict(create_project())
    data["schema_version"] = 1
    # Un archivo v1 nunca debería declarar environment; si lo hace,
    # se rechaza en vez de ignorarlo en silencio.
    with pytest.raises(ProjectFormatError, match="schema_version=1"):
        project_from_dict(data)


def test_round_trip_v2_perfect_ground(tmp_path):
    original = create_ground_compatible_project(PerfectGroundEnvironment())
    destination = tmp_path / "monopolo.antsim"

    save_project(original, destination)
    loaded = load_project(destination)

    assert loaded == original
    assert loaded.environment == PerfectGroundEnvironment()


def test_reading_v1_and_saving_migrates_to_v2_free_space(tmp_path):
    source = Path("examples/dipole-20m.antsim")
    original = load_project(source)
    assert original.schema_version == 1  # precondición del fixture histórico

    destination = tmp_path / "migrado.antsim"
    save_project(original, destination)

    with destination.open(encoding="utf-8") as file:
        migrated_data = json.load(file)

    assert migrated_data["schema_version"] == 2
    assert migrated_data["simulation"]["environment"] == {
        "kind": "free_space"
    }

    reloaded = load_project(destination)
    assert reloaded.schema_version == 2
    assert reloaded.environment == FreeSpaceEnvironment()


def test_saving_does_not_mutate_the_original_project_in_memory():
    original = load_project(Path("examples/dipole-20m.antsim"))
    original_schema_version = original.schema_version
    original_environment = original.environment

    project_to_dict(original)

    assert original.schema_version == original_schema_version
    assert original.environment == original_environment


def test_existing_v1_example_project_still_loads():
    project = load_project(Path("examples/dipole-20m.antsim"))

    assert project.schema_version == 1
    assert project.environment == FreeSpaceEnvironment()
    assert project.metadata.name == "Dipolo de 20 metros"


def test_requests_after_round_trip_preserve_environment(tmp_path):
    original = create_ground_compatible_project(PerfectGroundEnvironment())
    destination = tmp_path / "monopolo.antsim"

    save_project(original, destination)
    loaded = load_project(destination)

    assert (
        loaded.to_simulation_request().environment
        == PerfectGroundEnvironment()
    )
    assert (
        loaded.to_sweep_request().environment
        == PerfectGroundEnvironment()
    )
