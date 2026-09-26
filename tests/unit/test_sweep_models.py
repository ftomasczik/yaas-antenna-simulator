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

def test_sweep_calculates_swr_bandwidth():
    result = SweepResult(
        points=(
            SweepPoint(
                frequency_mhz=14.0,
                impedance=complex(50.0, -20.0),
                swr=2.5,
            ),
            SweepPoint(
                frequency_mhz=14.1,
                impedance=complex(55.0, -10.0),
                swr=1.8,
            ),
            SweepPoint(
                frequency_mhz=14.2,
                impedance=complex(60.0, 0.0),
                swr=1.2,
            ),
            SweepPoint(
                frequency_mhz=14.3,
                impedance=complex(65.0, 10.0),
                swr=1.9,
            ),
            SweepPoint(
                frequency_mhz=14.4,
                impedance=complex(70.0, 20.0),
                swr=2.4,
            ),
        )
    )

    bandwidth = result.swr_bandwidth(2.0)

    assert bandwidth is not None
    assert bandwidth.lower_frequency_mhz == 14.1
    assert bandwidth.upper_frequency_mhz == 14.3
    assert bandwidth.bandwidth_khz == pytest.approx(200.0)
    assert bandwidth.center_frequency_mhz == pytest.approx(14.2)
    assert (
        bandwidth.fractional_bandwidth_percent
        == pytest.approx(1.40845, rel=0.001)
    )


def test_sweep_returns_no_bandwidth_when_limit_is_not_met():
    result = SweepResult(
        points=(
            SweepPoint(
                frequency_mhz=14.0,
                impedance=complex(20.0, -50.0),
                swr=3.0,
            ),
            SweepPoint(
                frequency_mhz=14.1,
                impedance=complex(25.0, -40.0),
                swr=2.5,
            ),
        )
    )

    assert result.swr_bandwidth(2.0) is None


def test_sweep_rejects_invalid_swr_threshold():
    result = SweepResult(
        points=(
            SweepPoint(
                frequency_mhz=14.0,
                impedance=complex(50.0, 0.0),
                swr=1.0,
            ),
        )
    )

    with pytest.raises(ValueError):
        result.swr_bandwidth(0.5)


# ---------------------------------------------------------------------------
# Diagnóstico de límites del barrido (resonancia, ROE mínima, ancho de banda)
# ---------------------------------------------------------------------------


def _interior_result() -> SweepResult:
    """Barrido de referencia con resonancia y ROE mínima interiores."""
    return SweepResult(
        points=(
            SweepPoint(
                frequency_mhz=49.0,
                impedance=complex(20.0, -60.0),
                swr=6.0,
            ),
            SweepPoint(
                frequency_mhz=50.0,
                impedance=complex(50.0, 0.0),
                swr=1.0,
            ),
            SweepPoint(
                frequency_mhz=51.0,
                impedance=complex(65.0, 10.0),
                swr=1.4,
            ),
            SweepPoint(
                frequency_mhz=52.0,
                impedance=complex(20.0, 60.0),
                swr=6.0,
            ),
        )
    )


def test_fully_interior_result_is_not_at_any_boundary():
    result = _interior_result()

    assert result.resonance_point.frequency_mhz == 50.0
    assert result.resonance_is_at_boundary is False
    assert result.minimum_swr_point.frequency_mhz == 50.0
    assert result.minimum_swr_is_at_boundary is False

    bandwidth = result.swr_bandwidth(2.0)
    assert bandwidth is not None
    assert bandwidth.truncated_below is False
    assert bandwidth.truncated_above is False


def test_resonance_at_lower_boundary_is_flagged():
    result = SweepResult(
        points=(
            SweepPoint(
                frequency_mhz=49.0,
                impedance=complex(50.0, 0.0),
                swr=1.0,
            ),
            SweepPoint(
                frequency_mhz=50.0,
                impedance=complex(60.0, 10.0),
                swr=1.3,
            ),
            SweepPoint(
                frequency_mhz=51.0,
                impedance=complex(70.0, 30.0),
                swr=1.8,
            ),
        )
    )

    assert result.resonance_point.frequency_mhz == 49.0
    assert result.resonance_is_at_boundary is True


def test_resonance_at_upper_boundary_is_flagged():
    result = SweepResult(
        points=(
            SweepPoint(
                frequency_mhz=49.0,
                impedance=complex(70.0, 30.0),
                swr=1.8,
            ),
            SweepPoint(
                frequency_mhz=50.0,
                impedance=complex(60.0, 10.0),
                swr=1.3,
            ),
            SweepPoint(
                frequency_mhz=51.0,
                impedance=complex(50.0, 0.0),
                swr=1.0,
            ),
        )
    )

    assert result.resonance_point.frequency_mhz == 51.0
    assert result.resonance_is_at_boundary is True


