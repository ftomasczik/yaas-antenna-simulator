"""Caso de uso: convertir un documento MMANA-GAL compatible a un proyecto.

Este módulo depende únicamente de modelos y funciones ya públicas de
``yaas.domain``, ``yaas.projects`` y ``yaas.importers`` (parser
estructural y capa de compatibilidad de MMANA-GAL). No conoce
``argparse``, no importa PyNEC ni ``yaas.engines.pynec``, y no
invoca ninguna simulación: es una transformación pura de datos, para
poder reutilizarse desde la CLI y desde una futura interfaz gráfica.

La política de segmentación (``derive_nec_segments``) implementa
exactamente la densidad uniforme ``lambda/160`` aceptada en
``docs/decisions/0007-use-uniform-nec-segmentation.md``; no reproduce
el tapering de MMANA-GAL (ver
``docs/research/mmana-format-characterization.md`` y
``docs/research/nec-segmentation-convergence.md``).
"""

import math

from yaas.domain import Point3D, VoltageSource, Wire
from yaas.importers import (
    MmanaDocument,
    analyze_mmana_compatibility,
    interpret_environment,
    interpret_source,
)
from yaas.projects import AntennaProject, ProjectMetadata, SweepSettings

# Velocidad de la luz en el vacío, en m/s (valor exacto por definición).
SPEED_OF_LIGHT_M_PER_S = 299_792_458.0

# Densidad uniforme fija aceptada por el ADR 0007. Deliberadamente el
# único lugar donde este número aparece en código de producción; no se
# expone como parámetro de derive_nec_segments para que no pueda
# invocarse por accidente con una densidad distinta de la aceptada.
UNIFORM_SEGMENTATION_DIVISOR = 160


def derive_nec_segments(
    wire_length_m: float,
    frequency_mhz: float,
    *,
    requires_center_segment: bool,
) -> int:
    """Deriva la cantidad de segmentos NEC de un conductor recto.

    Implementa la política uniforme ``lambda/160`` del ADR 0007
    (``docs/decisions/0007-use-uniform-nec-segmentation.md``):

    - ``wavelength_m = SPEED_OF_LIGHT_M_PER_S / (frequency_mhz * 1e6)``
    - ``target_segment_length = wavelength_m / 160``
    - ``segments = ceil(wire_length_m / target_segment_length)``, con
      un piso de 1.
    - Si ``requires_center_segment`` es ``True`` y el resultado es
      par, se suma 1 (para garantizar un segmento central exacto para
      la fuente).

    Esta función **no** usa ``DM1``/``DM2``/``SC``/``EC`` del archivo
    MMANA-GAL original en ningún cálculo (ni siquiera los recibe como
    parámetro): esos campos describen una política de *tapering*
    (segmentos de longitud variable dentro de un mismo conductor) que
    esta función deliberadamente **no reproduce**. El resultado es
    siempre una cantidad única de segmentos de igual longitud para
    todo el conductor.

    Args:
        wire_length_m: Longitud del conductor, en metros. Debe ser
            finita y positiva.
        frequency_mhz: Frecuencia principal, en MHz. Debe ser finita y
            positiva.
        requires_center_segment: ``True`` si este es el conductor
            alimentado (exige una cantidad impar de segmentos).

    Returns:
        Cantidad de segmentos: un entero positivo, impar si
        ``requires_center_segment`` es ``True``.

    Raises:
        ValueError: Si ``wire_length_m`` o ``frequency_mhz`` no son
            finitos y positivos.
    """
    if not math.isfinite(wire_length_m) or wire_length_m <= 0:
        raise ValueError(
            "La longitud del conductor debe ser finita y positiva; "
            f"se encontró {wire_length_m!r}."
        )

    if not math.isfinite(frequency_mhz) or frequency_mhz <= 0:
        raise ValueError(
            "La frecuencia debe ser finita y positiva; se encontró "
            f"{frequency_mhz!r}."
        )

    wavelength_m = SPEED_OF_LIGHT_M_PER_S / (frequency_mhz * 1e6)
    target_segment_length_m = wavelength_m / UNIFORM_SEGMENTATION_DIVISOR
    segments = max(1, math.ceil(wire_length_m / target_segment_length_m))

    if requires_center_segment and segments % 2 == 0:
        segments += 1

    return segments


