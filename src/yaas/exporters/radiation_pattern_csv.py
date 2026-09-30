"""Exportación de patrones de radiación a CSV."""

import csv
import io
from pathlib import Path

from yaas.domain import RadiationPatternResult


CSV_FIELDNAMES = (
    "frequency_mhz",
    "theta_deg",
    "phi_deg",
    "gain_db",
)


def radiation_pattern_to_csv(result: RadiationPatternResult) -> str:
    """Convierte un patrón de radiación en texto CSV.

    Cada fila es una celda de ``gain_db[theta_index][phi_index]``, en
    el mismo orden que ``RadiationPatternResult.samples`` (theta en el
    lazo externo, phi en el interno). La frecuencia se repite en cada
    fila para que el archivo sea autocontenido.

    Un nulo del dominio (``gain_db=None``, por ejemplo el centinela
    de NEC ya traducido por el adaptador del motor) se escribe como
    un campo vacío. Este exportador no aplica ninguna regla del
    centinela: una ganancia numérica, incluso ``-999.99``, se escribe
    como número.

    Se sigue la misma convención que los demás exportadores CSV: el
    dialecto por defecto del módulo ``csv`` (coma, fin de línea CRLF)
    y los números con su representación de Python (la más corta que
    reproduce el valor exacto, independiente del locale).

    Raises:
        TypeError: Si ``result`` no es un ``RadiationPatternResult``.
    """
    if not isinstance(result, RadiationPatternResult):
        raise TypeError(
            "Se esperaba un RadiationPatternResult: "
            f"{type(result).__name__!r}."
        )

    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)

    writer.writerow(CSV_FIELDNAMES)

    for sample in result.samples:
        writer.writerow(
            (
                result.frequency_mhz,
                sample.theta_deg,
                sample.phi_deg,
                "" if sample.gain_db is None else sample.gain_db,
            )
        )

    return buffer.getvalue()


def export_radiation_pattern_csv(
    result: RadiationPatternResult,
    destination: str | Path,
) -> Path:
    """Exporta un patrón de radiación a un archivo CSV.

    Escribe exactamente el texto de ``radiation_pattern_to_csv``. El
    contenido se genera antes de abrir el archivo, así que un
    ``result`` inválido no crea ni modifica ningún archivo.

    Args:
        result: Patrón de radiación a exportar.
        destination: Ruta del archivo de salida.

    Returns:
        Ruta del archivo creado.

    Raises:
        TypeError: Si ``result`` no es un ``RadiationPatternResult``.
    """
    content = radiation_pattern_to_csv(result)
    output_path = Path(destination)

    with output_path.open(
        mode="w",
        encoding="utf-8",
        newline="",
    ) as csv_file:
        csv_file.write(content)

    return output_path
