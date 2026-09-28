"""Capa semántica y de compatibilidad para documentos MMANA-GAL (fase 6B.1).

Este módulo interpreta los campos del formato .maa que se confirmaron
experimentalmente (ver ``docs/research/mmana-format-characterization.md``),
y evalúa si un ``MmanaDocument`` ya analizado estructuralmente
(``yaas.importers.mmana``) podría convertirse hoy a un modelo de
YAAS, sin realizar esa conversión.

Separación deliberada del parser estructural (fase 6A):

- Este módulo no modifica ``yaas.importers.mmana``; solo lo consume.
- No convierte ningún resultado a ``AntennaProject`` ni a ningún otro
  modelo de ``yaas.domain``.
- No deriva segmentos NEC ni invoca ningún motor de simulación.
- No introduce dependencias hacia ``argparse``, ``gettext`` ni la CLI.
- No usa ``eval`` ni ``exec``: la referencia de conductor se reconoce
  con una expresión regular explícita, nunca evaluando texto.

El contrato de campos interpretado aquí proviene de experimentos
controlados y documentación externa, no únicamente del corpus
estructural de 26 archivos de la fase 6A; ver el documento de
caracterización para la procedencia de cada campo.
"""

import math
import re
from dataclasses import dataclass
from enum import Enum
from typing import Literal

from yaas.importers.errors import MmanaCompatibilityError
from yaas.importers.mmana import (
    MmanaDocument,
    MmanaEnvironment,
    MmanaLoad,
    MmanaSegmentation,
    MmanaSource,
)

# ---------------------------------------------------------------------------
# Referencia de conductor (wire_ref)
# ---------------------------------------------------------------------------

_WIRE_REFERENCE_PATTERN = re.compile(r"^w([1-9][0-9]*)([bce])(-?[0-9]+)?$")

_ANCHOR_NAMES: dict[str, Literal["begin", "center", "end"]] = {
    "b": "begin",
    "c": "center",
    "e": "end",
}


@dataclass(frozen=True)
class MmanaWireReference:
    """Referencia interpretada a una posición sobre un conductor.

    ``anchor`` es ``"begin"``, ``"center"`` o ``"end"`` (letras ``b``,
    ``c``, ``e`` del formato original). ``pulse_offset`` es el
    desplazamiento entero (en pulsos, positivo, negativo o cero)
    respecto de ese punto de anclaje.
    """

    wire_number: int
    anchor: Literal["begin", "center", "end"]
    pulse_offset: int

    @staticmethod
    def parse(raw: str) -> "MmanaWireReference":
        """Interpreta una referencia como ``w1b``, ``w3c1`` o ``w2c-2``.

        Rechaza sintaxis parcial, números de conductor no positivos
        (incluidos los que llevan ceros a la izquierda) y cualquier
        texto adicional al final.

        Raises:
            ValueError: Si ``raw`` no respeta la sintaxis esperada.
        """
        match = _WIRE_REFERENCE_PATTERN.match(raw)
        if match is None:
            raise ValueError(
                f"Referencia de conductor con sintaxis inválida: {raw!r}."
            )

        wire_number_text, anchor_letter, offset_text = match.groups()
        return MmanaWireReference(
            wire_number=int(wire_number_text),
            anchor=_ANCHOR_NAMES[anchor_letter],
            pulse_offset=int(offset_text) if offset_text is not None else 0,
        )


# ---------------------------------------------------------------------------
# Fuente
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MmanaSourceSemantics:
    """Fuente interpretada: ``wire_ref, phase_degrees, voltage_volts``."""

    wire_reference: MmanaWireReference
    phase_degrees: float
    voltage_volts: float


def interpret_source(source: MmanaSource) -> MmanaSourceSemantics:
    """Interpreta una fuente cruda según el contrato confirmado.

    Raises:
        ValueError: Si ``source.wire_ref`` no tiene sintaxis válida.
    """
    return MmanaSourceSemantics(
        wire_reference=MmanaWireReference.parse(source.wire_ref),
        phase_degrees=source.value1,
        voltage_volts=source.value2,
    )


# ---------------------------------------------------------------------------
# Cargas
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MmanaResistiveLoad:
    """Carga tipo 1: resistencia y reactancia concentradas (R+jX)."""

    wire_reference: MmanaWireReference
    resistance_ohm: float
    reactance_ohm: float


