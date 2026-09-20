"""Adaptador del motor NEC2++ proporcionado por PyNEC."""

from PyNEC import nec_context

from antsim.domain import (
    SimulationRequest,
    SimulationResult,
    calculate_swr,
)


class PyNecEngine:
    """Ejecuta simulaciones mediante PyNEC y NEC2++."""

    def simulate(
        self,
        request: SimulationRequest,
    ) -> SimulationResult:
        """Ejecuta una simulación básica en espacio libre."""
        context = nec_context()
        geometry = context.get_geometry()

        for wire in request.wires:
            geometry.wire(
                wire.tag,
                wire.segments,
                wire.start.x,
                wire.start.y,
                wire.start.z,
                wire.end.x,
                wire.end.y,
                wire.end.z,
                wire.radius_m,
                1.0,
                1.0,
            )

        # Finaliza la geometría sin plano de tierra.
        context.geometry_complete(0)

        # Condición de espacio libre.
        context.gn_card(
            -1,
            0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
        )

        # Una única frecuencia, expresada en MHz.
        context.fr_card(
            0,
            1,
            request.frequency_mhz,
            0.0,
        )

        source = request.source

        # Fuente de tensión.
        context.ex_card(
            0,
            source.wire_tag,
            source.segment,
            0,
            source.voltage.real,
            source.voltage.imag,
            0.0,
            0.0,
            0.0,
            0.0,
        )

        # Ejecuta NEC2++.
        context.xq_card(0)

        raw_impedance = (
            context
            .get_input_parameters(0)
            .get_impedance()
        )

        # Normaliza ndarray o escalar a complex de Python.
        if hasattr(raw_impedance, "item"):
            impedance = complex(raw_impedance.item())
        else:
            impedance = complex(raw_impedance)

        swr = calculate_swr(
            impedance=impedance,
            reference_impedance=request.reference_impedance,
        )

        return SimulationResult(
            frequency_mhz=request.frequency_mhz,
            impedance=impedance,
            swr=swr,
        )