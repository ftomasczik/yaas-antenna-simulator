"""Exportación NEC de un patrón de radiación (tarjeta RP de texto)."""

import dataclasses

import pytest

from yaas.domain import (
    AngularSweep,
    FreeSpaceEnvironment,
    PerfectGroundEnvironment,
    Point3D,
    RadiationPatternRequest,
    RealGroundEnvironment,
    SimulationRequest,
    VoltageSource,
    Wire,
)
from yaas.exporters import (
    export_radiation_pattern_nec,
    radiation_pattern_request_to_nec,
    simulation_request_to_nec,
    sweep_request_to_nec,
)
from yaas.projects import (
    AntennaProject,
    ProjectMetadata,
    RadiationPatternSettings,
    SweepSettings,
    load_project,
    save_project,
)

HEADER_50_OHM = (
    "CM Test dipole\n"
    "CM Reference impedance: 50 ohm\n"
    "CM Informational only: NEC/4nec2 may require manually "
    "setting this reference impedance to display SWR.\n"
    "CE\n"
)

VERTICAL_THETA = AngularSweep(start_deg=0.0, count=181, step_deg=1.0)
GROUND_THETA = AngularSweep(start_deg=0.0, count=91, step_deg=1.0)
SINGLE_PHI = AngularSweep(start_deg=0.0, count=1, step_deg=0.0)
HORIZON_THETA = AngularSweep(start_deg=90.0, count=1, step_deg=0.0)
FULL_PHI = AngularSweep(start_deg=0.0, count=361, step_deg=1.0)


def create_dipole_wire(height_m: float = 0.0) -> Wire:
    return Wire(
        tag=1,
        start=Point3D(-5.03, 0.0, height_m),
        end=Point3D(5.03, 0.0, height_m),
        radius_m=0.001,
        segments=101,
    )


def create_monopole_wire() -> Wire:
    return Wire(
        tag=1,
        start=Point3D(0.0, 0.0, 0.0),
        end=Point3D(0.0, 0.0, 5.03),
        radius_m=0.001,
        segments=38,
    )


def real_ground(conductivity_s_per_m: float = 0.005) -> RealGroundEnvironment:
    return RealGroundEnvironment(
        relative_permittivity=13.0,
        conductivity_s_per_m=conductivity_s_per_m,
    )


def create_pattern_request(
    wire: Wire | None = None,
    environment=FreeSpaceEnvironment(),
    segment: int = 51,
    theta: AngularSweep = VERTICAL_THETA,
    phi: AngularSweep = SINGLE_PHI,
    frequency_mhz: float = 14.15,
) -> RadiationPatternRequest:
    return RadiationPatternRequest(
        wires=(wire or create_dipole_wire(),),
        environment=environment,
        source=VoltageSource(wire_tag=1, segment=segment),
        frequency_mhz=frequency_mhz,
        theta=theta,
        phi=phi,
    )


def point_request_for(
    request: RadiationPatternRequest,
    reference_impedance: float = 50.0,
) -> SimulationRequest:
    """Exportación puntual equivalente: misma geometría, entorno,
    fuente y frecuencia."""
    return SimulationRequest(
        frequency_mhz=request.frequency_mhz,
        wires=request.wires,
        source=request.source,
        reference_impedance=reference_impedance,
        environment=request.environment,
    )


# Los tres entornos, cada uno con una geometría válida para él y un
# corte vertical dentro de su dominio de theta.
ENVIRONMENT_CASES = [
    pytest.param(
        create_dipole_wire(),
        FreeSpaceEnvironment(),
        51,
        VERTICAL_THETA,
        None,
        id="free_space",
    ),
    pytest.param(
        create_monopole_wire(),
        PerfectGroundEnvironment(),
        1,
        GROUND_THETA,
        "GN 1 0 0 0 0 0 0 0",
        id="perfect_ground",
    ),
    pytest.param(
        create_dipole_wire(height_m=10.0),
        real_ground(),
        51,
        GROUND_THETA,
        "GN 2 0 0 0 13 0.005 0 0 0 0",
        id="real_ground",
    ),
]


def card_names(nec_text: str) -> list[str]:
    return [line.split()[0] for line in nec_text.splitlines()]


def lines_starting_with(nec_text: str, prefix: str) -> list[str]:
    return [line for line in nec_text.splitlines() if line.startswith(prefix)]


def rp_fields(nec_text: str) -> list[str]:
    (rp_line,) = lines_starting_with(nec_text, "RP ")
    return rp_line.split()[1:]


