"""Lectura estructural del formato de proyecto MMANA-GAL (.maa).

Alcance de esta fase (6A — lectura estructural):

- Este módulo solo reconoce la gramática posicional del archivo y
  valida su forma (marcador literal, contadores de sección, cantidad
  de campos numéricos, valores numéricos finitos).
- No convierte el resultado a ``AntennaProject`` ni a ningún modelo de
  ``yaas.domain``.
- No deriva segmentos NEC ni ninguna otra decisión de simulación a
  partir de los campos leídos.
- No interpreta el significado de la referencia de conductor
  (``wire_ref``, por ejemplo ``w4b`` o ``w1e2``): se conserva tal cual
  aparece en el archivo.
- Los campos cuyo significado físico no está confirmado (el marcador
  de la segunda línea, el indicador de fuentes/cargas, los valores de
  carga tipo 0, la fila de segmentación y la fila de entorno/patrón)
  se conservan sin interpretar en los modelos, en vez de descartarse.

El orden de las secciones es fijo y se reconoce por posición, no por el
texto decorativo de cada encabezado: MMANA-GAL localiza esos textos
(por ejemplo, en ruso vía CP1251), así que un análisis basado en
coincidencia literal de encabezados no sería robusto entre archivos.
"""

import math
from dataclasses import dataclass
from pathlib import Path

from yaas.importers.errors import MmanaFormatError

_MARKER_LINE = "*"
_UTF8_BOM = b"\xef\xbb\xbf"

# Bytes que CP1252 deja indefinidos pero que CP1251 sí asigna a un
# carácter (letras cirílicas extendidas usadas en macedonio/serbio).
# Verificado empíricamente contra ambas tablas de codificación.
_CP1252_UNDEFINED_BYTES = frozenset({0x81, 0x8D, 0x8F, 0x90, 0x9D})


@dataclass(frozen=True)
class MmanaWire:
    """Fila cruda de la sección de conductores.

    ``segment_override`` fue siempre ``-1`` en el corpus estructural
    original (fase 6A); su significado se confirmó experimentalmente
    en una fase posterior (ver
    ``yaas.importers.mmana_compatibility.interpret_segment_override``).
    Este módulo no deriva ningún segmento a partir de él.
    """

    x1: float
    y1: float
    z1: float
    x2: float
    y2: float
    z2: float
    radius: float
    segment_override: float


@dataclass(frozen=True)
class MmanaSource:
    """Fila cruda de la sección de fuentes.

    ``wire_ref`` se conserva tal cual (no se interpreta su sufijo de
    posición). ``value1``/``value2`` se conservan sin asumir si
    representan fase/amplitud u otra convención.
    """

    wire_ref: str
    value1: float
    value2: float


@dataclass(frozen=True)
class MmanaLoad:
    """Fila cruda de la sección de cargas.

    ``load_type`` selecciona la forma del registro (se observaron
    exactamente dos formas en el corpus real: tipo 1 con 2 valores
    adicionales, tipo 0 con 3), pero el significado físico de
    ``values`` no está confirmado y se conserva sin interpretar.
    """

    wire_ref: str
    load_type: int
    values: tuple[float, ...]


@dataclass(frozen=True)
class MmanaSegmentation:
    """Fila cruda de la política global de auto-segmentación (4 campos).

    Ninguno de los 4 campos se nombra ni se interpreta: su semántica
    exacta no está confirmada por documentación oficial.
    """

    values: tuple[float, float, float, float]


@dataclass(frozen=True)
class MmanaEnvironment:
    """Fila cruda de la línea de entorno/patrón ``G/H/M/R/AzEl/X`` (7 campos).

    Se conserva sin interpretar; en particular no se asume qué campo es
    la impedancia de referencia ni el tipo de suelo.
    """

    values: tuple[float, float, float, float, float, float, float]