@dataclass(frozen=True)
class MmanaLcqLoad:
    """Carga tipo 0: inductancia, capacidad y factor de calidad (LCQ)."""

    wire_reference: MmanaWireReference
    inductance_uh: float
    capacitance_pf: float
    quality_factor: float


def interpret_load(load: MmanaLoad) -> MmanaResistiveLoad | MmanaLcqLoad:
    """Interpreta una carga cruda según el contrato confirmado.

    Raises:
        ValueError: Si ``load.wire_ref`` no tiene sintaxis válida, si
            ``load.load_type`` no es 0 ni 1, o si la cantidad de
            valores no corresponde a la esperada para ese tipo.
    """
    wire_reference = MmanaWireReference.parse(load.wire_ref)

    if load.load_type == 1:
        if len(load.values) != 2:
            raise ValueError(
                "Una carga tipo 1 (R+jX) debe tener exactamente 2 "
                f"valores; se encontraron {len(load.values)}."
            )
        resistance, reactance = load.values
        return MmanaResistiveLoad(
            wire_reference=wire_reference,
            resistance_ohm=resistance,
            reactance_ohm=reactance,
        )

    if load.load_type == 0:
        if len(load.values) != 3:
            raise ValueError(
                "Una carga tipo 0 (LCQ) debe tener exactamente 3 "
                f"valores; se encontraron {len(load.values)}."
            )
        inductance, capacitance, quality = load.values
        return MmanaLcqLoad(
            wire_reference=wire_reference,
            inductance_uh=inductance,
            capacitance_pf=capacitance,
            quality_factor=quality,
        )

    raise ValueError(f"Tipo de carga MMANA-GAL no reconocido: {load.load_type!r}.")


# ---------------------------------------------------------------------------
# Segmentación global (DM1, DM2, SC, EC)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MmanaSegmentationSemantics:
    """Política global de segmentación: ``DM1``, ``DM2``, ``SC``, ``EC``.

    Según la ayuda de MMANA-GAL: ``DM1`` controla el intervalo inicial
    o más fino del tapering; ``DM2`` controla el intervalo final o más
    grueso; ``SC`` es el multiplicador/parámetro de progresión que
    cambia gradualmente la longitud de los segmentos (normalmente
    ``1 < SC < 3``); ``EC`` indica cuántos segmentos del tamaño de
    ``DM1`` se colocan en el extremo donde comienza el tapering
    (normalmente ``1``, pero puede tomar otros valores).

    Esta fase **no** implementa el algoritmo de tapering: las fórmulas
    publicadas en la ayuda no son completamente consistentes entre la
    descripción general y sus propios ejemplos respecto de la
    posición exacta de los multiplicadores ``SC``/``EC`` (ver
    ``docs/research/mmana-format-characterization.md``). Los cuatro
    campos se conservan y se validan en sus dominios básicos, sin
    derivar ningún número de segmentos NEC a partir de ellos.
    """

    dm1: float
    dm2: float
    sc: float
    ec: float


def interpret_segmentation(
    segmentation: MmanaSegmentation,
) -> MmanaSegmentationSemantics:
    dm1, dm2, sc, ec = segmentation.values
    return MmanaSegmentationSemantics(dm1=dm1, dm2=dm2, sc=sc, ec=ec)


class MmanaSegmentOverrideKind(Enum):
    """Los cinco modos documentados de ``segment_override``.

    Los cinco están documentados (especificación aportada para esta
    fase); en el corpus real de 26 archivos y en los 20 experimentos
    controlados solo se observó ``-1`` (``TAPER_BOTH_ENDS``) en la
    práctica. Esa diferencia entre "documentado" y "observado" no
    afecta esta interpretación (los cinco se reconocen por igual),
    pero sí determina cuáles acepta el MVP de compatibilidad: ver
    ``docs/research/mmana-format-characterization.md`` y
    ``_check_wires`` (solo ``-1`` no genera un error).
    """

    MANUAL = "manual"
    AUTOMATIC = "automatic"
    TAPER_BOTH_ENDS = "taper_both_ends"
    TAPER_FROM_BEGIN = "taper_from_begin"
    TAPER_FROM_END = "taper_from_end"