def assert_card_order(nec_text: str, has_gn: bool) -> None:
    """última GW < GE < GN (si existe) < EX < FR < RP < EN, y EN al final."""
    names = card_names(nec_text)
    last_gw = max(i for i, name in enumerate(names) if name == "GW")
    sequence = [last_gw, names.index("GE")]
    if has_gn:
        sequence.append(names.index("GN"))
    else:
        assert "GN" not in names
    sequence += [
        names.index("EX"),
        names.index("FR"),
        names.index("RP"),
        names.index("EN"),
    ]

    assert sequence == sorted(sequence)
    assert len(set(sequence)) == len(sequence)
    assert names[-1] == "EN"


# ---------------------------------------------------------------------------
# Texto completo exacto
# ---------------------------------------------------------------------------


def test_free_space_vertical_cut_exact_text():
    nec_text = radiation_pattern_request_to_nec(
        request=create_pattern_request(),
        title="Test dipole",
    )

    assert nec_text == (
        HEADER_50_OHM
        + "GW 1 101 -5.03 0 0 5.03 0 0 0.001\n"
        "GE 0\n"
        "EX 0 1 51 0 1 0\n"
        "FR 0 1 0 0 14.15 0\n"
        "RP 0 181 1 0000 0 0 1 0 0 0\n"
        "EN\n"
    )


def test_free_space_azimuth_cut_exact_text():
    nec_text = radiation_pattern_request_to_nec(
        request=create_pattern_request(theta=HORIZON_THETA, phi=FULL_PHI),
        title="Test dipole",
    )

    assert nec_text == (
        HEADER_50_OHM
        + "GW 1 101 -5.03 0 0 5.03 0 0 0.001\n"
        "GE 0\n"
        "EX 0 1 51 0 1 0\n"
        "FR 0 1 0 0 14.15 0\n"
        "RP 0 1 361 0000 90 0 0 1 0 0\n"
        "EN\n"
    )


# ---------------------------------------------------------------------------
# Estructura de la tarjeta RP
# ---------------------------------------------------------------------------


def test_rp_card_keeps_every_field_in_position():
    # Valores distintos en cada campo: cualquier intercambio theta/phi
    # o inicio/paso cambiaría la tarjeta.
    request = create_pattern_request(
        theta=AngularSweep(start_deg=10.0, count=3, step_deg=20.0),
        phi=AngularSweep(start_deg=15.0, count=5, step_deg=30.0),
    )

    fields = rp_fields(radiation_pattern_request_to_nec(request))

    # Diez campos después de RP: cuatro enteros (I4 = XNDA completo,
    # un solo token) y seis flotantes. No son los trece argumentos de
    # PyNEC.rp_card().
    assert len(fields) == 10
    assert fields[:4] == ["0", "3", "5", "0000"]
    assert fields[4:] == ["10", "15", "20", "30", "0", "0"]


def test_rp_card_formats_decimal_values():
    request = create_pattern_request(
        theta=AngularSweep(start_deg=0.5, count=3, step_deg=0.25),
        phi=AngularSweep(start_deg=12.5, count=2, step_deg=0.001),
        frequency_mhz=7.0,
    )

    nec_text = radiation_pattern_request_to_nec(request)

    assert rp_fields(nec_text) == [
        "0", "3", "2", "0000", "0.5", "12.5", "0.25", "0.001", "0", "0",
    ]
    assert lines_starting_with(nec_text, "FR ") == ["FR 0 1 0 0 7 0"]


def test_exactly_one_rp_and_no_xq():
    nec_text = radiation_pattern_request_to_nec(create_pattern_request())
    names = card_names(nec_text)

    assert names.count("RP") == 1
    assert "XQ" not in names


def test_frequency_card_is_single_point():
    nec_text = radiation_pattern_request_to_nec(create_pattern_request())

    # FR 0 1 ...: una sola frecuencia, paso 0; nunca un FR de barrido.
    assert lines_starting_with(nec_text, "FR ") == ["FR 0 1 0 0 14.15 0"]


# ---------------------------------------------------------------------------
# Los tres entornos
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "wire,environment,segment,theta,expected_gn",
    ENVIRONMENT_CASES,
)
def test_each_environment_orders_cards_and_keeps_ground_cards(
    wire, environment, segment, theta, expected_gn
):
    nec_text = radiation_pattern_request_to_nec(
        create_pattern_request(
            wire=wire,
            environment=environment,
            segment=segment,
            theta=theta,
        )
    )

    assert_card_order(nec_text, has_gn=expected_gn is not None)
    if expected_gn is None:
        assert lines_starting_with(nec_text, "GE ") == ["GE 0"]
        assert lines_starting_with(nec_text, "GN ") == []
    else:
        assert lines_starting_with(nec_text, "GE ") == ["GE 1"]
        assert lines_starting_with(nec_text, "GN ") == [expected_gn]
    assert lines_starting_with(nec_text, "RP ") == [
        f"RP 0 {theta.count} 1 0000 0 0 1 0 0 0"
    ]


