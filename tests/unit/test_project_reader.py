import json

import pytest

from antsim.domain import (
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

    with pytest.raises(ValueError):
        load_project(destination)
        