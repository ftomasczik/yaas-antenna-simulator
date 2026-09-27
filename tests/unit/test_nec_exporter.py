import pytest

from antsim.domain import (
    FreeSpaceEnvironment,
    PerfectGroundEnvironment,
    Point3D,
    SimulationRequest,
    SweepRequest,
    VoltageSource,
    Wire,
)

from antsim.exporters import (
    export_nec,
    export_sweep_nec,
    simulation_request_to_nec,
    sweep_request_to_nec,
)

from antsim.projects import (
    AntennaProject,
    ProjectMetadata,
    SweepSettings,
    load_project,
    save_project,
)

def create_request() -> SimulationRequest:
    return SimulationRequest(
        frequency_mhz=14.15,
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
        reference_impedance=50.0,
    )


def test_simulation_request_to_nec():
    nec_text = simulation_request_to_nec(
        request=create_request(),
        title="Test dipole",
    )

    assert nec_text == (
        "CM Test dipole\n"
        "CM Reference impedance: 50 ohm\n"
        "CM Informational only: NEC/4nec2 may require manually "
        "setting this reference impedance to display SWR.\n"
        "CE\n"
        "GW 1 101 -5.03 0 0 5.03 0 0 0.001\n"
        "GE 0\n"
        "EX 0 1 51 0 1 0\n"
        "FR 0 1 0 0 14.15 0\n"
        "EN\n"
    )


def test_simulation_request_to_nec_reports_75_ohm_reference(tmp_path):
    request = SimulationRequest(
        frequency_mhz=14.15,
        wires=create_request().wires,
        source=create_request().source,
        reference_impedance=75.0,
    )

    nec_text = simulation_request_to_nec(
        request=request,
        title="Test dipole",
    )

    assert "CM Reference impedance: 75 ohm\n" in nec_text
    # El comentario es informativo: no cambia ninguna tarjeta eléctrica.
    assert "GW 1 101 -5.03 0 0 5.03 0 0 0.001\n" in nec_text
    assert "EX 0 1 51 0 1 0\n" in nec_text
    assert "FR 0 1 0 0 14.15 0\n" in nec_text


def test_export_nec(tmp_path):
    destination = tmp_path / "dipole.nec"

    result_path = export_nec(
        request=create_request(),
        destination=destination,
        title="Test dipole",
    )

    assert result_path == destination
    assert destination.is_file()
    assert destination.read_text(
        encoding="utf-8"
    ).endswith("EN\n")


def test_nec_title_is_restricted_to_one_line():
    nec_text = simulation_request_to_nec(
        request=create_request(),
        title="First line\nSecond line",
    )

    assert nec_text.startswith(
        "CM First line Second line\n"
        "CM Reference impedance: 50 ohm\n"
    )

def create_sweep_request() -> SweepRequest:
    request = create_request()

    return SweepRequest(
        start_frequency_mhz=13.5,
        stop_frequency_mhz=15.5,
        points=81,
        wires=request.wires,
        source=request.source,
        reference_impedance=(
            request.reference_impedance
        ),
    )


def test_sweep_request_to_nec():
    nec_text = sweep_request_to_nec(
        request=create_sweep_request(),
        title="Sweep dipole",
    )

    assert (
        "FR 0 81 0 0 13.5 0.025\n"
        in nec_text
    )
    assert nec_text.endswith("EN\n")
    assert "CM Reference impedance: 50 ohm\n" in nec_text


def test_sweep_request_to_nec_reports_75_ohm_reference():
    request = SweepRequest(
        start_frequency_mhz=13.5,
        stop_frequency_mhz=15.5,
        points=81,
        wires=create_request().wires,
        source=create_request().source,
        reference_impedance=75.0,
    )

    nec_text = sweep_request_to_nec(
        request=request,
        title="Sweep dipole",
    )

    assert "CM Reference impedance: 75 ohm\n" in nec_text
    # El comentario es informativo: no cambia ninguna tarjeta eléctrica.
    assert "FR 0 81 0 0 13.5 0.025\n" in nec_text
    assert "GW 1 101 -5.03 0 0 5.03 0 0 0.001\n" in nec_text


def test_export_sweep_nec(tmp_path):
    destination = tmp_path / "dipole-sweep.nec"

    result_path = export_sweep_nec(
        request=create_sweep_request(),
        destination=destination,
        title="Sweep dipole",
    )

    assert result_path == destination
    assert destination.is_file()
    assert (
        "FR 0 81 0 0 13.5 0.025\n"
        in destination.read_text(
            encoding="utf-8"
        )
    )


