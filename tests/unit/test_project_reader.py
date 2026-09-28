import json
from pathlib import Path

import pytest

from yaas.domain import (
    FreeSpaceEnvironment,
    PerfectGroundEnvironment,
    Point3D,
    RealGroundEnvironment,
    VoltageSource,
    Wire,
)
from yaas.projects import (
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
    destination = tmp_path / "dipolo.yaas"

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
    destination = tmp_path / "invalid.yaas"
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


def test_load_project_rejects_antsim_extension(tmp_path):
    """Corte limpio: el nombre anterior del formato (.antsim) ya no se
    admite, ni siquiera con contenido JSON por lo demás válido."""
    destination = tmp_path / "project.antsim"
    destination.write_text(
        json.dumps(project_to_dict(create_project())),
        encoding="utf-8",
    )

    with pytest.raises(ProjectFormatError, match="project.antsim"):
        load_project(destination)


@pytest.mark.parametrize(
    "example_path,expected_schema_version",
    [
        ("examples/dipole-20m.yaas", 1),
        ("examples/monopole-20m-perfect-ground.yaas", 2),
        ("examples/dipole-20m-real-ground.yaas", 3),
    ],
)
def test_yaas_examples_load_with_expected_schema_version(
    example_path, expected_schema_version
):
    project = load_project(example_path)

    assert project.schema_version == expected_schema_version


def test_no_tracked_example_uses_the_antsim_extension():
    """Ningun ejemplo del repositorio conserva la extension anterior."""
    examples_dir = Path("examples")

    assert list(examples_dir.glob("*.antsim")) == []


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
    source = tmp_path / "invalid.yaas"
    source.write_bytes(contents)
    with pytest.raises(ProjectFormatError) as error:
        load_project(source)
    assert str(source) in str(error.value)


def test_load_invalid_field_reports_path_and_field(tmp_path):
    source = tmp_path / "invalid.yaas"
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
# environment / schema_version 1<->2<->3 (fase 7A/7B)
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


def _historical_dict(schema_version: int, environment_dict: dict | None) -> dict:
    """Construye un dict "de archivo" independiente del escritor actual.

    A diferencia de partir de ``project_to_dict(create_project())``
    (que siempre refleja el comportamiento del escritor de hoy), este
    fixture representa un archivo ``.yaas`` histórico tal como
    podría existir en disco, con ``schema_version`` fijado
    explícitamente. ``environment_dict=None`` reproduce un archivo v1
    (sin la clave ``environment``).
    """
    simulation: dict = {
        "frequency_mhz": 14.15,
        "reference_impedance_ohm": 50.0,
        "sweep": {
            "start_mhz": 13.5,
            "stop_mhz": 15.5,
            "points": 81,
        },
    }
    if environment_dict is not None:
        simulation["environment"] = environment_dict

    return {
        "schema_version": schema_version,
        "project": {"name": "Proyecto histórico"},
        "geometry": {
            "wires": [
                {
                    "tag": 1,
                    "start_m": [0.0, 0.0, 0.0],
                    "end_m": [0.0, 0.0, 5.03],
                    "radius_m": 0.001,
                    "segments": 38,
                }
            ]
        },
        "source": {
            "type": "voltage",
            "wire_tag": 1,
            "segment": 1,
            "voltage_real": 1.0,
            "voltage_imag": 0.0,
        },
        "simulation": simulation,
    }


_REAL_GROUND_DICT = {
    "kind": "real_ground",
    "model": "sommerfeld_norton",
    "relative_permittivity": 13.0,
    "conductivity_s_per_m": 0.005,
}


def _real_ground_dict_with(**overrides) -> dict:
    data = dict(_REAL_GROUND_DICT)
    data.update(overrides)
    return data


def _real_ground_dict_without(*missing_keys: str) -> dict:
    return {
        key: value
        for key, value in _REAL_GROUND_DICT.items()
        if key not in missing_keys
    }


@pytest.mark.parametrize(
    "environment_dict,expected_environment",
    [
        ({"kind": "free_space"}, FreeSpaceEnvironment()),
        ({"kind": "perfect_ground"}, PerfectGroundEnvironment()),
    ],
)
def test_reads_historical_v2_file(environment_dict, expected_environment):
    """Un archivo v2 real (no derivado del escritor actual) sigue
    leyéndose exactamente igual que antes de agregar schema 3."""
    data = _historical_dict(2, environment_dict)

    loaded = project_from_dict(data)

    assert loaded.schema_version == 2
    assert loaded.environment == expected_environment


def test_rejects_real_ground_in_historical_v2_file():
    data = _historical_dict(2, _REAL_GROUND_DICT)

    with pytest.raises(ProjectFormatError, match="kind"):
        project_from_dict(data)


def test_rejects_v2_without_environment():
    data = _historical_dict(2, {"kind": "free_space"})
    del data["simulation"]["environment"]

    with pytest.raises(ProjectFormatError, match=r"simulation\.environment"):
        project_from_dict(data)


@pytest.mark.parametrize(
    "environment",
    [
        FreeSpaceEnvironment(),
        PerfectGroundEnvironment(),
        RealGroundEnvironment(
            relative_permittivity=13.0,
            conductivity_s_per_m=0.005,
        ),
    ],
)
def test_reads_v3_each_kind(environment):
    project = create_ground_compatible_project(environment)
    data = project_to_dict(project)
    assert data["schema_version"] == 3

    loaded = project_from_dict(data)

    assert loaded.schema_version == 3
    assert loaded.environment == environment


def test_rejects_v3_without_environment():
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


@pytest.mark.parametrize("bad_version", [0, 4, 999])
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


# ---------------------------------------------------------------------------
# real_ground: forma exacta y errores estructurales (fase 7B)
# ---------------------------------------------------------------------------


def test_reads_v3_real_ground_exact_values():
    project = create_ground_compatible_project(
        RealGroundEnvironment(
            relative_permittivity=13.0,
            conductivity_s_per_m=0.005,
        )
    )
    data = project_to_dict(project)
    assert data["simulation"]["environment"] == {
        "kind": "real_ground",
        "model": "sommerfeld_norton",
        "relative_permittivity": 13.0,
        "conductivity_s_per_m": 0.005,
    }

    loaded = project_from_dict(data)

    assert loaded.environment.relative_permittivity == 13.0
    assert loaded.environment.conductivity_s_per_m == 0.005


@pytest.mark.parametrize(
    "environment_dict,match",
    [
        pytest.param(
            _real_ground_dict_with(model="reflection_coefficient"),
            "model",
            id="unknown-model-value",
        ),
        pytest.param(
            _real_ground_dict_with(model=2),
            "model",
            id="model-not-a-string",
        ),
        pytest.param(
            _real_ground_dict_without("model"),
            "model",
            id="missing-model",
        ),
        pytest.param(
            _real_ground_dict_without("relative_permittivity"),
            "relative_permittivity",
            id="missing-permittivity",
        ),
        pytest.param(
            _real_ground_dict_without("conductivity_s_per_m"),
            "conductivity_s_per_m",
            id="missing-conductivity",
        ),
        pytest.param(
            _real_ground_dict_with(relative_permittivity="13.0"),
            "relative_permittivity",
            id="permittivity-numeric-string",
        ),
        pytest.param(
            _real_ground_dict_with(relative_permittivity=None),
            "relative_permittivity",
            id="permittivity-null",
        ),
        pytest.param(
            _real_ground_dict_with(relative_permittivity=[13.0]),
            "relative_permittivity",
            id="permittivity-list",
        ),
        pytest.param(
            _real_ground_dict_with(relative_permittivity={"value": 13.0}),
            "relative_permittivity",
            id="permittivity-object",
        ),
        pytest.param(
            _real_ground_dict_with(relative_permittivity=True),
            "relative_permittivity",
            id="permittivity-bool",
        ),
        pytest.param(
            _real_ground_dict_with(relative_permittivity=float("nan")),
            "relative_permittivity",
            id="permittivity-nan",
        ),
        pytest.param(
            _real_ground_dict_with(relative_permittivity=float("inf")),
            "relative_permittivity",
            id="permittivity-infinity",
        ),
        pytest.param(
            _real_ground_dict_with(conductivity_s_per_m="0.005"),
            "conductivity_s_per_m",
            id="conductivity-numeric-string",
        ),
        pytest.param(
            _real_ground_dict_with(conductivity_s_per_m=None),
            "conductivity_s_per_m",
            id="conductivity-null",
        ),
        pytest.param(
            _real_ground_dict_with(conductivity_s_per_m=[0.005]),
            "conductivity_s_per_m",
            id="conductivity-list",
        ),
        pytest.param(
            _real_ground_dict_with(conductivity_s_per_m={"value": 0.005}),
            "conductivity_s_per_m",
            id="conductivity-object",
        ),
        pytest.param(
            _real_ground_dict_with(conductivity_s_per_m=False),
            "conductivity_s_per_m",
            id="conductivity-bool",
        ),
        pytest.param(
            _real_ground_dict_with(conductivity_s_per_m=float("-inf")),
            "conductivity_s_per_m",
            id="conductivity-negative-infinity",
        ),
        pytest.param(
            _real_ground_dict_with(extra_field=1.0),
            "claves adicionales",
            id="extra-key",
        ),
    ],
)
def test_rejects_invalid_real_ground_environment(environment_dict, match):
    data = project_to_dict(create_project())
    data["simulation"]["environment"] = environment_dict

    with pytest.raises(ProjectFormatError, match=match):
        project_from_dict(data)


@pytest.mark.parametrize(
    "environment_dict",
    [
        _real_ground_dict_with(relative_permittivity=0.0),
        _real_ground_dict_with(relative_permittivity=-1.0),
        _real_ground_dict_with(conductivity_s_per_m=-0.005),
    ],
)
def test_rejects_real_ground_domain_invariants(environment_dict):
    """La permitividad no positiva y la conductividad negativa son
    válidas como JSON (números finitos) pero inválidas como dominio:
    RealGroundEnvironment.__post_init__ las rechaza, y el lector
    traduce ese ValueError a ProjectFormatError."""
    data = project_to_dict(create_project())
    data["simulation"]["environment"] = environment_dict

    with pytest.raises(ProjectFormatError):
        project_from_dict(data)


def test_rejects_real_ground_in_schema_2():
    data = project_to_dict(create_project())
    data["schema_version"] = 2
    data["simulation"]["environment"] = _REAL_GROUND_DICT

    with pytest.raises(ProjectFormatError, match="kind"):
        project_from_dict(data)


def test_rejects_real_ground_in_schema_1():
    data = project_to_dict(create_project())
    data["schema_version"] = 1
    data["simulation"]["environment"] = _REAL_GROUND_DICT

    with pytest.raises(ProjectFormatError, match="schema_version=1"):
        project_from_dict(data)


# ---------------------------------------------------------------------------
# Round trip, migración y no-mutación (v1/v2 -> v3)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "environment",
    [
        FreeSpaceEnvironment(),
        PerfectGroundEnvironment(),
        RealGroundEnvironment(
            relative_permittivity=13.0,
            conductivity_s_per_m=0.005,
        ),
    ],
)
def test_round_trip_v3_each_kind(tmp_path, environment):
    original = create_ground_compatible_project(environment)
    destination = tmp_path / "proyecto.yaas"

    save_project(original, destination)
    loaded = load_project(destination)

    assert loaded == original
    assert loaded.environment == environment
    assert loaded.schema_version == 3


