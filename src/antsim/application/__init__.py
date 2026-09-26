"""Casos de uso de aplicación, independientes de la presentación."""

from antsim.application.comparison import (
    ComparisonRequestError,
    compare_project_measurement,
)
from antsim.application.mmana_conversion import (
    UNIFORM_SEGMENTATION_DIVISOR,
    convert_mmana_to_project,
    derive_nec_segments,
)

__all__ = [
    "ComparisonRequestError",
    "UNIFORM_SEGMENTATION_DIVISOR",
    "compare_project_measurement",
    "convert_mmana_to_project",
    "derive_nec_segments",
]