# ---------------------------------------------------------------------------
# environment (fase 7A): espacio libre y tierra perfecta
# ---------------------------------------------------------------------------


def create_monopole_wire() -> Wire:
    return Wire(
        tag=1,
        start=Point3D(0.0, 0.0, 0.0),
        end=Point3D(0.0, 0.0, 5.03),
        radius_m=0.001,
        segments=38,
    )


def create_perfect_ground_request() -> SimulationRequest:
    return SimulationRequest(
        frequency_mhz=14.15,
        wires=(create_monopole_wire(),),
        source=VoltageSource(wire_tag=1, segment=1),
        reference_impedance=50.0,
        environment=PerfectGroundEnvironment(),
    )


def create_perfect_ground_sweep_request() -> SweepRequest:
    return SweepRequest(
        start_frequency_mhz=13.5,
        stop_frequency_mhz=15.5,
        points=81,
        wires=(create_monopole_wire(),),
        source=VoltageSource(wire_tag=1, segment=1),
        reference_impedance=50.0,
        environment=PerfectGroundEnvironment(),
    )


def test_simulation_request_free_space_matches_historical_output_explicitly():
    # Item 1: mismo texto exacto que test_simulation_request_to_nec,
    # ahora con FreeSpaceEnvironment explícito (equivalente al valor
    # por defecto ya verificado arriba).
    request = SimulationRequest(
        frequency_mhz=14.15,
        wires=create_request().wires,
        source=create_request().source,
        reference_impedance=50.0,
        environment=FreeSpaceEnvironment(),
    )

    nec_text = simulation_request_to_nec(
        request=request, title="Test dipole"
    )

    assert nec_text == (
        "CM Test dipole\n"
        "CM Reference impedance: 50 ohm\n"
        "CM Informational only: NEC/4nec2 may require manually "
        "setting this reference impedance to display SWR.\n"
        "CE\n"
        "GW 1 101 -5.03 0 0 5.03 0 0 0.001\n"
        "GE 0\n"
        "EX 0 1 51 0 1 0\n"
        "FR 0 1 0 0 14.15 0\n"
        "EN\n"
    )


def test_sweep_request_free_space_matches_historical_output_exactly():
    # Item 2: texto completo exacto (no solo subcadenas), para dejar
    # fijada la salida histórica del barrido igual que ya está fijada
    # para la simulación puntual.
    nec_text = sweep_request_to_nec(
        request=create_sweep_request(),
        title="Sweep dipole",
    )

    assert nec_text == (
        "CM Sweep dipole\n"
        "CM Reference impedance: 50 ohm\n"
        "CM Informational only: NEC/4nec2 may require manually "
        "setting this reference impedance to display SWR.\n"
        "CE\n"
        "GW 1 101 -5.03 0 0 5.03 0 0 0.001\n"
        "GE 0\n"
        "EX 0 1 51 0 1 0\n"
        "FR 0 81 0 0 13.5 0.025\n"
        "EN\n"
    )


def test_simulation_perfect_ground_contains_ge_1():
    nec_text = simulation_request_to_nec(
        request=create_perfect_ground_request(),
        title="Monopole",
    )

    assert "GE 1\n" in nec_text


def test_simulation_perfect_ground_contains_gn_card():
    nec_text = simulation_request_to_nec(
        request=create_perfect_ground_request(),
        title="Monopole",
    )

    assert "GN 1 0 0 0 0 0 0 0\n" in nec_text


def test_ge_appears_after_the_last_gw():
    nec_text = simulation_request_to_nec(
        request=create_perfect_ground_request(),
        title="Monopole",
    )
    lines = nec_text.splitlines()

    last_gw_index = max(
        index
        for index, line in enumerate(lines)
        if line.startswith("GW ")
    )
    ge_index = lines.index("GE 1")

    assert ge_index > last_gw_index


def test_gn_appears_after_ge_and_before_ex_and_fr():
    nec_text = simulation_request_to_nec(
        request=create_perfect_ground_request(),
        title="Monopole",
    )
    lines = nec_text.splitlines()

    ge_index = lines.index("GE 1")
    gn_index = lines.index("GN 1 0 0 0 0 0 0 0")
    ex_index = next(
        index
        for index, line in enumerate(lines)
        if line.startswith("EX ")
    )
    fr_index = next(
        index
        for index, line in enumerate(lines)
        if line.startswith("FR ")
    )

    assert ge_index < gn_index < ex_index
    assert gn_index < fr_index


