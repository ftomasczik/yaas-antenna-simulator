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
from yaas.application.radiation_pattern import (
    MissingRadiationPatternError,
    RadiationPatternAnalysis,
    RadiationPatternSummary,
    calculate_radiation_pattern,
    export_project_radiation_pattern_nec,
    prepare_radiation_pattern_request,
    summarize_radiation_pattern,
)

__all__ = [
    "ComparisonRequestError",
    "MissingRadiationPatternError",
    "MmanaImportResult",
    "RadiationPatternAnalysis",
    "RadiationPatternSummary",
    "UNIFORM_SEGMENTATION_DIVISOR",
    "calculate_radiation_pattern",
    "compare_project_measurement",
    "convert_mmana_to_project",
    "derive_nec_segments",
    "export_project_radiation_pattern_nec",
    "prepare_mmana_import",
    "prepare_radiation_pattern_request",
    "summarize_radiation_pattern",
    "write_mmana_import",
]