_SEGMENT_OVERRIDE_KIND_BY_CODE: dict[int, MmanaSegmentOverrideKind] = {
    0: MmanaSegmentOverrideKind.AUTOMATIC,
    -1: MmanaSegmentOverrideKind.TAPER_BOTH_ENDS,
    -2: MmanaSegmentOverrideKind.TAPER_FROM_BEGIN,
    -3: MmanaSegmentOverrideKind.TAPER_FROM_END,
}


def interpret_segment_override(value: float) -> MmanaSegmentOverrideKind | None:
    """Interpreta ``MmanaWire.segment_override`` según los 5 modos documentados.

    Reconoce los cinco modos documentados (ver
    :class:`MmanaSegmentOverrideKind`) sin importar si fueron
    observados en la práctica o no. Devuelve ``None`` si el valor no
    es un entero conocido (por ejemplo, un valor fraccionario o un
    entero negativo menor que -3, que no forma parte del contrato
    documentado).
    """
    if not value.is_integer():
        return None

    value_int = int(value)
    if value_int > 0:
        return MmanaSegmentOverrideKind.MANUAL

    return _SEGMENT_OVERRIDE_KIND_BY_CODE.get(value_int)


# ---------------------------------------------------------------------------
# Entorno (G/H/M/R/AzEl/X)
# ---------------------------------------------------------------------------


class MmanaEnvironmentKind(Enum):
    """Interpretación confirmada experimentalmente del campo G."""

    FREE_SPACE = "free_space"
    PERFECT_GROUND = "perfect_ground"
    REAL_GROUND = "real_ground"


_ENVIRONMENT_KIND_BY_CODE: dict[int, MmanaEnvironmentKind] = {
    0: MmanaEnvironmentKind.FREE_SPACE,
    1: MmanaEnvironmentKind.PERFECT_GROUND,
    2: MmanaEnvironmentKind.REAL_GROUND,
}


@dataclass(frozen=True)
class MmanaEnvironmentSemantics:
    """Entorno interpretado.

    Campos con significado confirmado: ``G`` (entorno, ``kind``/
    ``kind_code``), ``H`` (``additional_height_m``, altura adicional
    sobre el nivel de referencia en metros, según la ayuda de
    MMANA-GAL) y ``R`` (impedancia de referencia). Los cuatro campos
    restantes (``M``, ``Az``, ``El``, ``X``) se conservan en
    ``unconfirmed_fields``, en ese orden. ``Az``/``El`` ya se
    consultan posicionalmente para detectar un patrón puntual que
    YAAS no conservaría (ver ``_check_environment``), pero eso no
    les asigna todavía un nombre físico propio; ``M`` y ``X``
    permanecen completamente opacos, sin ningún uso.
    """

    kind_code: float
    kind: MmanaEnvironmentKind | None
    additional_height_m: float
    reference_impedance_ohm: float
    unconfirmed_fields: tuple[float, float, float, float]


def interpret_environment(environment: MmanaEnvironment) -> MmanaEnvironmentSemantics:
    ground, height, medium, reference, azimuth, elevation, extra = (
        environment.values
    )
    kind = None
    if ground.is_integer():
        kind = _ENVIRONMENT_KIND_BY_CODE.get(int(ground))

    return MmanaEnvironmentSemantics(
        kind_code=ground,
        kind=kind,
        additional_height_m=height,
        reference_impedance_ohm=reference,
        unconfirmed_fields=(medium, azimuth, elevation, extra),
    )


# ---------------------------------------------------------------------------
# Diagnóstico de compatibilidad
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MmanaCompatibilityIssue:
    """Un problema de compatibilidad, con código estable no traducido.

    ``code`` está pensado para que la CLI o una futura GUI lo traduzcan
    o presenten; nunca debe cambiar entre versiones sin ser tratado
    como una ruptura de compatibilidad. ``message`` es una explicación
    técnica en español, no destinada a mostrarse tal cual a un usuario
    final. ``location`` identifica el campo relacionado cuando es
    posible (por ejemplo ``"wires[2].radius"``).
    """

    severity: Literal["error", "warning"]
    code: str
    message: str
    location: str | None = None


