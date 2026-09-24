import math

import pytest

from antsim.domain import (
    MeasurementPoint,
    MeasurementSweep,
    reflection_coefficient_to_impedance,
)

def point_from_impedance(
    frequency_mhz: float,
    impedance: complex,
    reference_impedance: float = 50.0,
) -> MeasurementPoint:
    """Crea un punto medido desde una impedancia conocida."""
    reflection_coefficient = (
        impedance - reference_impedance
    ) / (
        impedance + reference_impedance
    )

    return MeasurementPoint(
        frequency_mhz=frequency_mhz,
        reflection_coefficient=reflection_coefficient,
        reference_impedance=reference_impedance,
    )

def test_matched_load_has_fifty_ohms_and_unit_swr():
    point = MeasurementPoint(
        frequency_mhz=14.15,
        reflection_coefficient=complex(0.0, 0.0),
    )

    assert point.impedance == complex(50.0, 0.0)
    assert point.swr == pytest.approx(1.0)


def test_reflection_coefficient_recovers_impedance():
    expected_impedance = complex(75.0, 25.0)
    reference_impedance = 50.0

    reflection_coefficient = (
        expected_impedance - reference_impedance
    ) / (
        expected_impedance + reference_impedance
    )

    impedance = reflection_coefficient_to_impedance(
        reflection_coefficient,
        reference_impedance,
    )

    assert impedance.real == pytest.approx(75.0)
    assert impedance.imag == pytest.approx(25.0)


def test_open_circuit_has_infinite_impedance_and_swr():
    point = MeasurementPoint(
        frequency_mhz=14.15,
        reflection_coefficient=complex(1.0, 0.0),
    )

    assert math.isinf(point.impedance.real)
    assert point.impedance.imag == 0.0
    assert math.isinf(point.swr)


def test_measurement_rejects_invalid_frequency():
    with pytest.raises(
        ValueError,
        match="frecuencia medida",
    ):
        MeasurementPoint(
            frequency_mhz=0.0,
            reflection_coefficient=complex(0.0, 0.0),
        )


def test_measurement_rejects_non_finite_s11():
    with pytest.raises(
        ValueError,
        match="coeficiente de reflexión",
    ):
        MeasurementPoint(
            frequency_mhz=14.15,
            reflection_coefficient=complex(math.nan, 0.0),
        )

def test_measurement_detects_reactance_zero_crossing():
    sweep = MeasurementSweep(
        points=(
            point_from_impedance(
                14.0,
                complex(50.0, -10.0),
            ),
            point_from_impedance(
                14.5,
                complex(50.0, 5.0),
            ),
        )
    )

    assert sweep.has_reactance_zero_crossing


def test_measurement_detects_missing_zero_crossing():
    sweep = MeasurementSweep(
        points=(
            point_from_impedance(
                14.0,
                complex(50.0, -20.0),
            ),
            point_from_impedance(
                14.5,
                complex(50.0, -5.0),
            ),
        )
    )

    assert not sweep.has_reactance_zero_crossing


def test_measurement_detects_minimum_swr_at_boundary():
    sweep = MeasurementSweep(
        points=(
            point_from_impedance(
                14.0,
                complex(80.0, 0.0),
            ),
            point_from_impedance(
                14.5,
                complex(60.0, 0.0),
            ),
        )
    )

    assert sweep.minimum_swr_is_at_boundary       