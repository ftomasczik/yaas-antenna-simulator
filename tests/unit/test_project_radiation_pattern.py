"""simulation.radiation_pattern (schema_version=4): modelo, lectura y escritura.

Los datos de archivo de este módulo se escriben a mano y son
independientes del escritor actual: ``project_to_dict()`` siempre
emite la versión vigente, así que no sirve para fabricar archivos
históricos (v1/v2/v3) ni para comprobar el lector de forma
independiente.
"""

import copy
import dataclasses
import json
import math
from pathlib import Path

import pytest

from yaas.domain import (
    AngularSweep,
    FreeSpaceEnvironment,
    PerfectGroundEnvironment,
    RealGroundEnvironment,
)
from yaas.projects import (
    CURRENT_SCHEMA_VERSION,
    SUPPORTED_SCHEMA_VERSIONS,
    ProjectFormatError,
    RadiationPatternSettings,
    load_project,
    project_from_dict,
    project_to_dict,
    save_project,
)

FREE_SPACE_DICT = {"kind": "free_space"}
PERFECT_GROUND_DICT = {"kind": "perfect_ground"}
REAL_GROUND_DICT = {
    "kind": "real_ground",
    "model": "sommerfeld_norton",
    "relative_permittivity": 13.0,
    "conductivity_s_per_m": 0.005,
}

VERTICAL_FREE_SPACE = {
    "theta": {"start_deg": 0.0, "count": 181, "step_deg": 1.0},
    "phi": {"start_deg": 0.0, "count": 1, "step_deg": 0.0},
}
VERTICAL_WITH_GROUND = {
    "theta": {"start_deg": 0.0, "count": 91, "step_deg": 1.0},
    "phi": {"start_deg": 0.0, "count": 1, "step_deg": 0.0},
}
FULL_AZIMUTH = {
    "theta": {"start_deg": 90.0, "count": 1, "step_deg": 0.0},
    "phi": {"start_deg": 0.0, "count": 361, "step_deg": 1.0},
}


