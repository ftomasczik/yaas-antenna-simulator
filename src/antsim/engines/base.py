"""Contrato común para los motores de simulación."""

from typing import Protocol

from antsim.domain import SimulationRequest, SimulationResult


class SimulationEngine(Protocol):
    """Interfaz que debe implementar un motor de simulación."""

    def simulate(
        self,
        request: SimulationRequest,
    ) -> SimulationResult:
        """Ejecuta una simulación y devuelve un resultado normalizado."""
        ...