@pytest.mark.parametrize(
    "wire,environment,segment,theta,expected_gn",
    ENVIRONMENT_CASES,
)
def test_only_difference_with_point_export_is_the_rp_card(
    wire, environment, segment, theta, expected_gn
):
    request = create_pattern_request(
        wire=wire,
        environment=environment,
        segment=segment,
        theta=theta,
    )

    pattern_text = radiation_pattern_request_to_nec(request, title="Modelo")
    point_text = simulation_request_to_nec(
        point_request_for(request),
        title="Modelo",
    )

    pattern_lines = pattern_text.splitlines()
    rp_index = card_names(pattern_text).index("RP")
    # Mismas líneas (CM/CE/GW/GE/GN/EX/FR/EN), en el mismo orden; la
    # única tarjeta adicional es RP, justo antes de EN.
    assert (
        pattern_lines[:rp_index] + pattern_lines[rp_index + 1:]
        == point_text.splitlines()
    )
    assert pattern_lines[rp_index + 1] == "EN"


def test_lossless_real_ground_formats_zero_conductivity():
    nec_text = radiation_pattern_request_to_nec(
        create_pattern_request(
            wire=create_dipole_wire(height_m=10.0),
            environment=RealGroundEnvironment(
                relative_permittivity=4.0,
                conductivity_s_per_m=0.0,
            ),
            theta=GROUND_THETA,
        )
    )

    assert lines_starting_with(nec_text, "GN ") == [
        "GN 2 0 0 0 4 0 0 0 0 0"
    ]


@pytest.mark.parametrize("reference_impedance", [50.0, 75.0])
def test_reference_impedance_comments_match_point_export(
    reference_impedance,
):
    request = create_pattern_request()

    pattern_text = radiation_pattern_request_to_nec(
        request,
        title="Test dipole",
        reference_impedance=reference_impedance,
    )
    point_text = simulation_request_to_nec(
        point_request_for(request, reference_impedance),
        title="Test dipole",
    )

    assert lines_starting_with(pattern_text, "CM ") == (
        lines_starting_with(point_text, "CM ")
    )
    assert (
        f"CM Reference impedance: {reference_impedance:g} ohm"
        in pattern_text.splitlines()
    )


# ---------------------------------------------------------------------------
# Errores
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "request_object",
    [
        None,
        "RP 0 181 1 0000 0 0 1 0 0 0",
        point_request_for(create_pattern_request()),
    ],
    ids=["none", "string", "simulation_request"],
)
def test_rejects_objects_that_are_not_pattern_requests(request_object):
    with pytest.raises(TypeError, match="RadiationPatternRequest"):
        radiation_pattern_request_to_nec(request_object)


def test_unknown_real_ground_model_keeps_explicit_error():
    # Mismo recurso que las pruebas históricas: un RealGroundEnvironment
    # construido sin __post_init__, con un modelo que el exportador no
    # sabe escribir.
    environment = object.__new__(RealGroundEnvironment)
    object.__setattr__(environment, "relative_permittivity", 13.0)
    object.__setattr__(environment, "conductivity_s_per_m", 0.005)
    object.__setattr__(environment, "model", "coeficiente_de_reflexion")

    request = create_pattern_request(
        wire=create_dipole_wire(height_m=10.0),
        environment=environment,
        theta=GROUND_THETA,
    )

    with pytest.raises(ValueError, match="RealGroundModel"):
        radiation_pattern_request_to_nec(request)


def test_unknown_environment_type_keeps_explicit_error():
    class _UnknownEnvironment:
        pass

    # El dominio ya impide construir la solicitud normalmente...
    with pytest.raises(ValueError, match="entorno desconocido"):
        create_pattern_request(environment=_UnknownEnvironment())

    # ...y, si se esquiva su validación, la defensa existente del
    # exportador sigue rechazando el entorno en vez de escribir un
    # archivo con un GE/GN inventado.
    request = object.__new__(RadiationPatternRequest)
    for field in dataclasses.fields(RadiationPatternRequest):
        object.__setattr__(
            request, field.name, getattr(create_pattern_request(), field.name)
        )
    object.__setattr__(request, "wires", (create_monopole_wire(),))
    object.__setattr__(request, "source", VoltageSource(wire_tag=1, segment=1))
    object.__setattr__(request, "environment", _UnknownEnvironment())

    with pytest.raises(ValueError, match="tipo de entorno"):
        radiation_pattern_request_to_nec(request)