def test_reading_v1_and_saving_migrates_to_v3_free_space(tmp_path):
    source = Path("examples/dipole-20m.yaas")
    original = load_project(source)
    assert original.schema_version == 1  # precondición del fixture histórico

    destination = tmp_path / "migrado.yaas"
    save_project(original, destination)

    with destination.open(encoding="utf-8") as file:
        migrated_data = json.load(file)

    assert migrated_data["schema_version"] == 3
    assert migrated_data["simulation"]["environment"] == {
        "kind": "free_space"
    }

    reloaded = load_project(destination)
    assert reloaded.schema_version == 3
    assert reloaded.environment == FreeSpaceEnvironment()


@pytest.mark.parametrize(
    "environment_dict,expected_environment",
    [
        ({"kind": "free_space"}, FreeSpaceEnvironment()),
        ({"kind": "perfect_ground"}, PerfectGroundEnvironment()),
    ],
)
def test_reading_v2_and_saving_migrates_to_v3(
    tmp_path, environment_dict, expected_environment
):
    original = project_from_dict(_historical_dict(2, environment_dict))
    assert original.schema_version == 2  # precondición del fixture histórico

    destination = tmp_path / "migrado.yaas"
    save_project(original, destination)

    with destination.open(encoding="utf-8") as file:
        migrated_data = json.load(file)

    assert migrated_data["schema_version"] == 3
    assert migrated_data["simulation"]["environment"] == environment_dict

    reloaded = load_project(destination)
    assert reloaded.schema_version == 3
    assert reloaded.environment == expected_environment


