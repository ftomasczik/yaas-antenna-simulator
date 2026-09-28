import csv
import math

from yaas.domain import ComparisonPoint, SweepComparison
from yaas.exporters.comparison_csv import export_comparison_csv


def _comparison() -> SweepComparison:
    points = (
        ComparisonPoint(
            frequency_mhz=14.0,
            simulated_impedance=complex(50, -10),
            measured_impedance=complex(55, -12),
            simulated_swr=1.5,
            measured_swr=1.6,
            interpolated=False,
        ),
        ComparisonPoint(
            frequency_mhz=14.1,
            simulated_impedance=complex(48, -8),
            measured_impedance=complex(50, -9),
            simulated_swr=1.4,
            measured_swr=1.45,
            interpolated=True,
        ),
    )
    return SweepComparison(
        reference_impedance=50.0,
        points=points,
        excluded_measurement_points=2,
    )


def test_export_comparison_csv_returns_destination(tmp_path):
    destination = tmp_path / "comparison.csv"

    result_path = export_comparison_csv(_comparison(), destination)

    assert result_path == destination
    assert destination.is_file()


def test_export_comparison_csv_writes_expected_header(tmp_path):
    destination = tmp_path / "comparison.csv"
    export_comparison_csv(_comparison(), destination)

    with destination.open(encoding="utf-8", newline="") as csv_file:
        header = next(csv.reader(csv_file))

    assert header == [
        "frequency_mhz",
        "simulated_resistance_ohm",
        "simulated_reactance_ohm",
        "measured_resistance_ohm",
        "measured_reactance_ohm",
        "simulated_swr",
        "measured_swr",
        "resistance_difference_ohm",
        "reactance_difference_ohm",
        "swr_difference",
        "interpolated",
    ]


def test_export_comparison_csv_uses_existing_difference_properties(tmp_path):
    destination = tmp_path / "comparison.csv"
    comparison = _comparison()
    export_comparison_csv(comparison, destination)

    with destination.open(encoding="utf-8", newline="") as csv_file:
        rows = list(csv.DictReader(csv_file))

    assert len(rows) == 2

    first_point = comparison.points[0]
    first_row = rows[0]

    assert float(first_row["frequency_mhz"]) == first_point.frequency_mhz
    assert float(first_row["simulated_resistance_ohm"]) == (
        first_point.simulated_impedance.real
    )
    assert float(first_row["measured_reactance_ohm"]) == (
        first_point.measured_impedance.imag
    )
    assert float(first_row["resistance_difference_ohm"]) == (
        first_point.impedance_difference.real
    )
    assert float(first_row["reactance_difference_ohm"]) == (
        first_point.impedance_difference.imag
    )
    assert math.isclose(
        float(first_row["swr_difference"]),
        first_point.swr_difference,
    )
    assert first_row["interpolated"] == "False"
    assert rows[1]["interpolated"] == "True"
