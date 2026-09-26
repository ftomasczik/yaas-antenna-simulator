"""Errores producidos durante la importación."""

from pathlib import Path


class TouchstoneFormatError(ValueError):
    """Indica que un archivo Touchstone no es válido."""


class MmanaFormatError(ValueError):
    """Indica que un archivo MMANA-GAL .maa no es válido o no puede analizarse.

    Conserva la ruta del archivo (si se conoce), el número de línea
    donde se detectó el problema (si aplica) y una explicación legible,
    como atributos independientes además del mensaje combinado.
    """

    def __init__(
        self,
        explanation: str,
        *,
        path: str | Path | None = None,
        line_number: int | None = None,
    ) -> None:
        self.path = Path(path) if path is not None else None
        self.line_number = line_number
        self.explanation = explanation

        parts = []
        if self.path is not None:
            parts.append(str(self.path))
        if line_number is not None:
            parts.append(f"línea {line_number}")

        prefix = ": ".join(parts)
        message = f"{prefix}: {explanation}" if prefix else explanation

        super().__init__(message)