@dataclass(frozen=True)
class MmanaDocument:
    """Resultado completo del análisis estructural de un archivo .maa.

    Los campos ``*_header`` conservan el texto decorativo original de
    cada encabezado de sección (varía por idioma de la interfaz de
    MMANA-GAL) para diagnóstico, sin que su contenido se valide ni se
    use para reconocer la sección.
    """

    title: str
    marker: str
    frequency_mhz: float
    wires_header: str
    wires: tuple[MmanaWire, ...]
    source_header: str
    source_flag: int
    sources: tuple[MmanaSource, ...]
    load_header: str
    load_flag: int
    loads: tuple[MmanaLoad, ...]
    segmentation_header: str
    segmentation: MmanaSegmentation
    environment_header: str
    environment: MmanaEnvironment
    comment_header: str | None
    comment: str | None
    encoding: str
    line_terminator: str


class _LineReader:
    """Cursor secuencial sobre las líneas ya divididas del archivo."""

    def __init__(self, lines: list[str], path: Path | None) -> None:
        self._lines = lines
        self._path = path
        self._index = 0

    @property
    def has_more(self) -> bool:
        return self._index < len(self._lines)

    def next_line(self, context: str) -> tuple[str, int]:
        """Devuelve (texto, número de línea 1-based) de la siguiente línea."""
        if not self.has_more:
            raise MmanaFormatError(
                f"El archivo terminó antes de encontrar {context}.",
                path=self._path,
                line_number=self._index + 1,
            )
        line = self._lines[self._index]
        self._index += 1
        return line, self._index

    def remaining(self) -> list[str]:
        rest = self._lines[self._index:]
        self._index = len(self._lines)
        return rest


def _parse_float(
    raw: str,
    *,
    path: Path | None,
    line_number: int,
    field: str,
) -> float:
    stripped = raw.strip()
    try:
        value = float(stripped)
    except ValueError as error:
        raise MmanaFormatError(
            f"{field}: valor numérico inválido: {raw!r}.",
            path=path,
            line_number=line_number,
        ) from error

    if not math.isfinite(value):
        raise MmanaFormatError(
            f"{field}: se esperaba un número finito y se encontró {raw!r}.",
            path=path,
            line_number=line_number,
        )

    return value


def _parse_count(
    raw: str,
    *,
    path: Path | None,
    line_number: int,
    context: str,
) -> int:
    stripped = raw.strip()
    try:
        value = int(stripped)
    except ValueError as error:
        raise MmanaFormatError(
            f"{context}: se esperaba un entero y se encontró {raw!r}.",
            path=path,
            line_number=line_number,
        ) from error

    if value < 0:
        raise MmanaFormatError(
            f"{context}: el contador no puede ser negativo ({value}).",
            path=path,
            line_number=line_number,
        )

    return value


def _split_exact(
    raw: str,
    expected: int,
    *,
    path: Path | None,
    line_number: int,
    context: str,
) -> list[str]:
    fields = [field.strip() for field in raw.split(",")]
    if len(fields) != expected:
        raise MmanaFormatError(
            f"{context}: se esperaban {expected} campos separados por "
            f"coma y se encontraron {len(fields)}.",
            path=path,
            line_number=line_number,
        )
    return fields


def _split_at_least(
    raw: str,
    minimum: int,
    *,
    path: Path | None,
    line_number: int,
    context: str,
) -> list[str]:
    fields = [field.strip() for field in raw.split(",")]
    if len(fields) < minimum:
        raise MmanaFormatError(
            f"{context}: se esperaban al menos {minimum} campos separados "
            f"por coma y se encontraron {len(fields)}.",
            path=path,
            line_number=line_number,
        )
    return fields


def _parse_count_and_flag(
    raw: str,
    *,
    path: Path | None,
    line_number: int,
    context: str,
) -> tuple[int, int]:
    fields = _split_exact(
        raw, 2, path=path, line_number=line_number, context=context
    )
    count = _parse_count(
        fields[0], path=path, line_number=line_number, context=f"{context} (conteo)"
    )
    flag = _parse_count(
        fields[1],
        path=path,
        line_number=line_number,
        context=f"{context} (indicador)",
    )
    return count, flag


def _read_wires(
    reader: _LineReader, path: Path | None
) -> tuple[str, tuple[MmanaWire, ...]]:
    header, _ = reader.next_line("el encabezado de conductores")
    count_raw, count_line = reader.next_line("el contador de conductores")
    count = _parse_count(
        count_raw,
        path=path,
        line_number=count_line,
        context="el contador de conductores",
    )

    wires = []
    for index in range(count):
        row_raw, row_line = reader.next_line(f"la fila de conductor #{index + 1}")
        fields = _split_exact(
            row_raw, 8, path=path, line_number=row_line, context="fila de conductor"
        )
        numbers = [
            _parse_float(
                raw_value,
                path=path,
                line_number=row_line,
                field=f"conductor, campo {position + 1}",
            )
            for position, raw_value in enumerate(fields)
        ]
        wires.append(MmanaWire(*numbers))

    return header, tuple(wires)