def test_sweep_perfect_ground_preserves_the_same_environment():
    nec_text = sweep_request_to_nec(
        request=create_perfect_ground_sweep_request(),
        title="Monopole sweep",
    )

    assert "GE 1\n" in nec_text
    assert "GN 1 0 0 0 0 0 0 0\n" in nec_text
    # Una única GE y una única GN: el mismo entorno para todo el
    # barrido, no una tarjeta por punto.
    assert nec_text.count("\nGE ") == 1
    assert nec_text.count("\nGN ") == 1


def test_reference_impedance_comments_remain_with_perfect_ground():
    request_50 = create_perfect_ground_request()
    request_75 = SimulationRequest(
        frequency_mhz=14.15,
        wires=request_50.wires,
        source=request_50.source,
        reference_impedance=75.0,
        environment=PerfectGroundEnvironment(),
    )

    nec_text_50 = simulation_request_to_nec(
        request=request_50, title="Monopole"
    )
    nec_text_75 = simulation_request_to_nec(
        request=request_75, title="Monopole"
    )

    assert "CM Reference impedance: 50 ohm\n" in nec_text_50
    assert "CM Reference impedance: 75 ohm\n" in nec_text_75


def test_gw_ex_fr_unchanged_between_free_space_and_perfect_ground():
    wire = create_monopole_wire()
    source = VoltageSource(wire_tag=1, segment=1)

    free_space_request = SimulationRequest(
        frequency_mhz=14.15,
        wires=(wire,),
        source=source,
        reference_impedance=50.0,
        environment=FreeSpaceEnvironment(),
    )
    perfect_ground_request = SimulationRequest(
        frequency_mhz=14.15,
        wires=(wire,),
        source=source,
        reference_impedance=50.0,
        environment=PerfectGroundEnvironment(),
    )

    free_space_lines = simulation_request_to_nec(
        request=free_space_request, title="Monopole"
    ).splitlines()
    perfect_ground_lines = simulation_request_to_nec(
        request=perfect_ground_request, title="Monopole"
    ).splitlines()

    def _lines_starting_with(lines, prefix):
        return [line for line in lines if line.startswith(prefix)]

    for prefix in ("GW ", "EX ", "FR "):
        assert _lines_starting_with(
            free_space_lines, prefix
        ) == _lines_starting_with(perfect_ground_lines, prefix)


def test_unknown_environment_type_is_rejected_clearly():
    class _UnknownEnvironment:
        pass

    request = SimulationRequest(
        frequency_mhz=14.15,
        wires=(create_monopole_wire(),),
        source=VoltageSource(wire_tag=1, segment=1),
        environment=_UnknownEnvironment(),
    )

    with pytest.raises(ValueError):
        simulation_request_to_nec(request=request, title="Monopole")


def test_project_v2_perfect_ground_exports_ge1_gn1(tmp_path):
    project = AntennaProject(
        metadata=ProjectMetadata(name="Monopolo sobre tierra perfecta"),
        wires=(create_monopole_wire(),),
        source=VoltageSource(wire_tag=1, segment=1),
        frequency_mhz=14.15,
        reference_impedance=50.0,
        sweep=SweepSettings(
            start_frequency_mhz=13.5,
            stop_frequency_mhz=15.5,
            points=81,
        ),
        environment=PerfectGroundEnvironment(),
    )
    destination = tmp_path / "monopolo.antsim"
    save_project(project, destination)
    loaded = load_project(destination)

    nec_text = simulation_request_to_nec(
        request=loaded.to_simulation_request(),
        title="Monopolo",
    )

    assert "GE 1\n" in nec_text
    assert "GN 1 0 0 0 0 0 0 0\n" in nec_text


def test_project_v1_free_space_exports_ge0_without_gn():
    project = load_project("examples/dipole-20m.antsim")
    assert project.schema_version == 1  # precondición del fixture histórico
    assert project.environment == FreeSpaceEnvironment()

    nec_text = simulation_request_to_nec(
        request=project.to_simulation_request(),
        title=project.metadata.name,
    )

    assert "GE 0\n" in nec_text
    assert "GN " not in nec_text