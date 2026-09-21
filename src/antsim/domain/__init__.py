"""Dominio del simulador de antenas."""

from antsim.domain.calculations import calculate_swr
from antsim.domain.models import (
    Point3D,
    SimulationRequest,
    SimulationResult,
    SweepPoint,
    SweepRequest,
    SweepResult,
    VoltageSource,
    Wire,
)

__all__ = [
    "Point3D",
    "SimulationRequest",
    "SimulationResult",
    "SweepPoint",
    "SweepRequest",
    "SweepResult",
    "VoltageSource",
    "Wire",
    "calculate_swr",
]