@dataclass(frozen=True)
class MmanaCompatibilityReport:
    """Resultado de :func:`analyze_mmana_compatibility`."""

    issues: tuple[MmanaCompatibilityIssue, ...]

    @property
    def errors(self) -> tuple[MmanaCompatibilityIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "error")

    @property
    def warnings(self) -> tuple[MmanaCompatibilityIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "warning")

    @property
    def is_compatible(self) -> bool:
        """``True`` si no hay errores (las advertencias no bloquean)."""
        return not self.errors

    def raise_if_incompatible(self) -> None:
        """Lanza :class:`MmanaCompatibilityError` si hay algún error.

        Raises:
            MmanaCompatibilityError: Con ``issues`` conteniendo los
                errores encontrados.
        """
        errors = self.errors
        if not errors:
            return

        summary = "; ".join(f"[{issue.code}] {issue.message}" for issue in errors)
        raise MmanaCompatibilityError(summary, issues=errors)


# Encabezados decorativos observados en archivos reales (fase 6A) y en
# los experimentos controlados de esta fase; cualquier otro valor se
# reporta como advertencia, no como error, porque el contenido
# decorativo nunca se usa para reconocer la sección (ver yaas.importers.mmana).
_CANONICAL_HEADERS: dict[str, frozenset[str]] = {
    "wires_header": frozenset({"***Wires***"}),
    "source_header": frozenset({"*** Source ***", "***Source***"}),
    "load_header": frozenset(
        {"*** Load ***", "***Load***", "***   Load   ***"}
    ),
    "segmentation_header": frozenset(
        {"*** Segmentation ***", "***Segmentation***", "**Segmentation**"}
    ),
    "environment_header": frozenset(
        {
            "*** G/H/M/R/AzEl/X ***",
            "***G/H/M/R/AzEl/X***",
            "*G/H/M/R/AzEl/X*",
            "*GH/??/R/AzEl/X*",
        }
    ),
}
_CANONICAL_COMMENT_HEADERS = frozenset({"### Comment ###", "###Comment###"})


def _check_frequency(
    document: MmanaDocument, issues: list[MmanaCompatibilityIssue]
) -> None:
    if not math.isfinite(document.frequency_mhz) or document.frequency_mhz <= 0:
        issues.append(
            MmanaCompatibilityIssue(
                severity="error",
                code="frequency-invalid",
                message=(
                    "La frecuencia principal debe ser finita y positiva; "
                    f"se encontró {document.frequency_mhz!r}."
                ),
                location="frequency_mhz",
            )
        )


def _check_wires(
    document: MmanaDocument, issues: list[MmanaCompatibilityIssue]
) -> None:
    for index, wire in enumerate(document.wires, start=1):
        location = f"wires[{index}]"

        if not math.isfinite(wire.radius) or wire.radius <= 0:
            issues.append(
                MmanaCompatibilityIssue(
                    severity="error",
                    code="wire-radius-invalid",
                    message=(
                        f"El conductor {index} tiene un radio inválido "
                        f"({wire.radius!r}); debe ser finito y positivo."
                    ),
                    location=f"{location}.radius",
                )
            )

        start = (wire.x1, wire.y1, wire.z1)
        end = (wire.x2, wire.y2, wire.z2)
        if not all(math.isfinite(value) for value in (*start, *end)):
            issues.append(
                MmanaCompatibilityIssue(
                    severity="error",
                    code="wire-geometry-invalid",
                    message=f"El conductor {index} tiene coordenadas no finitas.",
                    location=location,
                )
            )
        elif start == end:
            issues.append(
                MmanaCompatibilityIssue(
                    severity="error",
                    code="wire-geometry-invalid",
                    message=(
                        f"El conductor {index} tiene longitud cero "
                        "(el inicio y el final coinciden)."
                    ),
                    location=location,
                )
            )

        override_kind = interpret_segment_override(wire.segment_override)
        if override_kind is not MmanaSegmentOverrideKind.TAPER_BOTH_ENDS:
            issues.append(
                MmanaCompatibilityIssue(
                    severity="error",
                    code="wire-segment-override-unsupported",
                    message=(
                        f"El conductor {index} usa segment_override="
                        f"{wire.segment_override!r}; por ahora solo se "
                        "admite -1 (tapering en ambos extremos)."
                    ),
                    location=f"{location}.segment_override",
                )
            )
        else:
            issues.append(
                MmanaCompatibilityIssue(
                    severity="warning",
                    code="segmentation-taper-not-reproducible",
                    message=(
                        f"El conductor {index} usa tapering de MMANA-GAL "
                        "(segment_override=-1); el modelo Wire.segments "
                        "actual de YAAS (un entero uniforme por "
                        "conductor) no puede reproducirlo exactamente."
                    ),
                    location=f"{location}.segment_override",
                )
            )


