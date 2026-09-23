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
        "CE\n"
        "GW 1 101 -5.03 0 0 5.03 0 0 0.001\n"
        "GE 0\n"
        "EX 0 1 51 0 1 0\n"
        "FR 0 1 0 0 14.15 0\n"
        "EN\n"
    )


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
        "CM First line Second line\nCE\n"
    )