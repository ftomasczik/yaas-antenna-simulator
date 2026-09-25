import math

import pytest

from antsim.domain import (
    MeasurementPoint,
    MeasurementSweep,
    SweepPoint,
    SweepResult,
    compare_sweeps,
)


def simulated(*pairs):
    # La ROE previa no debe participar de la comparación.
    return SweepResult(tuple(SweepPoint(f, z, math.nan) for f, z in pairs))


def measured(*pairs, reference=50.0):
    return MeasurementSweep(tuple(
        MeasurementPoint(f, (z - reference) / (z + reference), reference)
        for f, z in pairs
    ))


def test_common_reference_recalculates_both_swr_without_changing_inputs():
    simulation = simulated((10, 100 + 0j))
    measurement = measured((10, 100 + 0j), reference=75)
    result = compare_sweeps(simulation, measurement, reference_impedance=100)
    assert result.reference_impedance == 100
    assert result.points[0].simulated_swr == pytest.approx(1)
    assert result.points[0].measured_swr == pytest.approx(1)
    assert result.points[0].impedance_difference == pytest.approx(0)
    assert result.points[0].swr_difference == pytest.approx(0)
    assert measurement.reference_impedance == 75
    assert math.isnan(simulation.points[0].swr)


@pytest.mark.parametrize("reference", [0, -50, math.nan, math.inf, -math.inf])
def test_rejects_invalid_common_reference(reference):
    with pytest.raises(ValueError, match="referencia"):
        compare_sweeps(simulated((10, 50)), measured((10, 50)),
                       reference_impedance=reference)


def test_interpolates_complex_impedance_on_irregular_measured_grid():
    result = compare_sweeps(
        simulated((10, 50 - 20j), (12, 90 + 20j)),
        measured((10, 50 - 20j), (10.5, 65 - 5j), (12, 90 + 20j)),
        reference_impedance=50,
    )
    assert [p.frequency_mhz for p in result.points] == [10, 10.5, 12]
    assert [p.interpolated for p in result.points] == [False, True, False]
    assert result.points[1].simulated_impedance == pytest.approx(60 - 10j)
    assert result.points[1].impedance_difference == pytest.approx(5 + 5j)
    # ROE de Z interpolada, no interpolación de ROE.
    gamma = abs(((60 - 10j) - 50) / ((60 - 10j) + 50))
    assert result.points[1].simulated_swr == pytest.approx((1 + gamma) / (1 - gamma))


def test_partial_overlap_excludes_points_without_extrapolating():
    result = compare_sweeps(
        simulated((10, 50), (12, 50)),
        measured((9, 50), (11, 50), (13, 50)),
        reference_impedance=50,
    )
    assert result.excluded_measurement_points == 2
    assert [p.frequency_mhz for p in result.points] == [11]


@pytest.mark.parametrize("frequencies", [(1, 2), (9, 13)])
def test_rejects_no_measured_samples_in_overlap(frequencies):
    with pytest.raises(ValueError, match="No hay frecuencias"):
        compare_sweeps(simulated((10, 50), (12, 50)),
                       measured(*((f, 50) for f in frequencies)),
                       reference_impedance=50)


def test_no_implicit_frequency_tolerance_or_extrapolation():
    result = compare_sweeps(
        simulated((10, 50), (12, 60)),
        measured((10 - 1e-10, 50), (10 + 1e-10, 50)),
        reference_impedance=50,
    )
    assert result.excluded_measurement_points == 1
    assert result.points[0].interpolated


@pytest.mark.parametrize("frequencies", [(10, 10), (12, 10), (0, 10),
                                         (math.nan, 10), (10, math.inf)])
def test_rejects_invalid_simulation_grid(frequencies):
    with pytest.raises(ValueError, match="frecuencias simuladas"):
        compare_sweeps(simulated(*((f, 50) for f in frequencies)),
                       measured((10, 50)), reference_impedance=50)


@pytest.mark.parametrize("impedance", [complex(math.nan, 0), complex(math.inf, 0),
                                       complex(50, math.inf)])
def test_rejects_nonfinite_simulated_impedance_even_outside_overlap(impedance):
    with pytest.raises(ValueError, match="impedancias finitas"):
        compare_sweeps(simulated((9, impedance), (10, 50)),
                       measured((10, 50)), reference_impedance=50)


def test_rejects_open_measurement_instead_of_subtracting_infinities():
    measurement = MeasurementSweep((MeasurementPoint(10, 1 + 0j),))
    with pytest.raises(ValueError, match="impedancias finitas"):
        compare_sweeps(simulated((10, 50)), measurement, reference_impedance=50)


@pytest.mark.parametrize("side", ["simulation", "measurement"])
def test_rejects_infinite_recalculated_swr_for_short_circuit(side):
    with pytest.raises(ValueError, match="ROE recalculadas finitas"):
        compare_sweeps(simulated((10, 0 if side == "simulation" else 50)),
                       measured((10, 0 if side == "measurement" else 50)),
                       reference_impedance=50)
