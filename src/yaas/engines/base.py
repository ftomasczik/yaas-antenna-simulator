"""Contrato común para los motores de simulación."""

from typing import Protocol

from yaas.domain import (
    SimulationRequest,
    SimulationResult,
    SweepRequest,
    SweepResult,
)


class SimulationEngine(Protocol):
    """Interfaz que debe implementar un motor de simulación."""

    def simulate(
        self,
        request: SimulationRequest,
    ) -> SimulationResult:
        """Ejecuta una simulación de frecuencia única."""
        ...

    def simulate_sweep(
        self,
        request: SweepRequest,
    ) -> SweepResult:
        """Ejecuta un barrido de frecuencia."""
        ...