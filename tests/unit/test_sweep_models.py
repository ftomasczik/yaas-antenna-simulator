import pytest

from antsim.domain import (
    Point3D,
    SweepPoint,
    SweepRequest,
    SweepResult,
    VoltageSource,
    Wire,
)


def create_wire() -> Wire:
    return Wire(
        tag=1,
        start=Point3D(-5.0, 0.0, 0.0),
        end=Point3D(5.0, 0.0, 0.0),
        radius_m=0.001,
        segments=101,
    )


def create_request(
    start: float = 14.0,
    stop: float = 14.2,
    points: int = 3,
) -> SweepRequest:
    return SweepRequest(
        start_frequency_mhz=start,
        stop_frequency_mhz=stop,
        points=points,
        wires=(create_wire(),),
        source=VoltageSource(
            wire_tag=1,
            segment=51,
        ),
    )


def test_sweep_calculates_frequency_step():
    request = create_request()

    assert request.frequency_step_mhz == pytest.approx(0.1)


def test_sweep_rejects_reversed_frequency_range():
    with pytest.raises(ValueError):
        create_request(
            start=14.2,
            stop=14.0,
        )


def test_sweep_requires_at_least_two_points():
    with pytest.raises(ValueError):
        create_request(points=1)


def test_sweep_finds_resonance_point():
    result = SweepResult(
        points=(
            SweepPoint(
                frequency_mhz=14.0,
                impedance=complex(60.0, -20.0),
                swr=1.6,
            ),
            SweepPoint(
                frequency_mhz=14.1,
                impedance=complex(65.0, 2.0),
                swr=1.4,
            ),
            SweepPoint(
                frequency_mhz=14.2,
                impedance=complex(70.0, 12.0),
                swr=1.5,
            ),
        )
    )

    assert result.resonance_point.frequency_mhz == 14.1


def test_sweep_finds_minimum_swr_point():
    result = SweepResult(
        points=(
            SweepPoint(
                frequency_mhz=14.0,
                impedance=complex(50.0, -5.0),
                swr=1.2,
            ),
            SweepPoint(
                frequency_mhz=14.1,
                impedance=complex(65.0, 0.0),
                swr=1.3,
            ),
        )
    )

    assert result.minimum_swr_point.frequency_mhz == 14.0
    