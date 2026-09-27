"""Adaptador del motor NEC2++ proporcionado por PyNEC."""

from typing import Any

from PyNEC import nec_context

from antsim.domain import (
    Environment,
    FreeSpaceEnvironment,
    PerfectGroundEnvironment,
    SimulationRequest,
    SimulationResult,
    SweepPoint,
    SweepRequest,
    SweepResult,
    VoltageSource,
    Wire,
    calculate_swr,
)


def check_runtime() -> None:
    """Comprueba que la biblioteca nativa puede crear un contexto NEC."""
    context = nec_context()
    del context


class PyNecEngine:
    """Ejecuta simulaciones mediante PyNEC y NEC2++."""

    def simulate(
        self,
        request: SimulationRequest,
    ) -> SimulationResult:
        """Ejecuta una simulación de frecuencia única."""
        context = self._create_context(
            request.wires,
            request.environment,
        )

        context.fr_card(
            0,
            1,
            request.frequency_mhz,
            0.0,
        )

        self._add_source(context, request.source)
        context.xq_card(0)

        impedance = self._get_impedance(context, 0)
        swr = calculate_swr(
            impedance=impedance,
            reference_impedance=request.reference_impedance,
        )

        return SimulationResult(
            frequency_mhz=request.frequency_mhz,
            impedance=impedance,
            swr=swr,
        )

    def simulate_sweep(
        self,
        request: SweepRequest,
    ) -> SweepResult:
        """Ejecuta un barrido lineal en una única llamada a NEC2++."""
        context = self._create_context(
            request.wires,
            request.environment,
        )

        context.fr_card(
            0,
            request.points,
            request.start_frequency_mhz,
            request.frequency_step_mhz,
        )

        self._add_source(context, request.source)
        context.xq_card(0)

        points: list[SweepPoint] = []

        for index in range(request.points):
            frequency_mhz = (
                request.start_frequency_mhz
                + index * request.frequency_step_mhz
            )

            impedance = self._get_impedance(
                context,
                index,
            )

            swr = calculate_swr(
                impedance=impedance,
                reference_impedance=request.reference_impedance,
            )

            points.append(
                SweepPoint(
                    frequency_mhz=frequency_mhz,
                    impedance=impedance,
                    swr=swr,
                )
            )

        return SweepResult(points=tuple(points))

    def _create_context(
        self,
        wires: tuple[Wire, ...],
        environment: Environment,
    ) -> Any:
        """Crea un contexto NEC2++ con su geometría y entorno.

        El orden se mantiene deliberadamente fijo: primero se agregan
        todos los conductores, luego se cierra la geometría
        (``geometry_complete``, tarjeta ``GE``) y recién después se
        declara el tipo de tierra (``gn_card``, tarjeta ``GN``). Ver
        ``docs/research/nec-ground-configuration.md``: invertir este
        orden (``GN`` antes de que ``GE`` declare un plano de tierra)
        no acopla la tierra a la impedancia de entrada, según se
        verificó empíricamente allí.
        """
        context = nec_context()
        geometry = context.get_geometry()

        for wire in wires:
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

        if isinstance(environment, FreeSpaceEnvironment):
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
        elif isinstance(environment, PerfectGroundEnvironment):
            # Finaliza la geometría con un plano de tierra en z=0.
            context.geometry_complete(1)

            # Tierra perfectamente conductora, sin radiales.
            context.gn_card(
                1,
                0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
            )
        else:
            raise ValueError(
                "PyNecEngine no admite este tipo de entorno: "
                f"{environment!r}."
            )

        return context

    def _add_source(
        self,
        context: Any,
        source: VoltageSource,
    ) -> None:
        """Agrega una fuente de tensión al contexto."""
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

    def _get_impedance(
        self,
        context: Any,
        index: int,
    ) -> complex:
        """Obtiene y normaliza una impedancia calculada."""
        raw_impedance = (
            context
            .get_input_parameters(index)
            .get_impedance()
        )

        if hasattr(raw_impedance, "item"):
            return complex(raw_impedance.item())

        return complex(raw_impedance)