def _check_sources(
    document: MmanaDocument, issues: list[MmanaCompatibilityIssue]
) -> None:
    wire_count = len(document.wires)

    if len(document.sources) != 1:
        issues.append(
            MmanaCompatibilityIssue(
                severity="error",
                code="source-count-invalid",
                message=(
                    "Se requiere exactamente una fuente; se encontraron "
                    f"{len(document.sources)}."
                ),
                location="sources",
            )
        )

    for index, source in enumerate(document.sources, start=1):
        location = f"sources[{index}]"

        try:
            semantics = interpret_source(source)
        except ValueError as error:
            issues.append(
                MmanaCompatibilityIssue(
                    severity="error",
                    code="wire-reference-syntax-invalid",
                    message=str(error),
                    location=location,
                )
            )
            continue

        # Finitud de fase/amplitud: se verifica siempre, independiente
        # de si la posición de la fuente es válida, porque son
        # problemas distintos. No se limita phase_degrees a ningún
        # rango (por ejemplo 0..360): cualquier valor finito es
        # aceptado, ya que la conversión trigonométrica
        # (cos/sin de radians(phase_degrees)) ya admite ángulos
        # equivalentes fuera de ese rango sin ambigüedad.
        phase_is_finite = math.isfinite(semantics.phase_degrees)
        if not phase_is_finite:
            issues.append(
                MmanaCompatibilityIssue(
                    severity="error",
                    code="source-phase-invalid",
                    message=(
                        f"La fuente {index} tiene una fase no finita: "
                        f"{semantics.phase_degrees!r}."
                    ),
                    location=location,
                )
            )

        if not math.isfinite(semantics.voltage_volts):
            issues.append(
                MmanaCompatibilityIssue(
                    severity="error",
                    code="source-voltage-invalid",
                    message=(
                        f"La fuente {index} tiene una amplitud no finita: "
                        f"{semantics.voltage_volts!r}."
                    ),
                    location=location,
                )
            )
        elif semantics.voltage_volts == 0:
            # Decisión de alcance del MVP, no una propiedad de
            # MMANA-GAL: una amplitud cero es una fuente sintácticamente
            # válida pero no representa ninguna excitación útil para
            # simular (Z sería indeterminada). Se rechaza explícitamente
            # en vez de dejar que una futura conversión produzca un
            # AntennaProject con una fuente inerte.
            issues.append(
                MmanaCompatibilityIssue(
                    severity="error",
                    code="source-voltage-invalid",
                    message=(
                        f"La fuente {index} tiene amplitud cero; una "
                        "excitación nula no representa una simulación "
                        "útil (restricción de alcance del MVP, no una "
                        "propiedad de MMANA-GAL)."
                    ),
                    location=location,
                )
            )

        reference = semantics.wire_reference
        if not (1 <= reference.wire_number <= wire_count):
            issues.append(
                MmanaCompatibilityIssue(
                    severity="error",
                    code="wire-reference-unknown",
                    message=(
                        f"La fuente {index} referencia el conductor "
                        f"{reference.wire_number}, que no existe (el "
                        f"documento declara {wire_count})."
                    ),
                    location=location,
                )
            )
            continue

        is_centered_without_offset = (
            reference.anchor == "center" and reference.pulse_offset == 0
        )
        if not is_centered_without_offset:
            issues.append(
                MmanaCompatibilityIssue(
                    severity="error",
                    code="source-not-centered",
                    message=(
                        f"La fuente {index} debe referenciar el centro "
                        "del conductor sin desplazamiento (wNc); se "
                        f"encontró {source.wire_ref!r}."
                    ),
                    location=location,
                )
            )
        elif phase_is_finite and semantics.phase_degrees != 0:
            issues.append(
                MmanaCompatibilityIssue(
                    severity="warning",
                    code="source-phase-nonzero",
                    message=(
                        f"La fuente {index} tiene fase "
                        f"{semantics.phase_degrees!r} grados distinta de "
                        "cero."
                    ),
                    location=location,
                )
            )


