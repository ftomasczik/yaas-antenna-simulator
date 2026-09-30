"""Adaptador del motor NEC2++ proporcionado por PyNEC."""

import math
from typing import Any

from PyNEC import nec_context

from yaas.domain import (
    Environment,
    FreeSpaceEnvironment,
    PerfectGroundEnvironment,
    RadiationPatternRequest,
    RadiationPatternResult,
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


# Valor centinela que NEC2 usa para una ganancia nula o no
# representable (por ejemplo, a lo largo del eje de un dipolo). No es
# una ganancia física: se traduce a ``None`` en el dominio.
_NEC_NULL_GAIN_DB = -999.99

# Tolerancia puramente absoluta (se usa con rel_tol=0.0) para reconocer
# el centinela: solo absorbe diferencias de representación en punto
# flotante; ninguna ganancia física calculada queda a menos de 1e-6 dB
# de -999.99.
_NEC_NULL_GAIN_TOLERANCE_DB = 1e-6

# Cada solicitud usa un contexto NEC2++ nuevo con una única frecuencia
# y una única tarjeta RP, así que el contexto contiene exactamente un
# patrón: el índice 0 (antes de rp_card() ese índice devuelve None).
_SINGLE_PATTERN_INDEX = 0


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

    def simulate_radiation_pattern(
        self,
        request: RadiationPatternRequest,
    ) -> RadiationPatternResult:
        """Calcula un patrón de radiación a una única frecuencia.

        Cada solicitud usa un contexto NEC2++ recién creado, con el
        orden de llamadas interno verificado para la API de PyNEC en
        ``docs/research/nec-radiation-patterns.md`` (§1.4, punto 1):
        geometría -> ``GE``/``GN`` -> ``fr_card`` -> ``ex_card`` ->
        ``rp_card``. ``rp_card()`` ya ejecuta el cálculo por sí solo,
        así que no se llama a ``xq_card()``. Este orden describe la API
        de PyNEC usada por YAAS, no un orden obligatorio para archivos
        NEC de texto.

        El dominio ya garantiza conteos positivos y ``theta <= 90``
        con plano de tierra, así que esas reglas no se repiten aquí.
        """
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

        # Firma real de PyNEC 2.3.4: rp_card(calc_mode, n_theta,
        # n_phi, output_format, normalization, D, A, theta0, phi0,
        # delta_theta, delta_phi, radial_distance, gain_norm). El
        # campo XNDA de la tarjeta RP llega desempaquetado en cuatro
        # enteros: X=0, N=0 (sin normalizar), D=0 (ganancia de
        # potencia), A=0 (sin promedio).
        context.rp_card(
            0,
            request.theta.count,
            request.phi.count,
            0,
            0,
            0,
            0,
            request.theta.start_deg,
            request.phi.start_deg,
            request.theta.step_deg,
            request.phi.step_deg,
            0.0,
            0.0,
        )

        pattern = context.get_radiation_pattern(_SINGLE_PATTERN_INDEX)

        if pattern is None:
            raise RuntimeError(
                "PyNEC no devolvió ningún patrón de radiación."
            )

        return self._build_radiation_pattern_result(request, pattern)

    def _build_radiation_pattern_result(
        self,
        request: RadiationPatternRequest,
        pattern: Any,
    ) -> RadiationPatternResult:
        """Convierte el patrón nativo en un resultado de dominio.

        Comprueba que la salida nativa tenga la forma solicitada antes
        de construir el resultado, para que un fallo de integración
        aparezca como ``RuntimeError`` descriptivo y no como un
        ``IndexError`` incidental. ``get_gain()`` ya viene orientada
        como ``(n_theta, n_phi)``; se conserva esa orientación.
        """
        theta_angles = self._native_angles(
            pattern.get_theta_angles(),
            "theta",
            request.theta.count,
        )
        phi_angles = self._native_angles(
            pattern.get_phi_angles(),
            "phi",
            request.phi.count,
        )

        expected_shape = (len(theta_angles), len(phi_angles))
        native_gain = pattern.get_gain()

        try:
            rows = [tuple(row) for row in native_gain]
        except TypeError:
            rows = None

        if rows is None or len(rows) != expected_shape[0] or any(
            len(row) != expected_shape[1] for row in rows
        ):
            raise RuntimeError(
                "PyNEC devolvió una matriz de ganancia con forma "
                f"{getattr(native_gain, 'shape', None)!r}; se esperaba "
                f"{expected_shape!r} (n_theta, n_phi)."
            )

        gain_db = tuple(
            tuple(
                self._native_gain(
                    value,
                    theta_angles[theta_index],
                    phi_angles[phi_index],
                )
                for phi_index, value in enumerate(row)
            )
            for theta_index, row in enumerate(rows)
        )

        return RadiationPatternResult(
            frequency_mhz=request.frequency_mhz,
            theta_angles_deg=theta_angles,
            phi_angles_deg=phi_angles,
            gain_db=gain_db,
        )

    def _native_angles(
        self,
        native_angles: Any,
        name: str,
        expected_count: int,
    ) -> tuple[float, ...]:
        """Convierte ángulos nativos a floats de Python y los verifica."""
        try:
            angles = tuple(float(angle) for angle in native_angles)
        except (TypeError, ValueError) as error:
            raise RuntimeError(
                f"PyNEC devolvió ángulos {name} que no pueden "
                f"convertirse a números: {native_angles!r}."
            ) from error

        if len(angles) != expected_count:
            raise RuntimeError(
                f"PyNEC devolvió {len(angles)} ángulos {name}; se "
                f"esperaban {expected_count}."
            )

        if not all(math.isfinite(angle) for angle in angles):
            raise RuntimeError(
                f"PyNEC devolvió ángulos {name} no finitos: {angles!r}."
            )

        return angles

    def _native_gain(
        self,
        native_value: Any,
        theta_deg: float,
        phi_deg: float,
    ) -> float | None:
        """Convierte una ganancia nativa; el centinela NEC pasa a None."""
        try:
            gain = float(native_value)
        except (TypeError, ValueError) as error:
            raise RuntimeError(
                "PyNEC devolvió una ganancia que no puede convertirse a "
                f"número ({native_value!r}) en theta={theta_deg:g}, "
                f"phi={phi_deg:g} grados."
            ) from error

        if not math.isfinite(gain):
            raise RuntimeError(
                f"PyNEC devolvió una ganancia no finita ({gain!r}) en "
                f"theta={theta_deg:g}, phi={phi_deg:g} grados."
            )

        if math.isclose(
            gain,
            _NEC_NULL_GAIN_DB,
            rel_tol=0.0,
            abs_tol=_NEC_NULL_GAIN_TOLERANCE_DB,
        ):
            return None

        return gain

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
