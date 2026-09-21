import csv

import pytest

from antsim.domain import SweepPoint, SweepResult
from antsim.exporters import export_sweep_csv


def test_export_sweep_csv(tmp_path):
    result = SweepResult(
        points=(
            SweepPoint(
                frequency_mhz=14.0,
                impedance=complex(60.0, -10.0),
                swr=1.4,
            ),
            SweepPoint(
                frequency_mhz=14.1,
                impedance=complex(65.0, 2.0),
                swr=1.3,
            ),
        )
    )

    destination = tmp_path / "sweep.csv"

    created_path = export_sweep_csv(
        result=result,
        destination=destination,
    )

    assert created_path == destination
    assert destination.exists()

    with destination.open(
        encoding="utf-8",
        newline="",
    ) as csv_file:
        rows = list(csv.DictReader(csv_file))

    assert len(rows) == 2

    assert float(rows[0]["frequency_mhz"]) == 14.0
    assert float(rows[0]["resistance_ohm"]) == 60.0
    assert float(rows[0]["reactance_ohm"]) == -10.0

    assert float(
        rows[0]["impedance_magnitude_ohm"]
    ) == pytest.approx(abs(complex(60.0, -10.0)))

    assert float(rows[0]["swr"]) == 1.4
    