def test_reading_v3_real_ground_and_saving_keeps_v3_real_ground(tmp_path):
    environment = RealGroundEnvironment(
        relative_permittivity=13.0,
        conductivity_s_per_m=0.005,
    )
    original = create_ground_compatible_project(environment)
    destination = tmp_path / "real_ground.yaas"

    save_project(original, destination)
    loaded = load_project(destination)
    assert loaded.schema_version == 3

    # Guardarlo de nuevo no cambia nada: ya estaba en la versión
    # actual y con el mismo entorno.
    destination_again = tmp_path / "real_ground_otra_vez.yaas"
    save_project(loaded, destination_again)
    reloaded = load_project(destination_again)

    assert reloaded.schema_version == 3
    assert reloaded.environment == environment


def test_saving_does_not_mutate_the_original_project_in_memory():
    original = load_project(Path("examples/dipole-20m.yaas"))
    original_schema_version = original.schema_version
    original_environment = original.environment

    project_to_dict(original)

    assert original.schema_version == original_schema_version
    assert original.environment == original_environment


def test_saving_does_not_mutate_a_loaded_v2_project_in_memory():
    original = project_from_dict(
        _historical_dict(2, {"kind": "perfect_ground"})
    )
    assert original.schema_version == 2

    project_to_dict(original)

    assert original.schema_version == 2
    assert original.environment == PerfectGroundEnvironment()


def test_existing_v1_example_project_still_loads():
    project = load_project(Path("examples/dipole-20m.yaas"))

    assert project.schema_version == 1
    assert project.environment == FreeSpaceEnvironment()
    assert project.metadata.name == "Dipolo de 20 metros"


@pytest.mark.parametrize(
    "environment",
    [
        FreeSpaceEnvironment(),
        PerfectGroundEnvironment(),
        RealGroundEnvironment(
            relative_permittivity=13.0,
            conductivity_s_per_m=0.005,
        ),
    ],
)
def test_requests_after_round_trip_preserve_environment(tmp_path, environment):
    original = create_ground_compatible_project(environment)
    destination = tmp_path / "proyecto.yaas"

    save_project(original, destination)
    loaded = load_project(destination)

    assert loaded.to_simulation_request().environment == environment
    assert loaded.to_sweep_request().environment == environment