def _check_loads(
    document: MmanaDocument, issues: list[MmanaCompatibilityIssue]
) -> None:
    wire_count = len(document.wires)

    if document.loads:
        wire_refs = ", ".join(load.wire_ref for load in document.loads)
        issues.append(
            MmanaCompatibilityIssue(
                severity="error",
                code="loads-present",
                message=(
                    f"El documento declara {len(document.loads)} carga(s) "
                    f"({wire_refs}); YAAS todavía no admite cargas "
                    "concentradas."
                ),
                location="loads",
            )
        )

    for index, load in enumerate(document.loads, start=1):
        location = f"loads[{index}]"
        try:
            reference = MmanaWireReference.parse(load.wire_ref)
        except ValueError as error:
            issues.append(
                MmanaCompatibilityIssue(
                    severity="error",
                    code="wire-reference-syntax-invalid",
                    message=str(error),
                    location=location,
                )
            )
            continue

        if not (1 <= reference.wire_number <= wire_count):
            issues.append(
                MmanaCompatibilityIssue(
                    severity="error",
                    code="wire-reference-unknown",
                    message=(
                        f"La carga {index} referencia el conductor "
                        f"{reference.wire_number}, que no existe (el "
                        f"documento declara {wire_count})."
                    ),
                    location=location,
                )
            )


def _check_environment(
    document: MmanaDocument, issues: list[MmanaCompatibilityIssue]
) -> None:
    semantics = interpret_environment(document.environment)

    if semantics.kind is not MmanaEnvironmentKind.FREE_SPACE:
        kind_description = (
            semantics.kind.value if semantics.kind is not None else "desconocido"
        )
        issues.append(
            MmanaCompatibilityIssue(
                severity="error",
                code="environment-not-free-space",
                message=(
                    "YAAS solo simula en espacio libre; el documento "
                    f"declara un entorno G={semantics.kind_code!r} "
                    f"({kind_description})."
                ),
                location="environment.values[0]",
            )
        )

    reference_impedance = semantics.reference_impedance_ohm
    if not math.isfinite(reference_impedance) or reference_impedance <= 0:
        issues.append(
            MmanaCompatibilityIssue(
                severity="error",
                code="reference-impedance-invalid",
                message=(
                    "La impedancia de referencia debe ser finita y "
                    f"positiva; se encontró {reference_impedance!r}."
                ),
                location="environment.values[3]",
            )
        )

    if not math.isfinite(semantics.additional_height_m):
        issues.append(
            MmanaCompatibilityIssue(
                severity="error",
                code="environment-height-invalid",
                message=(
                    "La altura adicional (H) debe ser finita; se "
                    f"encontró {semantics.additional_height_m!r}."
                ),
                location="environment.values[1]",
            )
        )

    _medium, azimuth, elevation, _extra = semantics.unconfirmed_fields
    if azimuth != 0 or elevation != 0:
        issues.append(
            MmanaCompatibilityIssue(
                severity="warning",
                code="environment-azel-not-preserved",
                message=(
                    f"Los parámetros de patrón puntual Az={azimuth!r}/"
                    f"El={elevation!r} no se conservarán; YAAS no "
                    "calcula diagramas de radiación todavía."
                ),
                location="environment.values[4:6]",
            )
        )


