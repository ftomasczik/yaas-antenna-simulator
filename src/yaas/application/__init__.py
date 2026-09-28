"""Casos de uso de aplicación, independientes de la presentación."""

from yaas.application.comparison import (
    ComparisonRequestError,
    compare_project_measurement,
)
from yaas.application.mmana_conversion import (
    UNIFORM_SEGMENTATION_DIVISOR,
    convert_mmana_to_project,
    derive_nec_segments,
)
from yaas.application.mmana_import import (
    MmanaImportResult,
    prepare_mmana_import,
    write_mmana_import,
)

__all__ = [
    "ComparisonRequestError",
    "MmanaImportResult",
    "UNIFORM_SEGMENTATION_DIVISOR",
    "compare_project_measurement",
    "convert_mmana_to_project",
    "derive_nec_segments",
    "prepare_mmana_import",
    "write_mmana_import",
]
