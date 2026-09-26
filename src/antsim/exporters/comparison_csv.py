"""Exportación de comparaciones de barridos a CSV."""

import csv
from pathlib import Path

from antsim.domain import SweepComparison


CSV_FIELDNAMES = (
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
)


def export_comparison_csv(
    comparison: SweepComparison,
    destination: str | Path,
) -> Path:
    """Exporta una comparación de barridos a un archivo CSV.

    Args:
        comparison: Comparación a exportar.
        destination: Ruta del archivo de salida.

    Returns:
        Ruta del archivo creado.
    """
    output_path = Path(destination)

    with output_path.open(
        mode="w",
        encoding="utf-8",
        newline="",
    ) as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=CSV_FIELDNAMES,
        )

        writer.writeheader()

        for point in comparison.points:
            impedance_difference = point.impedance_difference

            writer.writerow(
                {
                    "frequency_mhz": point.frequency_mhz,
                    "simulated_resistance_ohm": (
                        point.simulated_impedance.real
                    ),
                    "simulated_reactance_ohm": (
                        point.simulated_impedance.imag
                    ),
                    "measured_resistance_ohm": (
                        point.measured_impedance.real
                    ),
                    "measured_reactance_ohm": (
                        point.measured_impedance.imag
                    ),
                    "simulated_swr": point.simulated_swr,
                    "measured_swr": point.measured_swr,
                    "resistance_difference_ohm": (
                        impedance_difference.real
                    ),
                    "reactance_difference_ohm": (
                        impedance_difference.imag
                    ),
                    "swr_difference": point.swr_difference,
                    "interpolated": point.interpolated,
                }
            )

    return output_path