def convert_mmana_to_project(
    document: MmanaDocument,
    *,
    sweep: SweepSettings,
) -> AntennaProject:
    """Convierte un ``MmanaDocument`` compatible en un ``AntennaProject``.

    Flujo:

    1. Ejecuta ``analyze_mmana_compatibility(document)`` y llama a
       ``raise_if_incompatible()``: si el documento tiene algún error
       de compatibilidad, la excepción se propaga sin modificarse y
       **no se produce ningún ``AntennaProject`` parcial**. El resto
       de esta función confía en esa garantía y no repite esas
       validaciones (una única fuente centrada sin desplazamiento
       sobre un conductor existente; sin cargas; espacio libre con
       impedancia de referencia válida; todo conductor con
       ``segment_override = -1``; parámetros de segmentación
       válidos).
    2. Numera los conductores en el mismo orden que
       ``document.wires`` (1, 2, 3, …); esos números son los ``tag``
       de cada ``Wire`` resultante. Como la capa de compatibilidad ya
       exige que ``wire_ref`` sea ``wNc`` con ``N`` dentro de ese
       mismo rango posicional, el número de conductor de la fuente
       coincide exactamente con el ``tag`` que se le asigna aquí; no
       hace falta ninguna tabla de conversión aparte.
    3. Convierte coordenadas y radio directamente a metros (MMANA-GAL
       ya los expresa en metros; ver
       ``docs/research/mmana-format-characterization.md``).
    4. Deriva segmentos con ``derive_nec_segments`` (densidad
       ``lambda/160``, ADR 0007); solo el conductor alimentado exige
       cantidad impar.
    5. La fuente se ubica en el segmento central exacto del conductor
       alimentado: ``(segments + 1) // 2``.
    6. Convierte fase y amplitud a un voltaje complejo:
       ``voltage = amplitude * (cos(radians(phase)) + j*sin(radians(phase)))``.
    7. Usa la frecuencia principal y la impedancia de referencia
       confirmada del documento (campo ``R`` de
       ``G/H/M/R/AzEl/X``), y arma la metadata a partir del título y
       el comentario del documento.
    8. Usa ``sweep`` exactamente como se recibió; nunca se inventa ni
       se deriva un barrido a partir del documento MMANA-GAL.

    Decisión sobre ``additional_height_m`` (campo ``H``): se suma a la
    coordenada Z de **todos** los extremos de **todos** los
    conductores. Esto conserva la posición efectiva que describía el
    archivo original (una altura adicional sobre el nivel de
    referencia), en vez de tratar ``H`` como un campo oculto o
    descartarlo en silencio. Como el MVP de compatibilidad solo acepta
    entorno de espacio libre, esta traslación rígida de todas las
    coordenadas no cambia ningún resultado electromagnético (una
    simulación en espacio libre es invariante ante una traslación
    uniforme de toda la geometría).

    Explícitamente **no** soportado, ni degradado en silencio (la
    capa de compatibilidad ya lo convierte en un error, que se
    propaga sin modificarse): cargas concentradas, múltiples fuentes,
    entorno de tierra perfecta o real, fuentes en ``b``/``e`` o con
    desplazamiento, y ``segment_override`` distinto de ``-1``.

    Args:
        document: Documento MMANA-GAL ya analizado estructuralmente
            (``yaas.importers.load_mmana`` / ``parse_mmana``).
        sweep: Configuración de barrido a usar tal cual.

    Returns:
        El ``AntennaProject`` equivalente.

    Raises:
        MmanaCompatibilityError: Si el documento no es compatible.
            Ningún ``AntennaProject`` parcial se produce en ese caso.
    """
    analyze_mmana_compatibility(document).raise_if_incompatible()

    source_semantics = interpret_source(document.sources[0])
    fed_wire_number = source_semantics.wire_reference.wire_number

    environment_semantics = interpret_environment(document.environment)
    additional_height_m = environment_semantics.additional_height_m

    wires = tuple(
        Wire(
            tag=index,
            start=Point3D(
                mmana_wire.x1,
                mmana_wire.y1,
                mmana_wire.z1 + additional_height_m,
            ),
            end=Point3D(
                mmana_wire.x2,
                mmana_wire.y2,
                mmana_wire.z2 + additional_height_m,
            ),
            radius_m=mmana_wire.radius,
            segments=derive_nec_segments(
                math.dist(
                    (mmana_wire.x1, mmana_wire.y1, mmana_wire.z1),
                    (mmana_wire.x2, mmana_wire.y2, mmana_wire.z2),
                ),
                document.frequency_mhz,
                requires_center_segment=(index == fed_wire_number),
            ),
        )
        for index, mmana_wire in enumerate(document.wires, start=1)
    )

    fed_wire = wires[fed_wire_number - 1]

    phase_radians = math.radians(source_semantics.phase_degrees)
    voltage = source_semantics.voltage_volts * complex(
        math.cos(phase_radians), math.sin(phase_radians)
    )

    source = VoltageSource(
        wire_tag=fed_wire.tag,
        segment=(fed_wire.segments + 1) // 2,
        voltage=voltage,
    )

    metadata = ProjectMetadata(
        name=document.title,
        description=document.comment or "",
    )

    # No se envuelve ningun error de ProjectMetadata, SweepSettings ni
    # AntennaProject aqui a proposito: `sweep` es una entrada propia
    # de YAAS, no parte del documento MMANA-GAL, y ya se valido a si
    # misma al construirse. `title` ya se garantizo no vacio via
    # analyze_mmana_compatibility (error "title-empty"), asi que
    # ProjectMetadata tampoco deberia fallar aqui en la practica. Si
    # de todos modos algo fallara en esta construccion, el error debe
    # propagarse con su tipo real (ValueError de dominio), no
    # disfrazarse de MmanaCompatibilityError.
    return AntennaProject(
        metadata=metadata,
        wires=wires,
        source=source,
        frequency_mhz=document.frequency_mhz,
        reference_impedance=environment_semantics.reference_impedance_ohm,
        sweep=sweep,
    )
