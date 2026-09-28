"""Exportación de resultados a CSV."""

import csv
from pathlib import Path

from yaas.domain import SweepResult


CSV_FIELDNAMES = (
    "frequency_mhz",
    "resistance_ohm",
    "reactance_ohm",
    "impedance_magnitude_ohm",
    "swr",
)


def export_sweep_csv(
    result: SweepResult,
    destination: str | Path,
) -> Path:
    """Exporta un barrido a un archivo CSV.

    Args:
        result: Resultado del barrido.
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

        for point in result.points:
            writer.writerow(
                {
                    "frequency_mhz": point.frequency_mhz,
                    "resistance_ohm": point.impedance.real,
                    "reactance_ohm": point.impedance.imag,
                    "impedance_magnitude_ohm": abs(
                        point.impedance
                    ),
                    "swr": point.swr,
                }
            )

    return output_path