# ---------------------------------------------------------------------------
# Flujo completo desde un proyecto v4
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "wire,environment,segment,theta,expected_gn",
    ENVIRONMENT_CASES,
)
def test_v4_project_round_trip_exports_rp(
    tmp_path, wire, environment, segment, theta, expected_gn
):
    project = AntennaProject(
        metadata=ProjectMetadata(name="Patrón"),
        wires=(wire,),
        source=VoltageSource(wire_tag=1, segment=segment),
        frequency_mhz=14.15,
        reference_impedance=75.0,
        sweep=SweepSettings(
            start_frequency_mhz=13.5,
            stop_frequency_mhz=15.5,
            points=81,
        ),
        environment=environment,
        radiation_pattern=RadiationPatternSettings(
            theta=theta,
            phi=SINGLE_PHI,
        ),
    )
    destination = tmp_path / "patron.yaas"
    save_project(project, destination)
    loaded = load_project(destination)
    assert loaded.schema_version == 4

    nec_text = radiation_pattern_request_to_nec(
        loaded.to_radiation_pattern_request(),
        title=loaded.metadata.name,
        reference_impedance=loaded.reference_impedance,
    )

    assert_card_order(nec_text, has_gn=expected_gn is not None)
    assert lines_starting_with(nec_text, "RP ") == [
        f"RP 0 {theta.count} 1 0000 0 0 1 0 0 0"
    ]
    assert lines_starting_with(nec_text, "FR ") == ["FR 0 1 0 0 14.15 0"]
    assert lines_starting_with(nec_text, "EX ") == [
        f"EX 0 1 {segment} 0 1 0"
    ]
    assert lines_starting_with(nec_text, "GN ") == (
        [] if expected_gn is None else [expected_gn]
    )
    assert "CM Reference impedance: 75 ohm" in nec_text.splitlines()


def test_project_without_pattern_fails_before_the_exporter():
    project = load_project("examples/dipole-20m.yaas")

    with pytest.raises(ValueError, match="no define un patrón"):
        project.to_radiation_pattern_request()


# ---------------------------------------------------------------------------
# Regresión: las exportaciones existentes no cambian
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "example_path,expected_ground_cards",
    [
        ("examples/dipole-20m.yaas", ["GE 0"]),
        (
            "examples/monopole-20m-perfect-ground.yaas",
            ["GE 1", "GN 1 0 0 0 0 0 0 0"],
        ),
        (
            "examples/dipole-20m-real-ground.yaas",
            ["GE 1", "GN 2 0 0 0 13 0.005 0 0 0 0"],
        ),
    ],
    ids=["v1", "v2", "v3"],
)
def test_historical_examples_export_without_rp(
    example_path, expected_ground_cards
):
    project = load_project(example_path)

    for nec_text in (
        simulation_request_to_nec(project.to_simulation_request()),
        sweep_request_to_nec(project.to_sweep_request()),
    ):
        assert (
            lines_starting_with(nec_text, "GE ")
            + lines_starting_with(nec_text, "GN ")
            == expected_ground_cards
        )
        assert "RP" not in card_names(nec_text)
        assert card_names(nec_text)[-1] == "EN"


# ---------------------------------------------------------------------------
# Escritura a archivo
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("as_string", [False, True], ids=["path", "str"])
def test_export_writes_exactly_the_in_memory_text(tmp_path, as_string):
    request = create_pattern_request()
    destination = tmp_path / "patron.nec"

    returned = export_radiation_pattern_nec(
        request=request,
        destination=str(destination) if as_string else destination,
        title="Test dipole",
        reference_impedance=75.0,
    )

    assert returned == destination
    # Mismo contrato que export_nec: UTF-8 y fin de línea LF.
    assert destination.read_bytes() == radiation_pattern_request_to_nec(
        request,
        title="Test dipole",
        reference_impedance=75.0,
    ).encode("utf-8")
    assert b"\r\n" not in destination.read_bytes()


def test_export_rejects_other_types_without_creating_a_file(tmp_path):
    destination = tmp_path / "patron.nec"

    with pytest.raises(TypeError, match="RadiationPatternRequest"):
        export_radiation_pattern_nec(
            request=point_request_for(create_pattern_request()),
            destination=destination,
        )

    assert not destination.exists()