def file_dict(
    schema_version: int = 4,
    environment: dict | None = FREE_SPACE_DICT,
    radiation_pattern: dict | None = None,
) -> dict:
    """Archivo ``.yaas`` escrito a mano.

    El monopolo toca z=0 en un solo extremo, así que es válido con los
    tres entornos. ``environment=None`` reproduce un archivo v1.
    ``description`` y ``swr_limit`` se incluyen para que el round-trip
    dict -> proyecto -> dict pueda compararse de forma exacta.
    """
    simulation: dict = {
        "frequency_mhz": 14.15,
        "reference_impedance_ohm": 50.0,
    }
    if environment is not None:
        simulation["environment"] = copy.deepcopy(environment)
    simulation["sweep"] = {
        "start_mhz": 13.5,
        "stop_mhz": 15.5,
        "points": 81,
        "swr_limit": 2.0,
    }
    if radiation_pattern is not None:
        simulation["radiation_pattern"] = copy.deepcopy(radiation_pattern)

    return {
        "schema_version": schema_version,
        "project": {"name": "Monopolo", "description": ""},
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


def with_axis(axis: str, **fields) -> dict:
    """Patrón vertical de espacio libre con campos reemplazados en un eje."""
    pattern = copy.deepcopy(VERTICAL_FREE_SPACE)
    pattern[axis].update(fields)
    return pattern


# ---------------------------------------------------------------------------
# Contrato de versiones
# ---------------------------------------------------------------------------


def test_schema_constants():
    assert CURRENT_SCHEMA_VERSION == 4
    assert SUPPORTED_SCHEMA_VERSIONS == (1, 2, 3, 4)


@pytest.mark.parametrize(
    "example_path,expected_schema_version,expected_environment",
    [
        ("examples/dipole-20m.yaas", 1, FreeSpaceEnvironment()),
        (
            "examples/monopole-20m-perfect-ground.yaas",
            2,
            PerfectGroundEnvironment(),
        ),
        (
            "examples/dipole-20m-real-ground.yaas",
            3,
            RealGroundEnvironment(
                relative_permittivity=13.0,
                conductivity_s_per_m=0.005,
            ),
        ),
    ],
)
def test_historical_examples_still_load_and_convert(
    example_path,
    expected_schema_version,
    expected_environment,
):
    project = load_project(Path(example_path))

    assert project.schema_version == expected_schema_version
    assert project.radiation_pattern is None

    simulation_request = project.to_simulation_request()
    sweep_request = project.to_sweep_request()

    assert simulation_request.frequency_mhz == 14.15
    assert simulation_request.environment == expected_environment
    assert (
        sweep_request.start_frequency_mhz,
        sweep_request.stop_frequency_mhz,
        sweep_request.points,
    ) == (13.5, 15.5, 81)
    assert sweep_request.environment == expected_environment


# ---------------------------------------------------------------------------
# Lectura v4: casos válidos
# ---------------------------------------------------------------------------


def test_reads_v4_without_radiation_pattern():
    project = project_from_dict(file_dict())

    assert project.schema_version == 4
    assert project.radiation_pattern is None

    with pytest.raises(ValueError, match="no define un patrón"):
        project.to_radiation_pattern_request()


@pytest.mark.parametrize(
    "environment_dict,pattern,expected_shape",
    [
        (FREE_SPACE_DICT, VERTICAL_FREE_SPACE, (181, 1)),
        (PERFECT_GROUND_DICT, VERTICAL_WITH_GROUND, (91, 1)),
        (REAL_GROUND_DICT, VERTICAL_WITH_GROUND, (91, 1)),
        (FREE_SPACE_DICT, FULL_AZIMUTH, (1, 361)),
        (REAL_GROUND_DICT, FULL_AZIMUTH, (1, 361)),
    ],
    ids=[
        "free_space_181x1",
        "perfect_ground_91x1",
        "real_ground_91x1",
        "free_space_azimuth_0_to_360",
        "real_ground_azimuth_0_to_360",
    ],
)
def test_reads_v4_radiation_pattern(environment_dict, pattern, expected_shape):
    project = project_from_dict(
        file_dict(environment=environment_dict, radiation_pattern=pattern)
    )
    settings = project.radiation_pattern

    assert settings == RadiationPatternSettings(
        theta=AngularSweep(**pattern["theta"]),
        phi=AngularSweep(**pattern["phi"]),
    )
    assert (settings.theta.count, settings.phi.count) == expected_shape


def test_reads_full_azimuth_including_0_and_360():
    project = project_from_dict(file_dict(radiation_pattern=FULL_AZIMUTH))
    phi = project.radiation_pattern.phi

    assert phi.angles_deg[0] == 0.0
    assert phi.angles_deg[-1] == phi.stop_deg == 360.0


def test_reads_single_point_axes_with_zero_step():
    pattern = {
        "theta": {"start_deg": 90.0, "count": 1, "step_deg": 0.0},
        "phi": {"start_deg": 90.0, "count": 1, "step_deg": 0.0},
    }

    project = project_from_dict(file_dict(radiation_pattern=pattern))

    assert project.radiation_pattern.theta.angles_deg == (90.0,)
    assert project.radiation_pattern.phi.angles_deg == (90.0,)


def test_reads_integer_json_numbers_for_angles():
    # JSON no distingue 0 de 0.0 como tipo numérico: ambos son números.
    pattern = with_axis("theta", start_deg=0, step_deg=1)

    project = project_from_dict(file_dict(radiation_pattern=pattern))

    assert project.radiation_pattern.theta.stop_deg == 180


# ---------------------------------------------------------------------------
# Conversión a RadiationPatternRequest
# ---------------------------------------------------------------------------


def test_to_radiation_pattern_request_reuses_project_data():
    project = project_from_dict(
        file_dict(
            environment=REAL_GROUND_DICT,
            radiation_pattern=VERTICAL_WITH_GROUND,
        )
    )

    request = project.to_radiation_pattern_request()

    assert request.wires is project.wires
    assert request.source is project.source
    assert request.environment is project.environment
    assert request.frequency_mhz == project.frequency_mhz == 14.15
    assert request.theta is project.radiation_pattern.theta
    assert request.phi is project.radiation_pattern.phi


# ---------------------------------------------------------------------------
# Escritura
# ---------------------------------------------------------------------------


def test_writer_omits_radiation_pattern_when_absent():
    data = project_to_dict(project_from_dict(file_dict()))

    assert data["schema_version"] == 4
    assert "radiation_pattern" not in data["simulation"]


def test_writer_emits_the_exact_radiation_pattern_json():
    project = project_from_dict(
        file_dict(radiation_pattern=VERTICAL_FREE_SPACE)
    )

    pattern = project_to_dict(project)["simulation"]["radiation_pattern"]

    assert pattern == {
        "theta": {"start_deg": 0.0, "count": 181, "step_deg": 1.0},
        "phi": {"start_deg": 0.0, "count": 1, "step_deg": 0.0},
    }
    # Orden estable: theta antes que phi; start_deg, count, step_deg.
    assert list(pattern) == ["theta", "phi"]
    for axis in ("theta", "phi"):
        assert list(pattern[axis]) == ["start_deg", "count", "step_deg"]
    # Números JSON, nunca strings; sin campos derivados como stop_deg.
    assert type(pattern["theta"]["count"]) is int
    assert type(pattern["theta"]["start_deg"]) is float
    assert "stop_deg" not in json.dumps(pattern)


@pytest.mark.parametrize(
    "environment_dict,pattern",
    [
        (FREE_SPACE_DICT, None),
        (FREE_SPACE_DICT, VERTICAL_FREE_SPACE),
        (PERFECT_GROUND_DICT, VERTICAL_WITH_GROUND),
        (REAL_GROUND_DICT, FULL_AZIMUTH),
    ],
    ids=["no_pattern", "free_space", "perfect_ground", "real_ground"],
)
def test_round_trip_dict_project_dict(environment_dict, pattern):
    original = file_dict(
        environment=environment_dict,
        radiation_pattern=pattern,
    )

    assert project_to_dict(project_from_dict(original)) == original


@pytest.mark.parametrize(
    "pattern",
    [None, VERTICAL_WITH_GROUND],
    ids=["no_pattern", "with_pattern"],
)
def test_round_trip_file_project_file(tmp_path, pattern):
    source = tmp_path / "original.yaas"
    source.write_text(
        json.dumps(
            file_dict(
                environment=PERFECT_GROUND_DICT,
                radiation_pattern=pattern,
            )
        ),
        encoding="utf-8",
    )

    loaded = load_project(source)
    first = tmp_path / "primera.yaas"
    save_project(loaded, first)
    reloaded = load_project(first)
    second = tmp_path / "segunda.yaas"
    save_project(reloaded, second)

    assert reloaded == loaded
    assert reloaded.radiation_pattern == loaded.radiation_pattern
    assert second.read_text(encoding="utf-8") == first.read_text(
        encoding="utf-8"
    )


def test_saving_does_not_mutate_the_loaded_project():
    project = project_from_dict(
        file_dict(
            schema_version=4,
            environment=REAL_GROUND_DICT,
            radiation_pattern=VERTICAL_WITH_GROUND,
        )
    )
    snapshot = copy.deepcopy(project)

    data = project_to_dict(project)
    # Modificar el dict generado tampoco afecta al proyecto.
    data["simulation"]["radiation_pattern"]["theta"]["count"] = 1

    assert project == snapshot
    assert project.radiation_pattern.theta.count == 91


# ---------------------------------------------------------------------------
# Lectura v4: errores estructurales (tipos JSON y claves exactas)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", [None, [], "patrón", 1, True])
def test_rejects_radiation_pattern_that_is_not_an_object(value):
    data = file_dict()
    data["simulation"]["radiation_pattern"] = value

    with pytest.raises(
        ProjectFormatError,
        match=r"simulation\.radiation_pattern: se esperaba un objeto",
    ):
        project_from_dict(data)


@pytest.mark.parametrize("axis", ["theta", "phi"])
def test_rejects_missing_axis(axis):
    pattern = copy.deepcopy(VERTICAL_FREE_SPACE)
    del pattern[axis]

    with pytest.raises(
        ProjectFormatError,
        match=rf"simulation\.radiation_pattern\.{axis}: falta",
    ):
        project_from_dict(file_dict(radiation_pattern=pattern))


@pytest.mark.parametrize(
    "extra_key",
    ["frequency_mhz", "normalization", "azimuth"],
)
def test_rejects_extra_key_in_radiation_pattern(extra_key):
    pattern = copy.deepcopy(VERTICAL_FREE_SPACE)
    pattern[extra_key] = 0

    with pytest.raises(
        ProjectFormatError,
        match=rf"simulation\.radiation_pattern: no se admiten claves "
        rf"adicionales \({extra_key}\)",
    ):
        project_from_dict(file_dict(radiation_pattern=pattern))


@pytest.mark.parametrize("axis", ["theta", "phi"])
@pytest.mark.parametrize("value", [None, [], "0..180", 1.0])
def test_rejects_axis_that_is_not_an_object(axis, value):
    pattern = copy.deepcopy(VERTICAL_FREE_SPACE)
    pattern[axis] = value

    with pytest.raises(
        ProjectFormatError,
        match=rf"radiation_pattern\.{axis}: se esperaba un objeto",
    ):
        project_from_dict(file_dict(radiation_pattern=pattern))


@pytest.mark.parametrize("axis", ["theta", "phi"])
@pytest.mark.parametrize("field", ["start_deg", "count", "step_deg"])
def test_rejects_missing_axis_field(axis, field):
    pattern = copy.deepcopy(VERTICAL_FREE_SPACE)
    del pattern[axis][field]

    with pytest.raises(
        ProjectFormatError,
        match=rf"radiation_pattern\.{axis}\.{field}: falta",
    ):
        project_from_dict(file_dict(radiation_pattern=pattern))


@pytest.mark.parametrize("axis", ["theta", "phi"])
@pytest.mark.parametrize("extra_field", ["stop_deg", "unit"])
def test_rejects_extra_axis_field(axis, extra_field):
    pattern = with_axis(axis, **{extra_field: 0})

    with pytest.raises(
        ProjectFormatError,
        match=rf"radiation_pattern\.{axis}: no se admiten claves "
        rf"adicionales \({extra_field}\)",
    ):
        project_from_dict(file_dict(radiation_pattern=pattern))


@pytest.mark.parametrize("axis", ["theta", "phi"])
@pytest.mark.parametrize("field", ["start_deg", "step_deg"])
@pytest.mark.parametrize(
    "value",
    ["0", None, [], {}, True, False, math.nan, math.inf, -math.inf],
    ids=[
        "string", "null", "list", "object", "true", "false",
        "nan", "inf", "-inf",
    ],
)
def test_rejects_invalid_angle_field_type(axis, field, value):
    pattern = with_axis(axis, **{field: value})

    with pytest.raises(
        ProjectFormatError,
        match=rf"radiation_pattern\.{axis}\.{field}: se esperaba un "
        "número finito",
    ):
        project_from_dict(file_dict(radiation_pattern=pattern))


@pytest.mark.parametrize("axis", ["theta", "phi"])
@pytest.mark.parametrize(
    "value",
    ["1", None, [], {}, True, False, 1.0, math.nan],
    ids=[
        "string", "null", "list", "object", "true", "false",
        "float", "nan",
    ],
)
def test_rejects_invalid_count_type(axis, value):
    pattern = with_axis(axis, count=value)

    with pytest.raises(
        ProjectFormatError,
        match=rf"radiation_pattern\.{axis}\.count: se esperaba un entero",
    ):
        project_from_dict(file_dict(radiation_pattern=pattern))


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
def test_load_project_rejects_non_finite_json_literals(tmp_path, literal):
    # json.load acepta NaN/Infinity como extensión no estándar; el
    # lector los rechaza con la validación numérica existente.
    text = json.dumps(file_dict(radiation_pattern=VERTICAL_FREE_SPACE))
    text = text.replace(
        '"step_deg": 1.0',
        f'"step_deg": {literal}',
    )
    destination = tmp_path / "proyecto.yaas"
    destination.write_text(text, encoding="utf-8")

    with pytest.raises(
        ProjectFormatError,
        match=r"radiation_pattern\.theta\.step_deg: se esperaba un "
        "número finito",
    ):
        load_project(destination)


# ---------------------------------------------------------------------------
# Lectura v4: reglas de dominio (AngularSweep y RadiationPatternRequest)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("axis", ["theta", "phi"])
@pytest.mark.parametrize(
    "fields,match",
    [
        ({"count": 0}, "entero positivo"),
        ({"count": -1}, "entero positivo"),
        ({"step_deg": -1.0}, "no puede ser negativo"),
        ({"count": 2, "step_deg": 0.0}, "debe ser positivo"),
        (
            {"start_deg": 1e308, "count": 3, "step_deg": 1e308},
            "ángulo final",
        ),
    ],
    ids=[
        "count_zero",
        "count_negative",
        "negative_step",
        "zero_step_with_two_points",
        "non_finite_stop",
    ],
)
def test_rejects_invalid_angular_sweep_rules(axis, fields, match):
    pattern = with_axis(axis, **fields)

    with pytest.raises(
        ProjectFormatError,
        match=rf"simulation\.radiation_pattern\.{axis}: .*{match}",
    ):
        project_from_dict(file_dict(radiation_pattern=pattern))


@pytest.mark.parametrize(
    "environment_dict,pattern,match",
    [
        (
            FREE_SPACE_DICT,
            with_axis("theta", start_deg=-1.0),
            "theta inicial",
        ),
        (
            FREE_SPACE_DICT,
            with_axis("theta", count=182),
            "theta final no puede superar 180",
        ),
        (
            PERFECT_GROUND_DICT,
            VERTICAL_FREE_SPACE,
            "plano de tierra.*90 grados",
        ),
        (
            REAL_GROUND_DICT,
            VERTICAL_FREE_SPACE,
            "plano de tierra.*90 grados",
        ),
        (
            REAL_GROUND_DICT,
            with_axis("theta", start_deg=0.0, count=92),
            "plano de tierra.*90 grados",
        ),
        (
            FREE_SPACE_DICT,
            with_axis("phi", start_deg=-1.0),
            "phi inicial",
        ),
        (
            FREE_SPACE_DICT,
            with_axis("phi", count=362, step_deg=1.0),
            "phi final no puede superar 360",
        ),
    ],
    ids=[
        "theta_negative",
        "theta_above_180_free_space",
        "theta_above_90_perfect_ground",
        "theta_above_90_real_ground",
        "theta_91_real_ground",
        "phi_negative",
        "phi_above_360",
    ],
)
def test_rejects_pattern_outside_the_environment_domain(
    environment_dict,
    pattern,
    match,
):
    # Falla al cargar, no recién al simular, y el mensaje ubica el campo.
    data = file_dict(environment=environment_dict, radiation_pattern=pattern)

    with pytest.raises(
        ProjectFormatError,
        match=rf"simulation\.radiation_pattern: .*{match}",
    ):
        project_from_dict(data)


def test_rejects_unknown_environment_kind_in_v4():
    data = file_dict(
        environment={"kind": "underground"},
        radiation_pattern=VERTICAL_WITH_GROUND,
    )

    with pytest.raises(ProjectFormatError, match=r"environment\.kind"):
        project_from_dict(data)


def test_other_project_errors_keep_their_own_context():
    # Un error ajeno al patrón no se atribuye a radiation_pattern.
    data = file_dict(radiation_pattern=VERTICAL_FREE_SPACE)
    data["source"]["wire_tag"] = 99

    with pytest.raises(ProjectFormatError) as error:
        project_from_dict(data)

    assert "radiation_pattern" not in str(error.value)
    assert "conductor inexistente" in str(error.value)


# ---------------------------------------------------------------------------
# radiation_pattern en versiones anteriores
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "schema_version,environment_dict",
    [
        (1, None),
        (2, FREE_SPACE_DICT),
        (2, PERFECT_GROUND_DICT),
        (3, REAL_GROUND_DICT),
    ],
    ids=["v1", "v2-free_space", "v2-perfect_ground", "v3-real_ground"],
)
def test_rejects_radiation_pattern_before_v4(schema_version, environment_dict):
    data = file_dict(
        schema_version=schema_version,
        environment=environment_dict,
        radiation_pattern=VERTICAL_WITH_GROUND,
    )

    with pytest.raises(
        ProjectFormatError,
        match=rf"simulation\.radiation_pattern: no se admite en "
        rf"schema_version={schema_version}",
    ):
        project_from_dict(data)


