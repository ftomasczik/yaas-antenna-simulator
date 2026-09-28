import math

import pytest

from yaas.domain import MeasurementPoint, MeasurementSweep, SweepPoint, SweepResult


@pytest.mark.parametrize("impedance", [
    complex(math.inf, 0), complex(-math.inf, 0),
    complex(math.nan, 0), complex(50, math.inf), complex(50, math.nan),
])
def test_simulated_resonance_excludes_nonfinite_impedance(impedance):
    finite = SweepPoint(15, 50 + 5j, 1.1)
    result = SweepResult((SweepPoint(14, impedance, math.inf), finite))
    assert result.resonance_point is finite


def test_simulated_resonance_is_unavailable_without_finite_points():
    result = SweepResult((SweepPoint(14, complex(math.inf, 0), math.inf),))
    assert result.resonance_point is None


def test_measured_resonance_excludes_open_circuit():
    finite = MeasurementPoint(15, 0.1 + 0.2j)
    result = MeasurementSweep((MeasurementPoint(14, 1 + 0j), finite))
    assert result.resonance_point is finite


def test_measured_resonance_is_unavailable_for_only_open_circuits():
    result = MeasurementSweep((MeasurementPoint(14, 1 + 0j), MeasurementPoint(15, 1 + 0j)))
    assert result.resonance_point is None


def test_finite_zero_reactance_remains_a_valid_candidate():
    matched = MeasurementPoint(15, 0j)
    result = MeasurementSweep((MeasurementPoint(14, 0.1 + 0.2j), matched))
    assert result.resonance_point is matched