def _read_source(
    reader: _LineReader, path: Path | None
) -> tuple[str, int, tuple[MmanaSource, ...]]:
    header, _ = reader.next_line("el encabezado de fuentes")
    header_raw, header_line = reader.next_line("el contador de fuentes")
    count, flag = _parse_count_and_flag(
        header_raw,
        path=path,
        line_number=header_line,
        context="el contador de fuentes",
    )

    sources = []
    for index in range(count):
        row_raw, row_line = reader.next_line(f"la fila de fuente #{index + 1}")
        fields = _split_exact(
            row_raw, 3, path=path, line_number=row_line, context="fila de fuente"
        )
        wire_ref = fields[0]
        if not wire_ref:
            raise MmanaFormatError(
                "fila de fuente: la referencia de conductor está vacía.",
                path=path,
                line_number=row_line,
            )
        value1 = _parse_float(
            fields[1], path=path, line_number=row_line, field="fuente, valor 1"
        )
        value2 = _parse_float(
            fields[2], path=path, line_number=row_line, field="fuente, valor 2"
        )
        sources.append(MmanaSource(wire_ref=wire_ref, value1=value1, value2=value2))

    return header, flag, tuple(sources)


def _read_loads(
    reader: _LineReader, path: Path | None
) -> tuple[str, int, tuple[MmanaLoad, ...]]:
    header, _ = reader.next_line("el encabezado de cargas")
    header_raw, header_line = reader.next_line("el contador de cargas")
    count, flag = _parse_count_and_flag(
        header_raw,
        path=path,
        line_number=header_line,
        context="el contador de cargas",
    )

    loads = []
    for index in range(count):
        row_raw, row_line = reader.next_line(f"la fila de carga #{index + 1}")
        fields = _split_at_least(
            row_raw, 2, path=path, line_number=row_line, context="fila de carga"
        )
        wire_ref = fields[0]
        if not wire_ref:
            raise MmanaFormatError(
                "fila de carga: la referencia de conductor está vacía.",
                path=path,
                line_number=row_line,
            )

        load_type_value = _parse_float(
            fields[1], path=path, line_number=row_line, field="carga, tipo"
        )
        if not load_type_value.is_integer():
            raise MmanaFormatError(
                "fila de carga: el tipo de carga debe ser entero, se "
                f"encontró {fields[1]!r}.",
                path=path,
                line_number=row_line,
            )

        values = tuple(
            _parse_float(
                raw_value,
                path=path,
                line_number=row_line,
                field=f"carga, valor {position + 1}",
            )
            for position, raw_value in enumerate(fields[2:])
        )
        loads.append(
            MmanaLoad(
                wire_ref=wire_ref,
                load_type=int(load_type_value),
                values=values,
            )
        )

    return header, flag, tuple(loads)


def _read_segmentation(
    reader: _LineReader, path: Path | None
) -> tuple[str, MmanaSegmentation]:
    header, _ = reader.next_line("el encabezado de segmentación")
    row_raw, row_line = reader.next_line("la fila de segmentación")
    fields = _split_exact(
        row_raw, 4, path=path, line_number=row_line, context="fila de segmentación"
    )
    values = tuple(
        _parse_float(
            raw_value,
            path=path,
            line_number=row_line,
            field=f"segmentación, campo {position + 1}",
        )
        for position, raw_value in enumerate(fields)
    )
    return header, MmanaSegmentation(values=values)


def _read_environment(
    reader: _LineReader, path: Path | None
) -> tuple[str, MmanaEnvironment]:
    header, _ = reader.next_line("el encabezado de entorno/patrón")
    row_raw, row_line = reader.next_line("la fila de entorno/patrón")
    fields = _split_exact(
        row_raw,
        7,
        path=path,
        line_number=row_line,
        context="fila de entorno/patrón",
    )
    values = tuple(
        _parse_float(
            raw_value,
            path=path,
            line_number=row_line,
            field=f"entorno, campo {position + 1}",
        )
        for position, raw_value in enumerate(fields)
    )
    return header, MmanaEnvironment(values=values)


