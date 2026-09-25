"""Motores de simulación disponibles."""

from antsim.engines.base import SimulationEngine


def __getattr__(name: str) -> type[SimulationEngine]:
    """Conserva la API pública sin cargar el motor nativo al importar."""
    if name == "PyNecEngine":
        from antsim.engines.pynec import PyNecEngine

        return PyNecEngine
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "PyNecEngine",
    "SimulationEngine",
]
