"""Adaptador del motor NEC2++ proporcionado por PyNEC."""

from typing import Any

from PyNEC import nec_context

from yaas.domain import (
    Environment,
    FreeSpaceEnvironment,
    PerfectGroundEnvironment,
    RealGroundEnvironment,
    RealGroundModel,
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
        impedance = self._simulate_single_point(
            wires=request.wires,
            environment=request.environment,
            source=request.source,
            frequency_mhz=request.frequency_mhz,
        )

        return SimulationResult(
            frequency_mhz=request.frequency_mhz,
            impedance=impedance,
            swr=calculate_swr(
                impedance=impedance,
                reference_impedance=request.reference_impedance,
            ),
        )

    def simulate_sweep(
        self,
        request: SweepRequest,
    ) -> SweepResult:
        """Ejecuta un barrido lineal de frecuencia.

        Para espacio libre y tierra perfecta se conserva la estrategia
        histórica: una única llamada a NEC2++ con ``fr_card`` cubre
        todo el barrido en un mismo contexto (sin reconstruir
        geometría por punto). Para tierra real (Sommerfeld-Norton) se
        crea un contexto NEC2++ completamente nuevo por cada
        frecuencia (ver ``_simulate_sweep_per_frequency``): la
        investigación en ``docs/research/nec-real-ground.md`` y su
        validación en ``docs/validation/real-ground-dipole-4nec2.md``
        encontraron que reutilizar un único contexto puede introducir
        una discrepancia sistemática frente al cálculo independiente
        por frecuencia para geometrías cercanas al plano de tierra.
        """
        if isinstance(request.environment, RealGroundEnvironment):
            return self._simulate_sweep_per_frequency(request)

        return self._simulate_sweep_single_context(request)

    def _simulate_sweep_single_context(
        self,
        request: SweepRequest,
    ) -> SweepResult:
        """Barrido de contexto único (espacio libre y tierra perfecta)."""
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

            points.append(
                self._build_sweep_point(
                    frequency_mhz=frequency_mhz,
                    impedance=impedance,
                    reference_impedance=request.reference_impedance,
                )
            )

        return SweepResult(points=tuple(points))

    def _simulate_sweep_per_frequency(
        self,
        request: SweepRequest,
    ) -> SweepResult:
        """Barrido de contexto nuevo por frecuencia (tierra real).

        Cada punto reconstruye geometría, ``GE``/``GN`` y fuente desde
        cero en un contexto NEC2++ recién creado (vía
        ``_simulate_single_point``), y ejecuta exactamente una
        frecuencia. Ningún estado ni tabla de Sommerfeld-Norton se
        comparte entre puntos. Los puntos se devuelven en el mismo
        orden solicitado (ascendente, de ``start_frequency_mhz`` a
        ``stop_frequency_mhz``).

        YAAS no admite todavía cargas concentradas (ver
        ``SimulationRequest``/``SweepRequest`` en
        ``yaas.domain.models``, que no declaran ningún campo
        ``loads``, y el mensaje "Concentrated loads are not supported
        yet." ya existente en la CLI): no hay ninguna carga que
        aplicar ni una sola vez ni dos veces en ningún contexto.
        """
        points: list[SweepPoint] = []

        for index in range(request.points):
            frequency_mhz = (
                request.start_frequency_mhz
                + index * request.frequency_step_mhz
            )

            impedance = self._simulate_single_point(
                wires=request.wires,
                environment=request.environment,
                source=request.source,
                frequency_mhz=frequency_mhz,
            )

            points.append(
                self._build_sweep_point(
                    frequency_mhz=frequency_mhz,
                    impedance=impedance,
                    reference_impedance=request.reference_impedance,
                )
            )

        return SweepResult(points=tuple(points))

    def _simulate_single_point(
        self,
        wires: tuple[Wire, ...],
        environment: Environment,
        source: VoltageSource,
        frequency_mhz: float,
    ) -> complex:
        """Ejecuta una única frecuencia en un contexto NEC2++ recién creado.

        Usada tanto por ``simulate`` como por
        ``_simulate_sweep_per_frequency``, para no duplicar la
        secuencia geometría -> GE/GN -> frecuencia -> fuente ->
        ejecución (idéntica a la ya usada antes de este refactor: ver
        ``fr_card`` antes que ``_add_source``/``ex_card`` más abajo).
        """
        context = self._create_context(wires, environment)

        context.fr_card(
            0,
            1,
            frequency_mhz,
            0.0,
        )

        self._add_source(context, source)
        context.xq_card(0)

        return self._get_impedance(context, 0)

    def _build_sweep_point(
        self,
        frequency_mhz: float,
        impedance: complex,
        reference_impedance: float,
    ) -> SweepPoint:
        """Construye un punto de barrido junto con su ROE."""
        return SweepPoint(
            frequency_mhz=frequency_mhz,
            impedance=impedance,
            swr=calculate_swr(
                impedance=impedance,
                reference_impedance=reference_impedance,
            ),
        )

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

        La selección de tierra depende exclusivamente del tipo de
        ``environment`` (y, para tierra real, de su ``model``, ya
        validado como ``RealGroundModel`` por el dominio) — nunca de
        un entero de ``ground_type`` provisto directamente por quien
        llama.
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
        elif isinstance(environment, RealGroundEnvironment):
            if environment.model is not RealGroundModel.SOMMERFELD_NORTON:
                raise ValueError(
                    "PyNecEngine no admite este RealGroundModel: "
                    f"{environment.model!r}."
                )

            # Finaliza la geometría con un plano de tierra en z=0.
            context.geometry_complete(1)

            # Tierra real, método Sommerfeld-Norton, sin radiales.
            context.gn_card(
                2,
                0,
                environment.relative_permittivity,
                environment.conductivity_s_per_m,
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
