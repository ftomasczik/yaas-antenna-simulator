"""Dominio del simulador de antenas."""

from antsim.domain.calculations import (
    calculate_swr,
    reflection_coefficient_to_impedance,
)

from antsim.domain.models import (
    Point3D,
    SimulationRequest,
    SimulationResult,
    SweepPoint,
    SweepRequest,
    SweepResult,
    SwrBandwidth,
    VoltageSource,
    Wire,
    MeasurementPoint,
)

__all__ = [
    "MeasurementPoint",
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