def _check_segmentation(
    document: MmanaDocument, issues: list[MmanaCompatibilityIssue]
) -> None:
    """Valida solo los dominios básicos documentados de DM1/DM2/SC/EC.

    No valida relaciones entre campos (por ejemplo, DM1 frente a DM2):
    ninguna está respaldada por la ayuda de MMANA-GAL ni por una
    decisión explícita del proyecto (ver
    ``docs/research/mmana-format-characterization.md``).
    """
    semantics = interpret_segmentation(document.segmentation)

    if semantics.dm1 <= 0:
        issues.append(
            MmanaCompatibilityIssue(
                severity="error",
                code="segmentation-invalid",
                message=(
                    "DM1 debe ser positivo según la ayuda de MMANA-GAL; "
                    f"se encontró {semantics.dm1!r}."
                ),
                location="segmentation.dm1",
            )
        )

    if semantics.dm2 <= 0:
        issues.append(
            MmanaCompatibilityIssue(
                severity="error",
                code="segmentation-invalid",
                message=(
                    "DM2 debe ser positivo según la ayuda de MMANA-GAL; "
                    f"se encontró {semantics.dm2!r}."
                ),
                location="segmentation.dm2",
            )
        )

    if not (1 < semantics.sc < 3):
        issues.append(
            MmanaCompatibilityIssue(
                severity="error",
                code="segmentation-invalid",
                message=(
                    "SC debe cumplir 1 < SC < 3 según la ayuda de "
                    f"MMANA-GAL; se encontró {semantics.sc!r}."
                ),
                location="segmentation.sc",
            )
        )

    if not semantics.ec.is_integer() or semantics.ec <= 0:
        issues.append(
            MmanaCompatibilityIssue(
                severity="error",
                code="segmentation-invalid",
                message=(
                    "EC debe ser un entero positivo según la ayuda de "
                    f"MMANA-GAL; se encontró {semantics.ec!r}."
                ),
                location="segmentation.ec",
            )
        )


def _check_title_and_comment(
    document: MmanaDocument, issues: list[MmanaCompatibilityIssue]
) -> None:
    # Un título vacío es un ERROR (no una advertencia): AntennaProject
    # exige un ProjectMetadata.name no vacío, y esta capa no inventa un
    # título sustituto. Si esto fuera solo una advertencia,
    # convert_mmana_to_project podría fallar con un ValueError de
    # ProjectMetadata en vez de un MmanaCompatibilityError, ocultando
    # la causa real detrás de un tipo de excepción equivocado.
    if not document.title.strip():
        issues.append(
            MmanaCompatibilityIssue(
                severity="error",
                code="title-empty",
                message=(
                    "El título del documento está vacío o contiene "
                    "solo espacios; YAAS no inventa un título "
                    "sustituto."
                ),
                location="title",
            )
        )

    if document.comment is not None and not document.comment.strip():
        issues.append(
            MmanaCompatibilityIssue(
                severity="warning",
                code="comment-empty",
                message="La sección de comentario está presente pero vacía.",
                location="comment",
            )
        )


def _check_section_headers(
    document: MmanaDocument, issues: list[MmanaCompatibilityIssue]
) -> None:
    for attribute, canonical_values in _CANONICAL_HEADERS.items():
        actual = getattr(document, attribute)
        if actual not in canonical_values:
            issues.append(
                MmanaCompatibilityIssue(
                    severity="warning",
                    code="section-header-noncanonical",
                    message=(
                        f"El encabezado de {attribute} no coincide con "
                        f"ninguna variante conocida; se encontró {actual!r}."
                    ),
                    location=attribute,
                )
            )

    if (
        document.comment_header is not None
        and document.comment_header not in _CANONICAL_COMMENT_HEADERS
    ):
        issues.append(
            MmanaCompatibilityIssue(
                severity="warning",
                code="section-header-noncanonical",
                message=(
                    "El encabezado de comment_header no coincide con "
                    "ninguna variante conocida; se encontró "
                    f"{document.comment_header!r}."
                ),
                location="comment_header",
            )
        )


def analyze_mmana_compatibility(document: MmanaDocument) -> MmanaCompatibilityReport:
    """Evalúa si ``document`` podría convertirse hoy a un modelo de YAAS.

    No realiza ninguna conversión; solo diagnostica. Ver el módulo para
    el contrato de campos interpretado y
    ``docs/research/mmana-format-characterization.md`` para su
    procedencia.
    """
    issues: list[MmanaCompatibilityIssue] = []

    _check_frequency(document, issues)
    _check_wires(document, issues)
    _check_sources(document, issues)
    _check_loads(document, issues)
    _check_environment(document, issues)
    _check_segmentation(document, issues)
    _check_title_and_comment(document, issues)
    _check_section_headers(document, issues)

    return MmanaCompatibilityReport(issues=tuple(issues))