def _read_comment(reader: _LineReader) -> tuple[str | None, str | None]:
    if not reader.has_more:
        return None, None
    header, _ = reader.next_line("el encabezado de comentario")
    comment = "\n".join(reader.remaining())
    return header, comment


def parse_mmana(
    text: str,
    *,
    encoding: str = "utf-8",
    line_terminator: str = "\r\n",
    path: str | Path | None = None,
) -> MmanaDocument:
    """Analiza estructuralmente el contenido ya decodificado de un .maa.

    No valida el contenido decorativo de los encabezados de sección
    (varía según el idioma de la interfaz de MMANA-GAL); reconoce las
    secciones exclusivamente por su posición fija. Valida el marcador
    literal de la segunda línea y todos los contadores de sección.

    Args:
        text: Contenido ya decodificado del archivo.
        encoding: Nombre de la codificación usada para decodificar
            ``text``, conservado solo como metadato de diagnóstico.
        line_terminator: Separador de línea original detectado en el
            archivo (``"\\r\\n"`` o ``"\\n"``), conservado solo como
            metadato de diagnóstico o para una futura exportación.
        path: Ruta de origen, usada únicamente para enriquecer los
            mensajes de error.

    Raises:
        MmanaFormatError: Si el archivo no respeta la gramática
            estructural esperada.
    """
    resolved_path = Path(path) if path is not None else None
    lines = text.splitlines()
    reader = _LineReader(lines, resolved_path)

    title, _ = reader.next_line("el título")

    marker, marker_line = reader.next_line("el marcador de la segunda línea")
    if marker != _MARKER_LINE:
        raise MmanaFormatError(
            f"Se esperaba el marcador literal '*' y se encontró {marker!r}.",
            path=resolved_path,
            line_number=marker_line,
        )

    frequency_raw, frequency_line = reader.next_line("la frecuencia principal")
    frequency_mhz = _parse_float(
        frequency_raw,
        path=resolved_path,
        line_number=frequency_line,
        field="la frecuencia principal",
    )

    wires_header, wires = _read_wires(reader, resolved_path)
    source_header, source_flag, sources = _read_source(reader, resolved_path)
    load_header, load_flag, loads = _read_loads(reader, resolved_path)
    segmentation_header, segmentation = _read_segmentation(reader, resolved_path)
    environment_header, environment = _read_environment(reader, resolved_path)
    comment_header, comment = _read_comment(reader)

    return MmanaDocument(
        title=title,
        marker=marker,
        frequency_mhz=frequency_mhz,
        wires_header=wires_header,
        wires=wires,
        source_header=source_header,
        source_flag=source_flag,
        sources=sources,
        load_header=load_header,
        load_flag=load_flag,
        loads=loads,
        segmentation_header=segmentation_header,
        segmentation=segmentation,
        environment_header=environment_header,
        environment=environment,
        comment_header=comment_header,
        comment=comment,
        encoding=encoding,
        line_terminator=line_terminator,
    )