@pytest.mark.parametrize(
    "schema_version,environment_dict",
    [(1, None), (2, PERFECT_GROUND_DICT), (3, REAL_GROUND_DICT)],
    ids=["v1", "v2", "v3"],
)
def test_historical_versions_without_pattern_still_load(
    schema_version,
    environment_dict,
):
    project = project_from_dict(
        file_dict(schema_version=schema_version, environment=environment_dict)
    )

    assert project.schema_version == schema_version
    assert project.radiation_pattern is None


# ---------------------------------------------------------------------------
# Modelo de proyecto
# ---------------------------------------------------------------------------


def test_radiation_pattern_settings_is_immutable():
    settings = RadiationPatternSettings(
        theta=AngularSweep(start_deg=0.0, count=91, step_deg=1.0),
        phi=AngularSweep(start_deg=0.0, count=1, step_deg=0.0),
    )

    with pytest.raises(dataclasses.FrozenInstanceError):
        settings.theta = settings.phi  # type: ignore[misc]


@pytest.mark.parametrize("field", ["theta", "phi"])
@pytest.mark.parametrize(
    "value",
    [None, {"start_deg": 0.0, "count": 1, "step_deg": 0.0}],
    ids=["none", "dict"],
)
def test_radiation_pattern_settings_requires_angular_sweeps(field, value):
    values = {
        "theta": AngularSweep(start_deg=0.0, count=1, step_deg=0.0),
        "phi": AngularSweep(start_deg=0.0, count=1, step_deg=0.0),
    }
    values[field] = value

    with pytest.raises(ValueError, match=f"{field} debe ser un AngularSweep"):
        RadiationPatternSettings(**values)


def test_project_rejects_incoherent_pattern_at_construction():
    project = project_from_dict(file_dict(environment=PERFECT_GROUND_DICT))
    settings = RadiationPatternSettings(
        theta=AngularSweep(start_deg=0.0, count=181, step_deg=1.0),
        phi=AngularSweep(start_deg=0.0, count=1, step_deg=0.0),
    )

    with pytest.raises(ValueError, match="plano de tierra"):
        dataclasses.replace(project, radiation_pattern=settings)


def test_project_with_unknown_environment_and_pattern_is_rejected():
    class _UnknownEnvironment:
        pass

    project = project_from_dict(file_dict())

    with pytest.raises(ValueError, match="entorno desconocido"):
        dataclasses.replace(
            project,
            environment=_UnknownEnvironment(),
            radiation_pattern=RadiationPatternSettings(
                theta=AngularSweep(start_deg=0.0, count=1, step_deg=0.0),
                phi=AngularSweep(start_deg=0.0, count=1, step_deg=0.0),
            ),
        )
