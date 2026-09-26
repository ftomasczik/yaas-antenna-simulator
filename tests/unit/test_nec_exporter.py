from antsim.domain import (
    Point3D,
    SimulationRequest,
    VoltageSource,
    Wire,
)
from antsim.exporters import (
    export_nec,
    simulation_request_to_nec,
)

from antsim.domain import (
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

    