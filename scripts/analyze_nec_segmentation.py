"""Estudio reproducible de convergencia de segmentacion uniforme NEC2++.

Fase 6B.2 (revision 2). Material de investigacion, no codigo de
produccion: no se importa desde ``antsim`` ni se invoca desde la CLI.
No define ninguna politica de segmentacion definitiva.

Metodologia de convergencia (revision 2, sin nivel de referencia
fijo): se simulan densidades uniformes lambda/10 .. lambda/640 y se
comparan SOLO pares de niveles sucesivos (40->80, 80->160, 160->320,
320->640). Ningun nivel unico (ni el mas denso, lambda/640, ni el
usado como referencia en la revision anterior, lambda/160) se trata
como "verdad": la convergencia se declara solo si los DOS ULTIMOS
refinamientos (160->320 y 320->640) son estables por si mismos.

Para cada nivel se registra, ademas de R/X/ROE: la magnitud |Z|, el
coeficiente de reflexion complejo (gamma) respecto de la impedancia de
referencia de la geometria, y, entre pares sucesivos, el error
absoluto y relativo de Z y abs(delta gamma). ROE se registra solo como
dato complementario: cerca de una reflexion casi total, ROE es una
funcion muy no lineal de gamma y puede variar de forma no monotona
aunque Z y gamma converjan de forma suave (ver el informe .md).

Organizacion del archivo (separacion pedida entre calculo, geometrias,
analisis y presentacion):

    1. Utilidades de calculo puras (independientes de geometria y de NEC)
    2. Especificacion de geometrias sinteticas
    3. Segmentacion uniforme experimental
    4. Ejecucion (PyNecEngine) y resultados crudos por nivel
    5. Analisis: diferencias sucesivas y clasificacion de convergencia
    6. Presentacion (consola y CSV)
    7. Orquestacion (main)

Uso:

    .venv\\Scripts\\python.exe scripts\\analyze_nec_segmentation.py
    .venv\\Scripts\\python.exe scripts\\analyze_nec_segmentation.py --output-dir C:\\ruta\\propia

La salida legible se imprime por consola. Los CSV (detalle por
conductor, resultados por nivel, diferencias sucesivas) se escriben en
un directorio temporal fuera del repositorio (o en ``--output-dir``),
nunca dentro de el.
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import math
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Sequence

from antsim.domain import Point3D, SimulationRequest, VoltageSource, Wire
from antsim.engines.pynec import PyNecEngine

# =============================================================================
# 1. Utilidades de calculo puras
# =============================================================================

SPEED_OF_LIGHT_M_PER_S = 299_792_458.0
DEFAULT_RADIUS_M = 0.001

# Divisores de longitud de onda estudiados. No hay ningun "divisor de
# referencia": la convergencia se evalua exclusivamente comparando
# pares consecutivos (ver SUCCESSIVE_PAIRS).
DIVISORS: tuple[int, ...] = (10, 20, 40, 80, 160, 320, 640)

# Las diferencias sucesivas formales empiezan en 40 (no en 10 o 20),
# por pedido explicito: 40->80, 80->160, 160->320, 320->640. Se derivan
# de DIVISORS en vez de escribir las 4 tuplas a mano, para que quede
# claro que son "todas las consecutivas desde 40", no una lista
# arbitraria separada que pueda desincronizarse de DIVISORS.
SUCCESSIVE_DIFFERENCE_START_DIVISOR = 40
SUCCESSIVE_PAIRS: tuple[tuple[int, int], ...] = tuple(
    (a, b)
    for a, b in zip(DIVISORS, DIVISORS[1:])
    if a >= SUCCESSIVE_DIFFERENCE_START_DIVISOR
)

# La convergencia se declara solo si los DOS ULTIMOS refinamientos son
# estables (calculado, no una constante separada que pueda
# desincronizarse de SUCCESSIVE_PAIRS).
STABILITY_PAIRS: tuple[tuple[int, int], ...] = SUCCESSIVE_PAIRS[-2:]

# Umbrales de estabilidad entre niveles sucesivos. Se fijan antes de
# mirar los resultados de lambda/320 y lambda/640 y no se ajustan
# despues para forzar una conclusion (ver el informe .md).
CONVERGENCE_DELTA_Z_OHM = 0.5
CONVERGENCE_DELTA_GAMMA = 0.001

# --- Criterio practico de MVP (candidatos uniformes) ---
#
# Distinto del analisis de convergencia de arriba: aqui SI se compara
# cada candidato directamente contra lambda/640, mencionado
# explicitamente como "ancla practica" (no como "verdad") para
# evaluar si un candidato de densidad uniforme fija es aceptable. Se
# aplica UNICAMENTE a geometrias "representativa"; las de "estres" se
# reportan aparte y nunca deciden esta politica por si solas.
#
# MVP_CANDIDATE_DIVISORS se reporta para los tres (continuidad con la
# revision anterior, que ya habia evaluado y rechazado lambda/80).
# MVP_SELECTION_ORDER es el orden de preferencia real para ELEGIR una
# densidad minima (lambda/80 ya fue rechazada antes y no vuelve a
# postularse): se prueba lambda/160 primero (mas barata); si no
# cumple en las 4 geometrias representativas simultaneamente, se
# prueba lambda/320; si tampoco, no se elige ninguna densidad fija.
MVP_CANDIDATE_DIVISORS: tuple[int, ...] = (80, 160, 320)
MVP_SELECTION_ORDER: tuple[int, ...] = (160, 320)
MVP_PRACTICAL_ANCHOR_DIVISOR = 640
MVP_DELTA_Z_OHM = 1.0
MVP_RELATIVE_ERROR = 0.01
MVP_DELTA_GAMMA = 0.005

# Por encima de este |gamma|, no se exige el limite absoluto de
# MVP_DELTA_Z_OHM en las geometrias de estres: cerca de una reflexion
# casi total, Z es una funcion casi singular de gamma (ver el informe
# y el diagnostico de la V invertida), asi que un |delta Z| grande en
# ohms puede coexistir con un gamma bien convergido.
STRESS_ABSOLUTE_ERROR_EXEMPTION_GAMMA = 0.98


def wavelength_m(frequency_mhz: float) -> float:
    return SPEED_OF_LIGHT_M_PER_S / (frequency_mhz * 1e6)


def reflection_coefficient(impedance: complex, reference_impedance: float) -> complex:
    """Gamma = (Z - Z0) / (Z + Z0).

    Se calcula aqui en vez de reutilizar antsim.domain.calculate_swr
    porque esa funcion devuelve ROE, no gamma en si; exponer gamma es
    exactamente el punto de esta revision del estudio (ver el
    docstring del modulo). Formula identica a la que ya usa
    antsim.domain.calculations internamente.
    """
    denominator = impedance + reference_impedance
    if denominator == 0:
        return complex(math.inf, 0.0)
    return (impedance - reference_impedance) / denominator


# =============================================================================
# 2. Especificacion de geometrias sinteticas
# =============================================================================


@dataclass(frozen=True)
class WireSpec:
    """Conductor recto sintetico, antes de decidir su segmentacion."""

    tag: int
    start: tuple[float, float, float]
    end: tuple[float, float, float]
    radius_m: float
    label: str = ""

    @property
    def length_m(self) -> float:
        return math.dist(self.start, self.end)


# "representativa": geometria cercana a resonancia, cuyo resultado
# puede informar una politica general de segmentacion. "estres": caso
# deliberadamente dificil (gamma cercano a 1) que se conserva para
# diagnostico, pero que NUNCA decide por si solo la politica general
# (ver la seccion de evaluacion del criterio de MVP en main()).
GeometryClassification = Literal["representativa", "estres"]


@dataclass(frozen=True)
class GeometrySpec:
    """Geometria sintetica completa, independiente de la segmentacion."""

    name: str
    frequency_mhz: float
    wires: tuple[WireSpec, ...]
    fed_wire_tag: int
    classification: GeometryClassification
    reference_impedance: float = 50.0
    notes: str = ""

    @property
    def wavelength_m(self) -> float:
        return wavelength_m(self.frequency_mhz)


def build_reference_dipole() -> GeometrySpec:
    """Dipolo recto de referencia: 14.15 MHz, 10.06 m, radio 1 mm."""
    return GeometrySpec(
        name="Dipolo de referencia",
        frequency_mhz=14.15,
        wires=(
            WireSpec(
                tag=1,
                start=(-5.03, 0.0, 0.0),
                end=(5.03, 0.0, 0.0),
                radius_m=DEFAULT_RADIUS_M,
                label="dipolo",
            ),
        ),
        fed_wire_tag=1,
        classification="representativa",
        notes=(
            "Mismo dipolo usado como referencia en el resto del "
            "proyecto (examples/dipole-20m.antsim)."
        ),
    )


def build_simple_yagi() -> GeometrySpec:
    """Yagi sintetico de 3 elementos (reflector/excitado/director).

    Los tres elementos son conductores paralelos, sin ninguna conexion
    electrica entre si (como en una Yagi real: los elementos
    parasitos acoplan solo por campo cercano). Dimensiones elegidas
    solo para ejercitar la topologia Yagi, no para representar un
    diseno resonante real.
    """
    frequency_mhz = 14.15
    boom_spacing_m = 0.2 * wavelength_m(frequency_mhz)

    driven_half_length_m = 5.03
    reflector_half_length_m = driven_half_length_m * 1.05
    director_half_length_m = driven_half_length_m * 0.95

    return GeometrySpec(
        name="Yagi simple (3 elementos)",
        frequency_mhz=frequency_mhz,
        wires=(
            WireSpec(
                tag=1,
                start=(-reflector_half_length_m, -boom_spacing_m, 0.0),
                end=(reflector_half_length_m, -boom_spacing_m, 0.0),
                radius_m=DEFAULT_RADIUS_M,
                label="reflector",
            ),
            WireSpec(
                tag=2,
                start=(-driven_half_length_m, 0.0, 0.0),
                end=(driven_half_length_m, 0.0, 0.0),
                radius_m=DEFAULT_RADIUS_M,
                label="excitado",
            ),
            WireSpec(
                tag=3,
                start=(-director_half_length_m, boom_spacing_m, 0.0),
                end=(director_half_length_m, boom_spacing_m, 0.0),
                radius_m=DEFAULT_RADIUS_M,
                label="director",
            ),
        ),
        fed_wire_tag=2,
        classification="representativa",
        notes=(
            "Elementos electricamente independientes; acoplan solo "
            f"por proximidad. Espaciamiento de boom sintetico: "
            f"0.2*lambda = {boom_spacing_m:.4f} m."
        ),
    )


def build_rectangular_loop() -> GeometrySpec:
    """Loop cuadrado de onda completa (perimetro ~= 1 lambda).

    Los extremos de conductores adyacentes se construyen a partir de
    las MISMAS tuplas de esquina (no se recalculan por separado) para
    garantizar coincidencia exacta bit a bit. La fuente esta al centro
    de un lado, nunca en una esquina.
    """
    frequency_mhz = 14.15
    side_length_m = wavelength_m(frequency_mhz) / 4.0
    half = side_length_m / 2.0

    corner_a = (-half, -half, 0.0)
    corner_b = (half, -half, 0.0)
    corner_c = (half, half, 0.0)
    corner_d = (-half, half, 0.0)

    return GeometrySpec(
        name="Loop cuadrado (onda completa)",
        frequency_mhz=frequency_mhz,
        wires=(
            WireSpec(1, corner_a, corner_b, DEFAULT_RADIUS_M, "lado inferior (alimentado)"),
            WireSpec(2, corner_b, corner_c, DEFAULT_RADIUS_M, "lado derecho"),
            WireSpec(3, corner_c, corner_d, DEFAULT_RADIUS_M, "lado superior"),
            WireSpec(4, corner_d, corner_a, DEFAULT_RADIUS_M, "lado izquierdo"),
        ),
        fed_wire_tag=1,
        classification="representativa",
        notes=(
            f"Perimetro = lambda = {wavelength_m(frequency_mhz):.4f} m; "
            f"lado = {side_length_m:.4f} m."
        ),
    )


def _build_inverted_v(
    *,
    name: str,
    apex_half_width_m: float,
    apex_height_m: float,
    leg_end_height_m: float,
    leg_horizontal_reach_m: float,
    classification: GeometryClassification,
    notes: str,
) -> GeometrySpec:
    """Fabrica comun para las tres variantes de V invertida.

    Se evita deliberadamente alimentar en el vertice (union de dos
    conductores): ``VoltageSource(wire_tag, segment)`` referencia un
    unico conductor y no hay forma inequivoca de representar una
    fuente compartida entre dos que solo coinciden en un extremo. En
    su lugar, un tercer conductor ("seccion central") ocupa el
    vertice y se alimenta en su propio centro; las dos patas se
    conectan a los extremos de esa seccion (union estructural, nunca
    alimentada). Los cuatro parametros geometricos (ancho de la
    seccion central, altura del vertice, altura y alcance horizontal
    de las puntas de pata) son explicitos para que cada variante
    (estres o representativa) documente sus propias dimensiones sin
    reutilizar valores por defecto ocultos.
    """
    apex_left = (-apex_half_width_m, 0.0, apex_height_m)
    apex_right = (apex_half_width_m, 0.0, apex_height_m)

    return GeometrySpec(
        name=name,
        frequency_mhz=14.15,
        wires=(
            WireSpec(1, apex_left, apex_right, DEFAULT_RADIUS_M, "seccion central (alimentada)"),
            WireSpec(
                2, apex_left, (-leg_horizontal_reach_m, 0.0, leg_end_height_m),
                DEFAULT_RADIUS_M, "pata izquierda",
            ),
            WireSpec(
                3, apex_right, (leg_horizontal_reach_m, 0.0, leg_end_height_m),
                DEFAULT_RADIUS_M, "pata derecha",
            ),
        ),
        fed_wire_tag=1,
        classification=classification,
        notes=notes,
    )


def build_inverted_v_short_center() -> GeometrySpec:
    """[ESTRES] V invertida original: seccion central de 1.0 m (apice agudo).

    Deliberadamente fuera de resonancia (|gamma| ~ 0.99, ver informe).
    Se conserva como caso de estres, no decide la politica general.
    """
    return _build_inverted_v(
        name="[ESTRES] V invertida, seccion central corta (1.0 m)",
        apex_half_width_m=0.5,
        apex_height_m=8.0,
        leg_end_height_m=0.5,
        leg_horizontal_reach_m=5.03,
        classification="estres",
        notes=(
            "Seccion central de 1.0 m alimentada a su centro; cada "
            "pata desciende desde un extremo de esa seccion hasta "
            "0.5 m de altura a 5.03 m de distancia horizontal. "
            "Geometria fuera de resonancia a proposito (ver informe)."
        ),
    )


def build_inverted_v_long_center() -> GeometrySpec:
    """[ESTRES] Variante con seccion central mas larga (5.0 m, techo plano).

    Se agrego para diagnosticar si la variacion no monotona de ROE de
    la variante corta se relaciona con que su seccion central (1.0 m)
    tiene muy pocos segmentos en las densidades mas gruesas. Ampliar la
    seccion central a 5.0 m cambia el conductor alimentado sin cambiar
    la posicion de las puntas de las patas, para aislar esa unica
    variable. Sigue deliberadamente fuera de resonancia (|gamma| ~
    0.99): tambien es un caso de estres, no decide la politica general.
    """
    return _build_inverted_v(
        name="[ESTRES] V invertida, seccion central larga (5.0 m)",
        apex_half_width_m=2.5,
        apex_height_m=8.0,
        leg_end_height_m=0.5,
        leg_horizontal_reach_m=5.03,
        classification="estres",
        notes=(
            "Seccion central de 5.0 m (techo plano, no apice agudo) "
            "alimentada a su centro; mismas puntas de pata que la "
            "variante corta (0.5 m de altura, 5.03 m de distancia "
            "horizontal), por lo que las patas resultan mas cortas y "
            "menos inclinadas que en la variante original."
        ),
    )


def build_inverted_v_near_resonance() -> GeometrySpec:
    """[REPRESENTATIVA] V invertida cercana a resonancia.

    Geometria conectada nueva (a diferencia de las dos variantes de
    estres, elegida para acercarse a resonancia, no para alejarse de
    ella). Dimensiones:

    - Seccion central alimentada: 0.30 m total (0.15 m a cada lado del
      centro). Pequena pero fisicamente justificable: un tramo recto
      corto en el vertice, del orden del aislador/soporte central de
      una V invertida real, muy por debajo de los 1.0 m / 5.0 m de las
      variantes de estres.
    - Vertice a 6.0 m de altura, puntas de pata a 2.0 m de altura
      (caida de 4.0 m): dimensiones de mastil modestas, tipicas de una
      instalacion de aficionado en HF.
    - Longitud de cada pata: 4.88 m, elegida junto con la seccion
      central (0.15 m) para que cada "brazo" completo (centro + pata)
      sea 5.03 m -- la MISMA longitud de medio dipolo que ya se sabe
      cercana a resonancia en el dipolo de referencia de este mismo
      estudio a 14.15 MHz. Reutilizar esa longitud conocida es la
      justificacion de diseno, no un ajuste posterior a los
      resultados: la posicion horizontal de la punta de pata
      (2.9454 m) es la que resulta de imponer esa longitud de pata
      junto con la caida de altura de 4.0 m, no un valor elegido
      libremente.
    - Radio: 0.001 m, igual que el resto del estudio.
    - Extremos de la seccion central y de cada pata coinciden
      exactamente (mismas tuplas), igual que en las otras geometrias
      conectadas.

    No se ajusto ninguna dimension despues de simular para favorecer
    una densidad en particular: los numeros de arriba se fijaron antes
    de correr el estudio completo.
    """
    apex_half_width_m = 0.15
    apex_height_m = 6.0
    leg_end_height_m = 2.0
    leg_length_m = 5.03 - apex_half_width_m  # brazo total = 5.03 m, como el dipolo

    height_drop_m = apex_height_m - leg_end_height_m
    horizontal_delta_m = math.sqrt(leg_length_m**2 - height_drop_m**2)
    leg_horizontal_reach_m = apex_half_width_m + horizontal_delta_m

    return _build_inverted_v(
        name="[REPRESENTATIVA] V invertida cercana a resonancia",
        apex_half_width_m=apex_half_width_m,
        apex_height_m=apex_height_m,
        leg_end_height_m=leg_end_height_m,
        leg_horizontal_reach_m=leg_horizontal_reach_m,
        classification="representativa",
        notes=(
            f"Seccion central: {2 * apex_half_width_m:.2f} m total, "
            f"alimentada a su centro. Vertice a {apex_height_m:.1f} m, "
            f"puntas de pata a {leg_end_height_m:.1f} m de altura "
            f"({leg_horizontal_reach_m:.4f} m de distancia horizontal), "
            f"pata de {leg_length_m:.4f} m. Brazo total (centro+pata) "
            "= 5.03 m, igual al medio-dipolo de referencia de este "
            "estudio (justificacion de diseno, no ajustado post-hoc)."
        ),
    )


def build_geometries() -> tuple[GeometrySpec, ...]:
    return (
        build_reference_dipole(),
        build_simple_yagi(),
        build_rectangular_loop(),
        build_inverted_v_near_resonance(),
        build_inverted_v_short_center(),
        build_inverted_v_long_center(),
    )


# =============================================================================
# 3. Segmentacion uniforme experimental
# =============================================================================


@dataclass(frozen=True)
class WireSegmentInfo:
    """Segmentacion decidida para un conductor en un divisor dado."""

    geometry_name: str
    divisor: int
    tag: int
    label: str
    is_fed: bool
    length_m: float
    radius_m: float
    raw_segments: int
    floored_to_one: bool
    forced_odd: bool
    segments: int
    segment_length_m: float
    length_to_radius_ratio: float


def uniform_segments_for_wire(
    wire: WireSpec,
    target_length_m: float,
    *,
    geometry_name: str,
    divisor: int,
    is_fed: bool,
) -> WireSegmentInfo:
    """target_length = lambda/divisor; segments = ceil(long/target), piso 1.

    Regla experimental adicional: si el conductor es el alimentado y
    el resultado es par, se suma 1 (para tener un segmento central
    exacto). Ningun ajuste se aplica en silencio: ambos (piso a 1,
    forzado a impar) quedan registrados en los campos booleanos de
    WireSegmentInfo y se muestran en la salida. Esta formula sigue sin
    presentarse como politica definitiva.
    """
    raw_segments = math.ceil(wire.length_m / target_length_m)

    floored_to_one = raw_segments < 1
    segments = max(1, raw_segments)

    forced_odd = False
    if is_fed and segments % 2 == 0:
        segments += 1
        forced_odd = True

    segment_length_m = wire.length_m / segments

    return WireSegmentInfo(
        geometry_name=geometry_name,
        divisor=divisor,
        tag=wire.tag,
        label=wire.label,
        is_fed=is_fed,
        length_m=wire.length_m,
        radius_m=wire.radius_m,
        raw_segments=raw_segments,
        floored_to_one=floored_to_one,
        forced_odd=forced_odd,
        segments=segments,
        segment_length_m=segment_length_m,
        length_to_radius_ratio=segment_length_m / wire.radius_m,
    )


# =============================================================================
# 4. Ejecucion (PyNecEngine) y resultados crudos por nivel
# =============================================================================


@dataclass
class CaseResult:
    """Resultado crudo de UN nivel (una geometria, un divisor).

    No contiene ninguna comparacion contra otro nivel: eso es
    responsabilidad exclusiva de SuccessiveDifference (seccion 5), a
    proposito, para que ningun nivel pueda colarse como "referencia"
    dentro de este tipo.
    """

    geometry_name: str
    frequency_mhz: float
    divisor: int
    wire_segments: tuple[WireSegmentInfo, ...]
    total_segments: int
    min_segment_length_m: float
    max_segment_length_m: float
    min_length_to_radius_ratio: float
    resistance_ohm: float | None
    reactance_ohm: float | None
    impedance_magnitude_ohm: float | None
    reflection_coefficient: complex | None
    swr: float | None
    simulation_time_s: float
    is_finite: bool
    error: str | None = None


def _build_domain_request(
    geometry: GeometrySpec,
    wire_segments: tuple[WireSegmentInfo, ...],
) -> SimulationRequest:
    wires_by_tag = {wire.tag: wire for wire in geometry.wires}

    wires = tuple(
        Wire(
            tag=info.tag,
            start=Point3D(*wires_by_tag[info.tag].start),
            end=Point3D(*wires_by_tag[info.tag].end),
            radius_m=info.radius_m,
            segments=info.segments,
        )
        for info in wire_segments
    )

    fed_info = next(info for info in wire_segments if info.is_fed)
    center_segment = (fed_info.segments + 1) // 2

    return SimulationRequest(
        frequency_mhz=geometry.frequency_mhz,
        wires=wires,
        source=VoltageSource(wire_tag=geometry.fed_wire_tag, segment=center_segment),
        reference_impedance=geometry.reference_impedance,
    )


def run_case(engine: PyNecEngine, geometry: GeometrySpec, divisor: int) -> CaseResult:
    target_length_m = geometry.wavelength_m / divisor

    wire_segments = tuple(
        uniform_segments_for_wire(
            wire,
            target_length_m,
            geometry_name=geometry.name,
            divisor=divisor,
            is_fed=(wire.tag == geometry.fed_wire_tag),
        )
        for wire in geometry.wires
    )

    total_segments = sum(info.segments for info in wire_segments)
    min_segment_length_m = min(info.segment_length_m for info in wire_segments)
    max_segment_length_m = max(info.segment_length_m for info in wire_segments)
    min_length_to_radius_ratio = min(
        info.length_to_radius_ratio for info in wire_segments
    )

    request = _build_domain_request(geometry, wire_segments)

    start = time.perf_counter()
    try:
        result = engine.simulate(request)
    except Exception as error:  # noqa: BLE001 - estudio exploratorio, se registra y continua
        elapsed = time.perf_counter() - start
        return CaseResult(
            geometry_name=geometry.name,
            frequency_mhz=geometry.frequency_mhz,
            divisor=divisor,
            wire_segments=wire_segments,
            total_segments=total_segments,
            min_segment_length_m=min_segment_length_m,
            max_segment_length_m=max_segment_length_m,
            min_length_to_radius_ratio=min_length_to_radius_ratio,
            resistance_ohm=None,
            reactance_ohm=None,
            impedance_magnitude_ohm=None,
            reflection_coefficient=None,
            swr=None,
            simulation_time_s=elapsed,
            is_finite=False,
            error=f"{type(error).__name__}: {error}",
        )
    elapsed = time.perf_counter() - start

    is_finite = (
        math.isfinite(result.impedance.real)
        and math.isfinite(result.impedance.imag)
        and math.isfinite(result.swr)
    )
    gamma = reflection_coefficient(result.impedance, geometry.reference_impedance)

    return CaseResult(
        geometry_name=geometry.name,
        frequency_mhz=geometry.frequency_mhz,
        divisor=divisor,
        wire_segments=wire_segments,
        total_segments=total_segments,
        min_segment_length_m=min_segment_length_m,
        max_segment_length_m=max_segment_length_m,
        min_length_to_radius_ratio=min_length_to_radius_ratio,
        resistance_ohm=result.impedance.real,
        reactance_ohm=result.impedance.imag,
        impedance_magnitude_ohm=abs(result.impedance),
        reflection_coefficient=gamma,
        swr=result.swr,
        simulation_time_s=elapsed,
        is_finite=is_finite,
    )


# =============================================================================
# 5. Analisis: diferencias sucesivas y clasificacion de convergencia
# =============================================================================


@dataclass
class SuccessiveDifference:
    """Diferencia entre DOS niveles consecutivos (nunca contra uno fijo).

    No repite R/X/gamma de cada extremo (eso ya esta en CaseResult,
    indexable por geometria+divisor); solo guarda las metricas de
    diferencia en si, para no duplicar datos entre ambos tipos.
    """

    geometry_name: str
    from_divisor: int
    to_divisor: int
    absolute_error_ohm: float
    relative_error: float
    abs_delta_gamma: float


def compute_successive_differences(
    cases_by_divisor: dict[int, CaseResult],
) -> list[SuccessiveDifference]:
    differences = []
    for from_divisor, to_divisor in SUCCESSIVE_PAIRS:
        case_from = cases_by_divisor.get(from_divisor)
        case_to = cases_by_divisor.get(to_divisor)

        if (
            case_from is None or case_to is None
            or case_from.error is not None or case_to.error is not None
            or not case_from.is_finite or not case_to.is_finite
        ):
            continue

        z_from = complex(case_from.resistance_ohm, case_from.reactance_ohm)
        z_to = complex(case_to.resistance_ohm, case_to.reactance_ohm)
        absolute_error = abs(z_to - z_from)
        relative_error = (
            absolute_error / abs(z_from) if abs(z_from) > 0 else math.inf
        )
        abs_delta_gamma = abs(
            case_to.reflection_coefficient - case_from.reflection_coefficient
        )

        differences.append(
            SuccessiveDifference(
                geometry_name=case_from.geometry_name,
                from_divisor=from_divisor,
                to_divisor=to_divisor,
                absolute_error_ohm=absolute_error,
                relative_error=relative_error,
                abs_delta_gamma=abs_delta_gamma,
            )
        )
    return differences


def classify_convergence(differences: list[SuccessiveDifference]) -> bool | None:
    """Convergencia SOLO si los dos ULTIMOS refinamientos son estables.

    Devuelve None si no hay datos suficientes para evaluar alguno de
    los dos pares de estabilidad (por ejemplo, por un error de
    simulacion en algun nivel involucrado), en vez de asumir
    convergencia o no convergencia por defecto.
    """
    by_pair = {(d.from_divisor, d.to_divisor): d for d in differences}

    for pair in STABILITY_PAIRS:
        if pair not in by_pair:
            return None

    return all(
        by_pair[pair].absolute_error_ohm <= CONVERGENCE_DELTA_Z_OHM
        and by_pair[pair].abs_delta_gamma <= CONVERGENCE_DELTA_GAMMA
        for pair in STABILITY_PAIRS
    )


@dataclass
class MvpCandidateComparison:
    """Comparacion directa de UN candidato contra el ancla practica (lambda/640).

    Distinta de SuccessiveDifference: esta SI usa un nivel fijo como
    punto de comparacion, mencionado explicitamente como "ancla
    practica" para evaluar un candidato de densidad uniforme fija
    concreto, no como "verdad" general (esa distincion se mantiene
    solo para el analisis de convergencia por diferencias sucesivas,
    que sigue sin usar ningun nivel fijo). ``candidate_divisor``
    identifica de cual candidato se trata (por ejemplo, 80, 160 o
    320), para poder evaluar varios candidatos con el mismo tipo sin
    duplicar campos por candidato.
    """

    geometry_name: str
    classification: GeometryClassification
    candidate_divisor: int
    resistance_candidate: float
    reactance_candidate: float
    impedance_magnitude_candidate: float
    resistance_anchor: float
    reactance_anchor: float
    impedance_magnitude_anchor: float
    absolute_error_ohm: float
    relative_error: float
    gamma_candidate_real: float
    gamma_candidate_imag: float
    gamma_anchor_real: float
    gamma_anchor_imag: float
    abs_delta_gamma: float
    abs_gamma_anchor: float


def compute_mvp_candidate_comparison(
    geometry: GeometrySpec,
    cases_by_divisor: dict[int, CaseResult],
    candidate_divisor: int,
) -> MvpCandidateComparison | None:
    case_candidate = cases_by_divisor.get(candidate_divisor)
    case_anchor = cases_by_divisor.get(MVP_PRACTICAL_ANCHOR_DIVISOR)

    if (
        case_candidate is None or case_anchor is None
        or case_candidate.error is not None or case_anchor.error is not None
        or not case_candidate.is_finite or not case_anchor.is_finite
    ):
        return None

    z_candidate = complex(case_candidate.resistance_ohm, case_candidate.reactance_ohm)
    z_anchor = complex(case_anchor.resistance_ohm, case_anchor.reactance_ohm)
    absolute_error = abs(z_anchor - z_candidate)
    relative_error = (
        absolute_error / abs(z_candidate) if abs(z_candidate) > 0 else math.inf
    )
    abs_delta_gamma = abs(
        case_anchor.reflection_coefficient - case_candidate.reflection_coefficient
    )

    return MvpCandidateComparison(
        geometry_name=geometry.name,
        classification=geometry.classification,
        candidate_divisor=candidate_divisor,
        resistance_candidate=case_candidate.resistance_ohm,
        reactance_candidate=case_candidate.reactance_ohm,
        impedance_magnitude_candidate=case_candidate.impedance_magnitude_ohm,
        resistance_anchor=case_anchor.resistance_ohm,
        reactance_anchor=case_anchor.reactance_ohm,
        impedance_magnitude_anchor=case_anchor.impedance_magnitude_ohm,
        absolute_error_ohm=absolute_error,
        relative_error=relative_error,
        gamma_candidate_real=case_candidate.reflection_coefficient.real,
        gamma_candidate_imag=case_candidate.reflection_coefficient.imag,
        gamma_anchor_real=case_anchor.reflection_coefficient.real,
        gamma_anchor_imag=case_anchor.reflection_coefficient.imag,
        abs_delta_gamma=abs_delta_gamma,
        abs_gamma_anchor=abs(case_anchor.reflection_coefficient),
    )


def evaluate_mvp_criteria(comparison: MvpCandidateComparison) -> bool:
    """Aplica el criterio practico de MVP (ver constantes MVP_*).

    Para geometrias de estres con |gamma| >= el umbral de exencion, no
    se exige el limite absoluto de Z (ver
    STRESS_ABSOLUTE_ERROR_EXEMPTION_GAMMA): la singularidad Z(gamma)
    cerca de reflexion total hace que ese limite sea, por diseno,
    virtualmente imposible de cumplir sin que eso indique nada malo
    sobre la convergencia real de gamma.
    """
    exempt_from_absolute_limit = (
        comparison.classification == "estres"
        and comparison.abs_gamma_anchor >= STRESS_ABSOLUTE_ERROR_EXEMPTION_GAMMA
    )

    meets_absolute = (
        exempt_from_absolute_limit
        or comparison.absolute_error_ohm <= MVP_DELTA_Z_OHM
    )
    meets_relative = comparison.relative_error <= MVP_RELATIVE_ERROR
    meets_gamma = comparison.abs_delta_gamma <= MVP_DELTA_GAMMA

    return meets_absolute and meets_relative and meets_gamma


def select_uniform_density(
    comparisons_by_candidate: dict[int, list[MvpCandidateComparison]],
    geometries: tuple[GeometrySpec, ...],
) -> tuple[int | None, dict[int, bool | None]]:
    """Elige la densidad uniforme fija minima segun MVP_SELECTION_ORDER.

    Prueba cada candidato de MVP_SELECTION_ORDER en orden; el primero
    que cumpla el criterio practico en las 4 geometrias
    representativas SIMULTANEAMENTE gana. Las geometrias de estres
    nunca participan en esta decision (se filtran explicitamente).

    Devuelve (divisor_elegido_o_None, resultado_por_candidato), donde
    resultado_por_candidato mapea cada divisor de MVP_SELECTION_ORDER a
    True (cumple en las 4), False (no cumple en alguna) o None (faltan
    datos validos en alguna geometria representativa).
    """
    expected_representative_count = sum(
        1 for g in geometries if g.classification == "representativa"
    )

    result_by_candidate: dict[int, bool | None] = {}
    for candidate_divisor in MVP_SELECTION_ORDER:
        comparisons = [
            c for c in comparisons_by_candidate.get(candidate_divisor, [])
            if c.classification == "representativa"
        ]
        if len(comparisons) < expected_representative_count:
            result_by_candidate[candidate_divisor] = None
        else:
            result_by_candidate[candidate_divisor] = all(
                evaluate_mvp_criteria(c) for c in comparisons
            )

    for candidate_divisor in MVP_SELECTION_ORDER:
        if result_by_candidate[candidate_divisor] is True:
            return candidate_divisor, result_by_candidate

    return None, result_by_candidate


# =============================================================================
# 6. Presentacion (consola y CSV)
# =============================================================================


def _write_dataclass_csv(path: Path, rows: Sequence) -> None:
    """Escribe una lista de instancias de UNA dataclass como CSV.

    Generico para evitar repetir manualmente la lista de columnas por
    cada tipo de fila (WireSegmentInfo, CaseResult, SuccessiveDifference
    comparten este mismo escritor). Los valores complejos (por ejemplo
    CaseResult.reflection_coefficient) se descomponen en
    <campo>_real/<campo>_imag porque el modulo csv no serializa
    `complex` de forma legible. Los campos cuyo valor es una tupla
    (por ejemplo CaseResult.wire_segments, que anida otra dataclass)
    se omiten deliberadamente: ese detalle se exporta aparte, en su
    propio CSV de nivel mas fino.
    """
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    sample = rows[0]
    scalar_field_names = [
        f.name for f in dataclasses.fields(sample)
        if not isinstance(getattr(sample, f.name), tuple)
    ]

    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file)

        header = []
        for name in scalar_field_names:
            if isinstance(getattr(sample, name), complex):
                header.extend([f"{name}_real", f"{name}_imag"])
            else:
                header.append(name)
        writer.writerow(header)

        for row in rows:
            values = []
            for name in scalar_field_names:
                value = getattr(row, name)
                if isinstance(value, complex):
                    values.extend([value.real, value.imag])
                else:
                    values.append(value)
            writer.writerow(values)


def _print_wire_segments(case: CaseResult) -> None:
    for info in case.wire_segments:
        adjustments = []
        if info.floored_to_one:
            adjustments.append("piso-a-1")
        if info.forced_odd:
            adjustments.append("forzado-impar")
        adjustments_text = f" [{', '.join(adjustments)}]" if adjustments else ""
        fed_marker = " (alimentado)" if info.is_fed else ""
        print(
            f"    conductor {info.tag} {info.label}{fed_marker}: "
            f"long={info.length_m:.4f} m, segmentos={info.segments} "
            f"(bruto={info.raw_segments}){adjustments_text}, "
            f"long/seg={info.segment_length_m:.5f} m, "
            f"long_seg/radio={info.length_to_radius_ratio:.2f}"
        )


def _print_case(case: CaseResult) -> None:
    print(f"  lambda/{case.divisor:<3d}")
    _print_wire_segments(case)

    if case.error is not None:
        print(f"    ERROR: {case.error}")
        return

    if not case.is_finite:
        print("    ADVERTENCIA: resultado no finito (NaN/inf).")
        return

    gamma = case.reflection_coefficient
    print(
        f"    segmentos totales={case.total_segments}, "
        f"long_seg/radio minimo={case.min_length_to_radius_ratio:.2f}"
    )
    print(
        f"    Z = {case.resistance_ohm:.4f} {case.reactance_ohm:+.4f}j ohm "
        f"(|Z|={case.impedance_magnitude_ohm:.4f}), "
        f"gamma = {gamma.real:.5f} {gamma.imag:+.5f}j, "
        f"ROE (complementario) = {case.swr:.4f}, "
        f"tiempo={case.simulation_time_s:.4f} s"
    )


def _print_successive_differences(differences: list[SuccessiveDifference]) -> None:
    if not differences:
        print("    (sin diferencias sucesivas calculables)")
        return
    for diff in differences:
        stability_marker = " <- par de estabilidad" if (
            (diff.from_divisor, diff.to_divisor) in STABILITY_PAIRS
        ) else ""
        print(
            f"    lambda/{diff.from_divisor} -> lambda/{diff.to_divisor}: "
            f"error absoluto={diff.absolute_error_ohm:.4f} ohm, "
            f"error relativo={diff.relative_error:.5f}, "
            f"abs(delta gamma)={diff.abs_delta_gamma:.6f}"
            f"{stability_marker}"
        )


def _print_fed_wire_diagnosis(cases_by_divisor: dict[int, CaseResult], fed_wire_tag: int) -> None:
    """Diagnostico puramente basado en datos del conductor alimentado.

    Deliberadamente NO interpreta la causa de ningun comportamiento no
    monotono: eso se discute en docs/research/nec-segmentation-convergence.md,
    a partir de estos mismos numeros, no incrustado aqui como texto fijo.
    """
    print("    Diagnostico del conductor alimentado, por nivel:")
    for divisor in DIVISORS:
        case = cases_by_divisor.get(divisor)
        if case is None:
            continue
        fed_info = next((w for w in case.wire_segments if w.tag == fed_wire_tag), None)
        if fed_info is None:
            continue
        if case.reflection_coefficient is not None and case.swr is not None:
            gamma_text = (
                f"gamma=({case.reflection_coefficient.real:.5f}"
                f"{case.reflection_coefficient.imag:+.5f}j)"
            )
            print(
                f"      lambda/{divisor}: {fed_info.segments} segmentos "
                f"(long_seg={fed_info.segment_length_m:.5f} m), {gamma_text}, "
                f"ROE={case.swr:.4f}"
            )
        else:
            print(
                f"      lambda/{divisor}: {fed_info.segments} segmentos, "
                "sin resultado valido"
            )


def _check_repeatability(
    engine: PyNecEngine,
    geometries: tuple[GeometrySpec, ...],
    divisors_to_check: tuple[int, ...],
) -> bool:
    print()
    print(
        "=== Verificacion de repetibilidad "
        f"(niveles {', '.join(f'lambda/{d}' for d in divisors_to_check)}, dos corridas) ==="
    )
    all_match = True
    for geometry in geometries:
        for divisor in divisors_to_check:
            first = run_case(engine, geometry, divisor)
            second = run_case(engine, geometry, divisor)

            if first.error is not None or second.error is not None:
                print(f"  {geometry.name} @ lambda/{divisor}: ERROR, no comparable.")
                all_match = False
                continue

            matches = (
                first.resistance_ohm == second.resistance_ohm
                and first.reactance_ohm == second.reactance_ohm
                and first.swr == second.swr
                and first.total_segments == second.total_segments
            )
            if not matches:
                all_match = False
            print(
                f"  {geometry.name} @ lambda/{divisor}: "
                f"{'OK (identico)' if matches else 'DIFERENTE'}"
            )
    return all_match


def _print_mvp_comparison(comparison: MvpCandidateComparison | None, candidate_divisor: int) -> None:
    print(
        f"\n  Candidato lambda/{candidate_divisor} vs "
        f"ancla practica lambda/{MVP_PRACTICAL_ANCHOR_DIVISOR}:"
    )
    if comparison is None:
        print("    sin datos suficientes (error de simulacion o resultado no finito).")
        return

    print(
        f"    Z(lambda/{candidate_divisor}) = {comparison.resistance_candidate:.4f} "
        f"{comparison.reactance_candidate:+.4f}j ohm "
        f"(|Z|={comparison.impedance_magnitude_candidate:.4f})"
    )
    print(
        f"    Z(lambda/{MVP_PRACTICAL_ANCHOR_DIVISOR}) = {comparison.resistance_anchor:.4f} "
        f"{comparison.reactance_anchor:+.4f}j ohm "
        f"(|Z|={comparison.impedance_magnitude_anchor:.4f})"
    )
    print(
        f"    error absoluto={comparison.absolute_error_ohm:.4f} ohm, "
        f"error relativo={comparison.relative_error:.5f}, "
        f"abs(delta gamma)={comparison.abs_delta_gamma:.6f}, "
        f"|gamma(lambda/{MVP_PRACTICAL_ANCHOR_DIVISOR})|="
        f"{comparison.abs_gamma_anchor:.5f}"
    )
    meets = evaluate_mvp_criteria(comparison)
    exempt = (
        comparison.classification == "estres"
        and comparison.abs_gamma_anchor >= STRESS_ABSOLUTE_ERROR_EXEMPTION_GAMMA
    )
    print(
        f"    [{comparison.classification.upper()}] Cumple criterio "
        f"practico de MVP: {'SI' if meets else 'NO'}"
        + (
            " (exenta del limite absoluto de Z por |gamma| alto)"
            if exempt else ""
        )
    )


def _print_mvp_candidate_summary(
    candidate_divisor: int,
    comparisons: list[MvpCandidateComparison],
    geometries: tuple[GeometrySpec, ...],
) -> bool | None:
    """Imprime el resumen de UN candidato y devuelve si cumple en las representativas.

    True/False si hay datos completos para las geometrias
    representativas; None si falta algun dato (nunca se asume un valor
    por defecto en ese caso).
    """
    representative = [c for c in comparisons if c.classification == "representativa"]
    stress = [c for c in comparisons if c.classification == "estres"]
    expected_representative_count = sum(
        1 for g in geometries if g.classification == "representativa"
    )

    print(f"\n  --- Candidato lambda/{candidate_divisor} ---")
    print("  Geometrias representativas:")
    for comparison in representative:
        meets = evaluate_mvp_criteria(comparison)
        print(
            f"    {comparison.geometry_name}: {'CUMPLE' if meets else 'NO cumple'} "
            f"(|deltaZ|={comparison.absolute_error_ohm:.4f} ohm, "
            f"rel={comparison.relative_error:.5f}, "
            f"abs(dgamma)={comparison.abs_delta_gamma:.6f})"
        )

    print("  Geometrias de estres (no deciden la politica general):")
    for comparison in stress:
        meets = evaluate_mvp_criteria(comparison)
        print(
            f"    {comparison.geometry_name}: "
            f"{'CUMPLE' if meets else 'NO cumple'} "
            f"(|gamma|={comparison.abs_gamma_anchor:.4f}, "
            f"|deltaZ|={comparison.absolute_error_ohm:.2f} ohm)"
        )

    if len(representative) < expected_representative_count:
        print(
            f"  lambda/{candidate_divisor}: sin datos suficientes en alguna "
            "geometria representativa."
        )
        return None

    passes = all(evaluate_mvp_criteria(c) for c in representative)
    print(
        f"  lambda/{candidate_divisor}, las 4 representativas "
        f"simultaneamente: {'CUMPLE' if passes else 'NO cumple'}"
    )
    return passes


def _print_uniform_density_selection(
    comparisons_by_candidate: dict[int, list[MvpCandidateComparison]],
    geometries: tuple[GeometrySpec, ...],
    repeatable: bool,
) -> int | None:
    print(
        "\n=== Seleccion de densidad uniforme fija minima "
        f"(orden: {', '.join(f'lambda/{d}' for d in MVP_SELECTION_ORDER)}) ==="
    )
    print(
        f"(|delta Z| <= {MVP_DELTA_Z_OHM} ohm [excepto estres con "
        f"|gamma| >= {STRESS_ABSOLUTE_ERROR_EXEMPTION_GAMMA}], "
        f"error relativo <= {MVP_RELATIVE_ERROR}, "
        f"abs(delta gamma) <= {MVP_DELTA_GAMMA}, resultados finitos y "
        f"repetibles; respecto de lambda/{MVP_PRACTICAL_ANCHOR_DIVISOR} "
        "como ancla practica, no como verdad general. Las geometrias de "
        "estres nunca deciden esta seleccion.)"
    )

    for candidate_divisor in MVP_CANDIDATE_DIVISORS:
        _print_mvp_candidate_summary(
            candidate_divisor, comparisons_by_candidate.get(candidate_divisor, []), geometries
        )

    selected_divisor, result_by_candidate = select_uniform_density(
        comparisons_by_candidate, geometries
    )

    if not repeatable:
        conclusion = (
            "INCONCLUSA: fallo la verificacion de repetibilidad en al "
            "menos un caso (candidato, lambda/320 o lambda/640)."
        )
        selected_divisor = None
    elif any(result_by_candidate.get(d) is None for d in MVP_SELECTION_ORDER):
        conclusion = (
            "INCONCLUSA: faltan datos validos en al menos una geometria "
            "representativa para lambda/160 o lambda/320."
        )
        selected_divisor = None
    elif selected_divisor is not None:
        conclusion = (
            f"lambda/{selected_divisor} ACEPTADA como densidad uniforme "
            "fija minima (cumple en las 4 geometrias representativas "
            "simultaneamente)."
        )
    else:
        conclusion = (
            "NINGUNA densidad uniforme fija de las evaluadas "
            f"({', '.join(f'lambda/{d}' for d in MVP_SELECTION_ORDER)}) "
            "cumple en las 4 geometrias representativas simultaneamente. "
            "No existe una densidad uniforme fija respaldada por este "
            "estudio; se recomienda una estrategia adaptativa."
        )

    print(f"\n  CONCLUSION: {conclusion}")
    return selected_divisor


# =============================================================================
# 7. Orquestacion
# =============================================================================


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=(
            "Directorio donde escribir los CSV. Por defecto, un "
            "directorio temporal nuevo fuera del repositorio."
        ),
    )
    arguments = parser.parse_args()

    output_dir = arguments.output_dir or Path(
        tempfile.mkdtemp(prefix="antsim-nec-segmentation-")
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    engine = PyNecEngine()
    geometries = build_geometries()

    all_wire_segments: list[WireSegmentInfo] = []
    all_cases: list[CaseResult] = []
    all_differences: list[SuccessiveDifference] = []
    comparisons_by_candidate: dict[int, list[MvpCandidateComparison]] = {
        divisor: [] for divisor in MVP_CANDIDATE_DIVISORS
    }
    convergence_by_geometry: dict[str, bool | None] = {}

    fed_wire_diagnosis_targets = {
        "[ESTRES] V invertida, seccion central corta (1.0 m)",
        "[ESTRES] V invertida, seccion central larga (5.0 m)",
    }

    for geometry in geometries:
        print(f"\n### Geometria: {geometry.name} ###")
        print(
            f"Frecuencia: {geometry.frequency_mhz} MHz | "
            f"lambda = {geometry.wavelength_m:.4f} m"
        )
        if geometry.notes:
            print(f"Notas: {geometry.notes}")

        cases_by_divisor: dict[int, CaseResult] = {}
        for divisor in DIVISORS:
            case = run_case(engine, geometry, divisor)
            cases_by_divisor[divisor] = case
            all_wire_segments.extend(case.wire_segments)

        for divisor in DIVISORS:
            _print_case(cases_by_divisor[divisor])
            all_cases.append(cases_by_divisor[divisor])

        differences = compute_successive_differences(cases_by_divisor)
        all_differences.extend(differences)

        print("\n  Diferencias sucesivas:")
        _print_successive_differences(differences)

        converged = classify_convergence(differences)
        convergence_by_geometry[geometry.name] = converged
        print(
            f"\n  Convergencia (segun los dos ultimos refinamientos, "
            f"{STABILITY_PAIRS}): "
            + (
                "sin datos suficientes" if converged is None
                else ("CONVERGE" if converged else "NO converge")
            )
        )

        if geometry.name in fed_wire_diagnosis_targets:
            _print_fed_wire_diagnosis(cases_by_divisor, geometry.fed_wire_tag)

        for candidate_divisor in MVP_CANDIDATE_DIVISORS:
            mvp_comparison = compute_mvp_candidate_comparison(
                geometry, cases_by_divisor, candidate_divisor
            )
            if mvp_comparison is not None:
                comparisons_by_candidate[candidate_divisor].append(mvp_comparison)
            _print_mvp_comparison(mvp_comparison, candidate_divisor)

    wire_csv_path = output_dir / "wire_segments.csv"
    cases_csv_path = output_dir / "cases.csv"
    differences_csv_path = output_dir / "successive_differences.csv"
    mvp_csv_path = output_dir / "mvp_candidate.csv"
    _write_dataclass_csv(wire_csv_path, all_wire_segments)
    _write_dataclass_csv(cases_csv_path, all_cases)
    _write_dataclass_csv(differences_csv_path, all_differences)
    _write_dataclass_csv(
        mvp_csv_path,
        [c for comparisons in comparisons_by_candidate.values() for c in comparisons],
    )

    print(f"\nCSV de detalle por conductor: {wire_csv_path}")
    print(f"CSV de resultados por nivel: {cases_csv_path}")
    print(f"CSV de diferencias sucesivas: {differences_csv_path}")
    print(f"CSV de candidato de MVP: {mvp_csv_path}")

    print("\n=== Resumen de convergencia por geometria (diferencias sucesivas) ===")
    for name, converged in convergence_by_geometry.items():
        status = (
            "sin datos suficientes" if converged is None
            else ("CONVERGE" if converged else "NO converge")
        )
        print(f"  {name}: {status}")

    repeatable = _check_repeatability(
        engine, geometries, divisors_to_check=(80, 160, 320, 640)
    )
    print(
        "\nRepetibilidad (candidatos lambda/80, lambda/160, lambda/320 y "
        "ancla practica lambda/640): "
        + ("OK en todas las geometrias." if repeatable else "FALLO en al menos un caso.")
    )

    non_finite = [case for case in all_cases if case.error is None and not case.is_finite]
    errored = [case for case in all_cases if case.error is not None]
    print(
        f"\nCasos con error de simulacion: {len(errored)}. "
        f"Casos con resultado no finito: {len(non_finite)}."
    )

    _print_uniform_density_selection(comparisons_by_candidate, geometries, repeatable)


if __name__ == "__main__":
    main()
