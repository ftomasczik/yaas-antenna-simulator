"""Dominio del simulador de antenas."""

from yaas.domain.calculations import (
    calculate_swr,
    reflection_coefficient_to_impedance,
)
from yaas.domain.models import (
    AngularSweep,
    Environment,
    FreeSpaceEnvironment,
    MeasurementPoint,
    MeasurementSweep,
    PerfectGroundEnvironment,
    Point3D,
    RadiationPatternRequest,
    RadiationPatternResult,
    RadiationPatternSample,
    RealGroundEnvironment,
    RealGroundModel,
    SimulationRequest,
    SimulationResult,
    SweepPoint,
    SweepRequest,
    SweepResult,
    SwrBandwidth,
    VoltageSource,
    Wire,
)

from yaas.domain.comparison import (
    ComparisonPoint,
    SweepComparison,
    compare_sweeps,
)

__all__ = [
    "ComparisonPoint",
    "SweepComparison",
    "compare_sweeps",
    "AngularSweep",
    "Environment",
    "FreeSpaceEnvironment",
    "MeasurementPoint",
    "MeasurementSweep",
    "PerfectGroundEnvironment",
    "Point3D",
    "RadiationPatternRequest",
    "RadiationPatternResult",
    "RadiationPatternSample",
    "RealGroundEnvironment",
    "RealGroundModel",
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
