"""Dominio del simulador de antenas."""

from antsim.domain.calculations import (
    calculate_swr,
    reflection_coefficient_to_impedance,
)
from antsim.domain.models import (
    Environment,
    FreeSpaceEnvironment,
    MeasurementPoint,
    MeasurementSweep,
    PerfectGroundEnvironment,
    Point3D,
    SimulationRequest,
    SimulationResult,
    SweepPoint,
    SweepRequest,
    SweepResult,
    SwrBandwidth,
    VoltageSource,
    Wire,
)

from antsim.domain.comparison import (
    ComparisonPoint,
    SweepComparison,
    compare_sweeps,
)

__all__ = [
    "ComparisonPoint",
    "SweepComparison",
    "compare_sweeps",
    "Environment",
    "FreeSpaceEnvironment",
    "MeasurementPoint",
    "MeasurementSweep",
    "PerfectGroundEnvironment",
    "Point3D",
    "SimulationRequest",
    "SimulationResult",
    "SweepPoint",
    "SweepRequest",
    "SweepResult",
    "SwrBandwidth",
    "VoltageSource",
    "Wire",
    "calculate_swr",
    "reflection_coefficient_to_impedance",
]