def detect_mmana_encoding(
    data: bytes,
    *,
    legacy_encoding: str | None = None,
) -> tuple[str, str]:
    """Determina la codificación de texto y el separador de línea de un .maa.

    CP1251 y CP1252 asignan un carácter a prácticamente todo el rango
    0xC0-0xFF: el alfabeto cirílico completo de CP1251 y las letras
    latinas acentuadas de CP1252 ocupan exactamente el mismo rango de
    bytes (verificado contra las tablas de ambas páginas de código).
    Por lo tanto, que un archivo "decodifique sin error" bajo CP1251 o
    bajo CP1252 no es evidencia de cuál es la correcta, y tampoco lo es
    contar cuántos caracteres resultantes parecen cirílicos: un byte
    latino acentuado de CP1252 (por ejemplo ``é`` = 0xE9) decodifica
    igual de "cirílico" bajo CP1251 (0xE9 -> "й"). Este módulo no
    adivina en ese caso ambiguo.

    Política, en orden:

    1. Marca de orden de bytes UTF-8 presente -> ``"utf-8-sig"``.
    2. El contenido completo decodifica como UTF-8 estricto ->
       ``"utf-8"`` (cubre los archivos ASCII y los genuinamente UTF-8).
    3. El archivo contiene algún byte que CP1252 deja indefinido
       (0x81, 0x8D, 0x8F, 0x90 o 0x9D) pero que CP1251 sí define -> se
       usa ``"cp1251"``. Esta es una señal estructural decisiva (CP1252
       no puede representar ese byte en absoluto), no una suposición
       estadística.
    4. En cualquier otro caso no-UTF-8, no se elige en silencio: se usa
       ``legacy_encoding`` si el llamador lo especificó explícitamente
       (debe ser ``"cp1251"`` o ``"cp1252"``); si no se especificó, se
       rechaza el archivo pidiendo esa decisión explícita.

    Args:
        data: Contenido crudo del archivo.
        legacy_encoding: Codificación de 8 bits a usar cuando el
            archivo no es UTF-8 y no contiene ninguna señal decisiva
            propia. Debe ser ``"cp1251"`` o ``"cp1252"`` cuando se
            especifica.

    Returns:
        Una tupla ``(nombre_de_codificación, separador_de_línea)``.

    Raises:
        MmanaFormatError: Si el archivo no es UTF-8, no contiene una
            señal decisiva propia, y no se especificó
            ``legacy_encoding``; o si la codificación elegida
            (decisiva o explícita) no logra decodificar el archivo.
    """
    line_terminator = "\r\n" if b"\r\n" in data else "\n"

    if data.startswith(_UTF8_BOM):
        return "utf-8-sig", line_terminator

    try:
        data.decode("utf-8")
        return "utf-8", line_terminator
    except UnicodeDecodeError:
        pass

    if any(byte in _CP1252_UNDEFINED_BYTES for byte in data):
        try:
            data.decode("cp1251")
        except UnicodeDecodeError as error:
            raise MmanaFormatError(
                "El archivo no es UTF-8, contiene un byte que CP1252 no "
                "define, y tampoco es válido como CP1251."
            ) from error
        return "cp1251", line_terminator

    if legacy_encoding is not None:
        if legacy_encoding not in ("cp1251", "cp1252"):
            raise MmanaFormatError(
                "legacy_encoding debe ser 'cp1251' o 'cp1252'; se "
                f"recibió {legacy_encoding!r}."
            )
        try:
            data.decode(legacy_encoding)
        except UnicodeDecodeError as error:
            raise MmanaFormatError(
                f"El archivo no puede decodificarse como {legacy_encoding}."
            ) from error
        return legacy_encoding, line_terminator

    raise MmanaFormatError(
        "El archivo no es UTF-8 y su contenido es ambiguo entre CP1251 "
        "y CP1252 (ambas páginas de código lo decodifican sin error). "
        "Especifique legacy_encoding='cp1251' o 'cp1252' explícitamente; "
        "esta función no elige en silencio entre ambas."
    )


def load_mmana(
    source: str | Path,
    *,
    legacy_encoding: str | None = None,
) -> MmanaDocument:
    """Carga y analiza estructuralmente un archivo MMANA-GAL .maa.

    Lee el archivo como bytes, determina su codificación mediante
    :func:`detect_mmana_encoding` (ver su política explícita para el
    caso ambiguo CP1251/CP1252) y delega el análisis estructural en
    :func:`parse_mmana`.

    Args:
        source: Ruta del archivo a cargar.
        legacy_encoding: Ver :func:`detect_mmana_encoding`.

    Raises:
        MmanaFormatError: Si la codificación no puede determinarse sin
            ambigüedad, o si el contenido no respeta la gramática
            estructural esperada.
        OSError: Si el archivo no puede abrirse.
    """
    path = Path(source)
    data = path.read_bytes()
    encoding, line_terminator = detect_mmana_encoding(
        data, legacy_encoding=legacy_encoding
    )

    try:
        text = data.decode(encoding)
    except UnicodeDecodeError as error:
        raise MmanaFormatError(
            f"No se pudo decodificar el archivo como {encoding}: {error}",
            path=path,
        ) from error

    return parse_mmana(
        text,
        encoding=encoding,
        line_terminator=line_terminator,
        path=path,
    )
