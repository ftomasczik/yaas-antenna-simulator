"""Contrato común para los motores de simulación."""

from typing import Protocol

from yaas.domain import (
    RadiationPatternRequest,
    RadiationPatternResult,
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

    def simulate_radiation_pattern(
        self,
        request: RadiationPatternRequest,
    ) -> RadiationPatternResult:
        """Calcula un patrón de radiación a una única frecuencia."""
        ...