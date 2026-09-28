"""Lectura de archivos Touchstone de un puerto."""

import math
from pathlib import Path

from yaas.domain import (
    MeasurementPoint,
    MeasurementSweep,
)
from yaas.importers.errors import TouchstoneFormatError


_FREQUENCY_FACTORS_TO_MHZ = {
    "hz": 1e-6,
    "khz": 1e-3,
    "mhz": 1.0,
    "ghz": 1e3,
}


def _parse_options(
    line: str,
    line_number: int,
) -> tuple[float, str, float]:
    """Interpreta una línea de opciones Touchstone."""
    fields = line[1:].split()

    if len(fields) != 5:
        raise TouchstoneFormatError(
            f"Línea {line_number}: encabezado "
            "Touchstone inválido."
        )

    frequency_unit = fields[0].lower()
    parameter = fields[1].lower()
    data_format = fields[2].lower()
    reference_marker = fields[3].lower()

    if frequency_unit not in _FREQUENCY_FACTORS_TO_MHZ:
        raise TouchstoneFormatError(
            f"Línea {line_number}: unidad de frecuencia "
            f"no compatible: {fields[0]}."
        )

    if parameter != "s":
        raise TouchstoneFormatError(
            f"Línea {line_number}: solamente se admite "
            "el parámetro S."
        )

    if data_format not in {"ri", "ma", "db"}:
        raise TouchstoneFormatError(
            f"Línea {line_number}: formato no compatible: "
            f"{fields[2]}."
        )

    if reference_marker != "r":
        raise TouchstoneFormatError(
            f"Línea {line_number}: falta la impedancia "
            "de referencia R."
        )

    try:
        reference_impedance = float(fields[4])
    except ValueError as error:
        raise TouchstoneFormatError(
            f"Línea {line_number}: impedancia de "
            "referencia inválida."
        ) from error

    if (
        not math.isfinite(reference_impedance)
        or reference_impedance <= 0
    ):
        raise TouchstoneFormatError(
            f"Línea {line_number}: la impedancia de "
            "referencia debe ser positiva y finita."
        )

    return (
        _FREQUENCY_FACTORS_TO_MHZ[frequency_unit],
        data_format,
        reference_impedance,
    )


def _values_to_reflection_coefficient(
    first_value: float,
    second_value: float,
    data_format: str,
) -> complex:
    """Convierte una pareja Touchstone en S11 complejo."""
    if data_format == "ri":
        return complex(first_value, second_value)

    angle_radians = math.radians(second_value)

    if data_format == "ma":
        magnitude = first_value
    else:
        magnitude = 10 ** (first_value / 20.0)

    return complex(
        magnitude * math.cos(angle_radians),
        magnitude * math.sin(angle_radians),
    )


def parse_touchstone_s1p(
    text: str,
) -> MeasurementSweep:
    """Interpreta el contenido de un archivo Touchstone S1P."""
    frequency_factor: float | None = None
    data_format: str | None = None
    reference_impedance: float | None = None
    points: list[MeasurementPoint] = []

    for line_number, original_line in enumerate(
        text.splitlines(),
        start=1,
    ):
        line = original_line.split(
            "!",
            maxsplit=1,
        )[0].strip()

        if not line:
            continue

        if line.startswith("#"):
            if frequency_factor is not None:
                raise TouchstoneFormatError(
                    f"Línea {line_number}: existe más "
                    "de un encabezado Touchstone."
                )

            (
                frequency_factor,
                data_format,
                reference_impedance,
            ) = _parse_options(
                line=line,
                line_number=line_number,
            )
            continue

        if (
            frequency_factor is None
            or data_format is None
            or reference_impedance is None
        ):
            raise TouchstoneFormatError(
                f"Línea {line_number}: faltan las "
                "opciones Touchstone antes de los datos."
            )

        fields = line.split()

        if len(fields) != 3:
            raise TouchstoneFormatError(
                f"Línea {line_number}: se esperaban "
                "tres valores."
            )

        try:
            (
                frequency,
                first_value,
                second_value,
            ) = (
                float(value)
                for value in fields
            )
        except ValueError as error:
            raise TouchstoneFormatError(
                f"Línea {line_number}: hay un valor "
                "numérico inválido."
            ) from error

        values = (
            frequency,
            first_value,
            second_value,
        )

        if not all(
            math.isfinite(value)
            for value in values
        ):
            raise TouchstoneFormatError(
                f"Línea {line_number}: los valores "
                "deben ser finitos."
            )

        try:
            reflection_coefficient = (
                _values_to_reflection_coefficient(
                    first_value=first_value,
                    second_value=second_value,
                    data_format=data_format,
                )
            )
        except OverflowError as error:
            raise TouchstoneFormatError(
                f"Línea {line_number}: la magnitud "
                "calculada es demasiado grande."
            ) from error

        try:
            point = MeasurementPoint(
                frequency_mhz=(
                    frequency * frequency_factor
                ),
                reflection_coefficient=(
                    reflection_coefficient
                ),
                reference_impedance=(
                    reference_impedance
                ),
            )
        except ValueError as error:
            raise TouchstoneFormatError(
                f"Línea {line_number}: {error}"
            ) from error

        points.append(point)

    if frequency_factor is None:
        raise TouchstoneFormatError(
            "El archivo no contiene opciones Touchstone."
        )

    if not points:
        raise TouchstoneFormatError(
            "El archivo no contiene mediciones."
        )

    try:
        return MeasurementSweep(
            points=tuple(points)
        )
    except ValueError as error:
        raise TouchstoneFormatError(
            str(error)
        ) from error


def load_touchstone_s1p(
    source: str | Path,
) -> MeasurementSweep:
    """Carga un barrido S11 desde un archivo Touchstone."""
    source_path = Path(source)

    text = source_path.read_text(
        encoding="utf-8-sig"
    )

    return parse_touchstone_s1p(text)