def test_minimum_swr_at_lower_boundary_is_flagged():
    result = SweepResult(
        points=(
            SweepPoint(
                frequency_mhz=49.0,
                impedance=complex(50.0, 0.0),
                swr=1.0,
            ),
            SweepPoint(
                frequency_mhz=50.0,
                impedance=complex(60.0, 20.0),
                swr=1.5,
            ),
            SweepPoint(
                frequency_mhz=51.0,
                impedance=complex(70.0, 40.0),
                swr=2.2,
            ),
        )
    )

    assert result.minimum_swr_point.frequency_mhz == 49.0
    assert result.minimum_swr_is_at_boundary is True


def test_minimum_swr_at_upper_boundary_is_flagged():
    result = SweepResult(
        points=(
            SweepPoint(
                frequency_mhz=49.0,
                impedance=complex(70.0, 40.0),
                swr=2.2,
            ),
            SweepPoint(
                frequency_mhz=50.0,
                impedance=complex(60.0, 20.0),
                swr=1.5,
            ),
            SweepPoint(
                frequency_mhz=51.0,
                impedance=complex(50.0, 0.0),
                swr=1.0,
            ),
        )
    )

    assert result.minimum_swr_point.frequency_mhz == 51.0
    assert result.minimum_swr_is_at_boundary is True


def test_swr_bandwidth_truncated_below():
    result = SweepResult(
        points=(
            SweepPoint(
                frequency_mhz=49.0,
                impedance=complex(50.0, -10.0),
                swr=1.3,
            ),
            SweepPoint(
                frequency_mhz=50.0,
                impedance=complex(50.0, 0.0),
                swr=1.0,
            ),
            SweepPoint(
                frequency_mhz=51.0,
                impedance=complex(60.0, 20.0),
                swr=1.6,
            ),
            SweepPoint(
                frequency_mhz=52.0,
                impedance=complex(20.0, 60.0),
                swr=6.0,
            ),
        )
    )

    bandwidth = result.swr_bandwidth(2.0)

    assert bandwidth is not None
    assert bandwidth.lower_frequency_mhz == 49.0
    assert bandwidth.upper_frequency_mhz == 51.0
    assert bandwidth.truncated_below is True
    assert bandwidth.truncated_above is False


def test_swr_bandwidth_truncated_above():
    result = SweepResult(
        points=(
            SweepPoint(
                frequency_mhz=49.0,
                impedance=complex(20.0, 60.0),
                swr=6.0,
            ),
            SweepPoint(
                frequency_mhz=50.0,
                impedance=complex(60.0, 20.0),
                swr=1.6,
            ),
            SweepPoint(
                frequency_mhz=51.0,
                impedance=complex(50.0, 0.0),
                swr=1.0,
            ),
            SweepPoint(
                frequency_mhz=52.0,
                impedance=complex(50.0, 10.0),
                swr=1.3,
            ),
        )
    )

    bandwidth = result.swr_bandwidth(2.0)

    assert bandwidth is not None
    assert bandwidth.lower_frequency_mhz == 50.0
    assert bandwidth.upper_frequency_mhz == 52.0
    assert bandwidth.truncated_below is False
    assert bandwidth.truncated_above is True


def test_swr_bandwidth_truncated_on_both_sides_when_whole_sweep_qualifies():
    """El barrido original 49-52 MHz: toda la ROE queda por debajo del límite."""
    result = SweepResult(
        points=(
            SweepPoint(
                frequency_mhz=49.0,
                impedance=complex(55.0, 5.0),
                swr=1.2,
            ),
            SweepPoint(
                frequency_mhz=50.0,
                impedance=complex(50.0, 0.0),
                swr=1.0,
            ),
            SweepPoint(
                frequency_mhz=51.0,
                impedance=complex(55.0, -5.0),
                swr=1.2,
            ),
            SweepPoint(
                frequency_mhz=52.0,
                impedance=complex(60.0, -10.0),
                swr=1.4,
            ),
        )
    )

    bandwidth = result.swr_bandwidth(2.0)

    assert bandwidth is not None
    assert bandwidth.lower_frequency_mhz == 49.0
    assert bandwidth.upper_frequency_mhz == 52.0
    assert bandwidth.truncated_below is True
    assert bandwidth.truncated_above is True


def test_swr_bandwidth_none_when_no_point_meets_the_limit():
    result = SweepResult(
        points=(
            SweepPoint(
                frequency_mhz=49.0,
                impedance=complex(20.0, -50.0),
                swr=3.0,
            ),
            SweepPoint(
                frequency_mhz=50.0,
                impedance=complex(25.0, -40.0),
                swr=2.5,
            ),
        )
    )

    assert result.swr_bandwidth(2.0) is None