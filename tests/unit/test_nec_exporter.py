import pytest

from yaas.domain import (
    FreeSpaceEnvironment,
    PerfectGroundEnvironment,
    Point3D,
    RealGroundEnvironment,
    SimulationRequest,
    SweepRequest,
    VoltageSource,
    Wire,
)

from yaas.exporters import (
    export_nec,
    export_sweep_nec,
    simulation_request_to_nec,
    sweep_request_to_nec,
)

from yaas.projects import (
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
    destination = tmp_path / "monopolo.yaas"
    save_project(project, destination)
    loaded = load_project(destination)

    nec_text = simulation_request_to_nec(
        request=loaded.to_simulation_request(),
        title="Monopolo",
    )

    assert "GE 1\n" in nec_text
    assert "GN 1 0 0 0 0 0 0 0\n" in nec_text


def test_project_v1_free_space_exports_ge0_without_gn():
    project = load_project("examples/dipole-20m.yaas")
    assert project.schema_version == 1  # precondición del fixture histórico
    assert project.environment == FreeSpaceEnvironment()

    nec_text = simulation_request_to_nec(
        request=project.to_simulation_request(),
        title=project.metadata.name,
    )

    assert "GE 0\n" in nec_text
    assert "GN " not in nec_text


# ---------------------------------------------------------------------------
# RealGroundEnvironment / Sommerfeld-Norton (fase 7B)
# ---------------------------------------------------------------------------


def _parse_gn_line(nec_text: str) -> list[str]:
    lines = nec_text.splitlines()
    gn_line = next(line for line in lines if line.startswith("GN "))
    return gn_line.split()


def create_real_ground_request(
    relative_permittivity: float = 13.0,
    conductivity_s_per_m: float = 0.005,
) -> SimulationRequest:
    return SimulationRequest(
        frequency_mhz=14.15,
        wires=(create_monopole_wire(),),
        source=VoltageSource(wire_tag=1, segment=1),
        reference_impedance=50.0,
        environment=RealGroundEnvironment(
            relative_permittivity=relative_permittivity,
            conductivity_s_per_m=conductivity_s_per_m,
        ),
    )


def create_real_ground_sweep_request(
    relative_permittivity: float = 13.0,
    conductivity_s_per_m: float = 0.005,
) -> SweepRequest:
    return SweepRequest(
        start_frequency_mhz=13.5,
        stop_frequency_mhz=15.5,
        points=81,
        wires=(create_monopole_wire(),),
        source=VoltageSource(wire_tag=1, segment=1),
        reference_impedance=50.0,
        environment=RealGroundEnvironment(
            relative_permittivity=relative_permittivity,
            conductivity_s_per_m=conductivity_s_per_m,
        ),
    )


def test_real_ground_contains_ge_1():
    nec_text = simulation_request_to_nec(
        request=create_real_ground_request(),
        title="Monopole real ground",
    )

    assert "GE 1\n" in nec_text


@pytest.mark.parametrize(
    "relative_permittivity,conductivity_s_per_m",
    [
        (13.0, 0.005),
        (4.0, 0.0),
        (80.0, 5.0),
    ],
)
def test_real_ground_gn_card_has_exact_structure(
    relative_permittivity, conductivity_s_per_m
):
    """Parsea la tarjeta GN campo por campo (no solo busca subcadenas).

    Confirma explícitamente: token inicial "GN"; exactamente 10
    campos después de él (I1-I4 + F1-F6); I1..I4 == 2,0,0,0; F1 ==
    permitividad; F2 == conductividad; F3..F6 == 0.
    """
    nec_text = simulation_request_to_nec(
        request=create_real_ground_request(
            relative_permittivity, conductivity_s_per_m
        ),
        title="Monopole real ground",
    )

    fields = _parse_gn_line(nec_text)

    assert fields[0] == "GN"
    assert len(fields) - 1 == 10
    assert fields[1:5] == ["2", "0", "0", "0"]
    assert fields[5] == f"{relative_permittivity:.12g}"
    assert fields[6] == f"{conductivity_s_per_m:.12g}"
    assert fields[7:11] == ["0", "0", "0", "0"]


def test_real_ground_gn_card_does_not_match_old_incorrect_layout():
    """No basta con que 13 y 0.005 aparezcan en el archivo: la tarjeta
    incorrecta anterior (8 campos, sin I3/I4) nunca debe aparecer."""
    nec_text = simulation_request_to_nec(
        request=create_real_ground_request(13.0, 0.005),
        title="Monopole real ground",
    )

    assert "GN 2 0 13 0.005 0 0 0 0\n" not in nec_text
    assert "GN 2 0 0 0 13 0.005 0 0 0 0\n" in nec_text


def test_real_ground_order_gw_ge_gn_ex_fr_en():
    nec_text = simulation_request_to_nec(
        request=create_real_ground_request(),
        title="Monopole real ground",
    )
    lines = nec_text.splitlines()

    last_gw_index = max(
        index
        for index, line in enumerate(lines)
        if line.startswith("GW ")
    )
    ge_index = lines.index("GE 1")
    gn_index = next(
        index
        for index, line in enumerate(lines)
        if line.startswith("GN ")
    )
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
    en_index = lines.index("EN")

    assert (
        last_gw_index
        < ge_index
        < gn_index
        < ex_index
        < fr_index
        < en_index
    )


def test_real_ground_sweep_has_single_ge_and_gn():
    nec_text = sweep_request_to_nec(
        request=create_real_ground_sweep_request(),
        title="Monopole real ground sweep",
    )

    assert "GN 2 0 0 0 13 0.005 0 0 0 0\n" in nec_text
    # Una única GE y una única GN: el mismo entorno para todo el
    # barrido, no una tarjeta por punto (aunque PyNecEngine sí use un
    # contexto NEC2++ nuevo por frecuencia internamente: ver
    # docs/validation/real-ground-dipole-4nec2.md).
    assert nec_text.count("\nGE ") == 1
    assert nec_text.count("\nGN ") == 1


def test_real_ground_sweep_fr_contains_all_points():
    nec_text = sweep_request_to_nec(
        request=create_real_ground_sweep_request(),
        title="Monopole real ground sweep",
    )

    assert "FR 0 81 0 0 13.5 0.025\n" in nec_text


def test_real_ground_rejects_unsupported_model():
    environment = object.__new__(RealGroundEnvironment)
    object.__setattr__(environment, "relative_permittivity", 13.0)
    object.__setattr__(environment, "conductivity_s_per_m", 0.005)
    object.__setattr__(environment, "model", "reflection_coefficient")

    request = SimulationRequest(
        frequency_mhz=14.15,
        wires=(create_monopole_wire(),),
        source=VoltageSource(wire_tag=1, segment=1),
        environment=environment,
    )

    with pytest.raises(ValueError, match="RealGroundModel"):
        simulation_request_to_nec(request=request, title="Monopole")


def test_gw_ex_fr_unchanged_between_perfect_ground_and_real_ground():
    wire = create_monopole_wire()
    source = VoltageSource(wire_tag=1, segment=1)

    perfect_ground_request = SimulationRequest(
        frequency_mhz=14.15,
        wires=(wire,),
        source=source,
        reference_impedance=50.0,
        environment=PerfectGroundEnvironment(),
    )
    real_ground_request = SimulationRequest(
        frequency_mhz=14.15,
        wires=(wire,),
        source=source,
        reference_impedance=50.0,
        environment=RealGroundEnvironment(
            relative_permittivity=13.0,
            conductivity_s_per_m=0.005,
        ),
    )

    perfect_ground_lines = simulation_request_to_nec(
        request=perfect_ground_request, title="Monopole"
    ).splitlines()
    real_ground_lines = simulation_request_to_nec(
        request=real_ground_request, title="Monopole"
    ).splitlines()

    def _lines_starting_with(lines, prefix):
        return [line for line in lines if line.startswith(prefix)]

    for prefix in ("GW ", "EX ", "FR "):
        assert _lines_starting_with(
            perfect_ground_lines, prefix
        ) == _lines_starting_with(real_ground_lines, prefix)


def test_saved_real_ground_project_exports_correct_gn_card(tmp_path):
    project = AntennaProject(
        metadata=ProjectMetadata(name="Monopolo sobre tierra real"),
        wires=(create_monopole_wire(),),
        source=VoltageSource(wire_tag=1, segment=1),
        frequency_mhz=14.15,
        reference_impedance=50.0,
        sweep=SweepSettings(
            start_frequency_mhz=13.5,
            stop_frequency_mhz=15.5,
            points=81,
        ),
        environment=RealGroundEnvironment(
            relative_permittivity=13.0,
            conductivity_s_per_m=0.005,
        ),
    )
    destination = tmp_path / "monopolo-real-ground.yaas"
    save_project(project, destination)
    loaded = load_project(destination)
    assert loaded.schema_version == 4

    nec_text = simulation_request_to_nec(
        request=loaded.to_simulation_request(),
        title="Monopolo",
    )

    assert "GE 1\n" in nec_text
    assert "GN 2 0 0 0 13 0.005 0 0 0 0\n" in nec_text


def test_saved_real_ground_project_sweep_exports_correct_gn_card(tmp_path):
    project = AntennaProject(
        metadata=ProjectMetadata(name="Monopolo sobre tierra real"),
        wires=(create_monopole_wire(),),
        source=VoltageSource(wire_tag=1, segment=1),
        frequency_mhz=14.15,
        reference_impedance=50.0,
        sweep=SweepSettings(
            start_frequency_mhz=13.5,
            stop_frequency_mhz=15.5,
            points=81,
        ),
        environment=RealGroundEnvironment(
            relative_permittivity=13.0,
            conductivity_s_per_m=0.005,
        ),
    )
    destination = tmp_path / "monopolo-real-ground.yaas"
    save_project(project, destination)
    loaded = load_project(destination)
    assert loaded.schema_version == 4

    nec_text = sweep_request_to_nec(
        request=loaded.to_sweep_request(),
        title="Monopolo sweep",
    )

    assert "GE 1\n" in nec_text
    assert "GN 2 0 0 0 13 0.005 0 0 0 0\n" in nec_text
    assert nec_text.count("\nGN ") == 1