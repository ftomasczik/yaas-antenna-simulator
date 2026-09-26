"""Caso de uso: importar un archivo MMANA-GAL y guardarlo como proyecto.

Este módulo orquesta, sin duplicar su lógica, tres piezas ya
existentes: el lector estructural (``antsim.importers.load_mmana``),
la conversión a dominio
(``antsim.application.mmana_conversion.convert_mmana_to_project``) y
el escritor de proyectos (``antsim.projects.save_project``). No
conoce ``argparse`` ni ``gettext``, no traduce ningún mensaje, y no
invoca PyNEC: es una transformación pura de datos (además de la
escritura explícita de ``write_mmana_import``), para poder
reutilizarse desde la CLI y desde una futura interfaz gráfica.
"""

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from antsim.application.mmana_conversion import convert_mmana_to_project
from antsim.importers import (
    MmanaCompatibilityReport,
    analyze_mmana_compatibility,
    load_mmana,
)
from antsim.projects import AntennaProject, SweepSettings, save_project


@dataclass(frozen=True)
class MmanaImportResult:
    """Resultado de preparar (sin escribir) la importación de un .maa.

    ``compatibility_report`` conserva también las advertencias (no
    solo los errores, que ya habrían impedido llegar hasta acá) para
    que la CLI o una futura GUI puedan mostrarlas al usuario.
    ``detected_encoding`` proviene directamente de
    ``MmanaDocument.encoding``, que el lector ya expone de forma
    fiable (es el mismo valor que decidió
    ``antsim.importers.detect_mmana_encoding``); no se vuelve a
    detectar aquí.
    """

    project: AntennaProject
    compatibility_report: MmanaCompatibilityReport
    source_path: Path
    detected_encoding: str


def prepare_mmana_import(
    source: str | Path,
    *,
    sweep: SweepSettings,
    legacy_encoding: str | None = None,
) -> MmanaImportResult:
    """Carga, analiza y convierte un archivo MMANA-GAL, sin escribir nada.

    Flujo:

    1. Carga el archivo con ``load_mmana`` (bytes → codificación →
       análisis estructural). ``legacy_encoding`` se reenvía tal cual
       a ``load_mmana``/``detect_mmana_encoding``: solo importa cuando
       el archivo no es UTF-8 y resulta ambiguo entre CP1251 y
       CP1252; en ese caso debe ser exactamente ``"cp1251"`` o
       ``"cp1252"``, o la carga falla con ``MmanaFormatError`` (ver
       ``antsim.importers.detect_mmana_encoding``). Esta función no
       reimplementa esa lógica, solo la reenvía.
    2. Analiza compatibilidad con ``analyze_mmana_compatibility``.
    3. Si hay algún error, ``raise_if_incompatible()`` lo propaga
       (``MmanaCompatibilityError``) y esta función termina ahí: no
       se llega a construir ningún ``AntennaProject``.
    4. Si el documento es compatible, lo convierte con
       ``convert_mmana_to_project`` (que vuelve a evaluar
       compatibilidad internamente; ver la nota de diseño más abajo).
    5. Devuelve un ``MmanaImportResult`` con el proyecto, el informe
       de compatibilidad completo (incluidas las advertencias) y
       metadatos de origen.

    Esta función **no escribe ningún archivo**; ver
    ``write_mmana_import`` para el paso de escritura, deliberadamente
    separado.

    Nota de diseño: ``analyze_mmana_compatibility`` se ejecuta aquí
    (para poder devolver el informe completo, con sus advertencias) y
    se vuelve a ejecutar dentro de ``convert_mmana_to_project`` (que
    no acepta un informe ya calculado). Es una duplicación del
    *análisis* de compatibilidad (una función pura y barata), no de
    su *parsing*, *conversión* ni *serialización*, que siguen
    viviendo en un único lugar cada una.

    Args:
        source: Ruta del archivo ``.maa`` a importar.
        sweep: Configuración de barrido a usar tal cual en el
            proyecto resultante; nunca se deriva del archivo
            MMANA-GAL.
        legacy_encoding: Ver ``antsim.importers.detect_mmana_encoding``.

    Returns:
        El resultado preparado, listo para inspeccionar o para
        pasarse a ``write_mmana_import``.

    Raises:
        MmanaFormatError: Si el archivo no puede leerse o no respeta
            la gramática estructural esperada (incluida una
            codificación ambigua sin ``legacy_encoding`` explícito).
        MmanaCompatibilityError: Si el documento no es compatible.
        OSError: Si el archivo de origen no puede abrirse.
    """
    source_path = Path(source)
    document = load_mmana(source_path, legacy_encoding=legacy_encoding)

    report = analyze_mmana_compatibility(document)
    report.raise_if_incompatible()

    project = convert_mmana_to_project(document, sweep=sweep)

    return MmanaImportResult(
        project=project,
        compatibility_report=report,
        source_path=source_path,
        detected_encoding=document.encoding,
    )


def write_mmana_import(
    result: MmanaImportResult,
    destination: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    """Escribe el proyecto ya preparado como archivo ``.antsim``, atómicamente.

    Reutiliza ``antsim.projects.save_project`` tal cual para la
    serialización (no se duplica nada de eso aquí); esta función solo
    agrega la política de sobrescritura y la mecánica de escritura
    atómica alrededor de esa llamada:

    1. Se crea un archivo temporal **en el mismo directorio que el
       destino** (``tempfile.mkstemp(dir=...)``), para garantizar que
       está en el mismo sistema de archivos: es lo que hace que el
       ``os.replace`` final sea atómico en condiciones normales.
    2. Se cierra el descriptor del temporal antes de llamar a
       ``save_project`` (que abre el archivo por su cuenta).
    3. ``save_project`` escribe únicamente sobre la ruta temporal;
       nunca sobre el destino directamente.
    4. Si eso tiene éxito, se vuelve a comprobar
       destino/``overwrite`` (algo pudo haber creado el destino
       mientras se escribía el temporal) y recién entonces se mueve
       el temporal al destino con ``os.replace`` — en la mayoría de
       los sistemas operativos, un renombrado dentro del mismo
       sistema de archivos es atómico: el destino queda con el
       contenido completo anterior o con el nuevo completo, nunca a
       medias.
    5. Ante **cualquier** excepción (de ``save_project``, de la
       segunda comprobación, o de cualquier otro paso), se elimina el
       temporal, el destino anterior (si existía) queda intacto, y la
       excepción original se propaga sin modificarse.

    Esta función nunca deja un archivo temporal visible, ni tras un
    éxito (``os.replace`` lo consume) ni tras un fallo (se elimina
    explícitamente antes de relanzar la excepción).

    Args:
        result: Resultado ya preparado por ``prepare_mmana_import``.
        destination: Archivo ``.antsim`` de destino. Se rechaza,
            incluso con ``overwrite=True``, si resuelve a la misma
            ruta que ``result.source_path`` (el archivo MMANA-GAL de
            origen).
        overwrite: Si ``False`` (por defecto) y el destino ya existe,
            se rechaza sin escribir nada.

    Returns:
        La ruta del archivo escrito (igual a ``destination``,
        resuelta a ``Path``).

    Raises:
        ValueError: Si ``destination`` resuelve al mismo archivo que
            ``result.source_path``, o si no usa la extensión
            ``.antsim`` (esto último, propagado sin cambios desde
            ``save_project``).
        FileExistsError: Si el destino ya existe y ``overwrite`` es
            ``False`` (verificado antes de escribir el temporal, y de
            nuevo antes de moverlo).
        OSError: Cualquier error de E/S de ``save_project`` o del
            propio movimiento atómico, propagado sin modificarse.
    """
    destination_path = Path(destination)
    source_path = result.source_path

    if source_path.resolve() == destination_path.resolve():
        raise ValueError(
            f"{destination_path}: el destino no puede ser el mismo "
            "archivo que el origen MMANA-GAL, ni siquiera con "
            "overwrite=True."
        )

    def _check_destination() -> None:
        if destination_path.exists() and not overwrite:
            raise FileExistsError(
                f"{destination_path}: el archivo ya existe; use "
                "overwrite=True para sobrescribirlo."
            )

    _check_destination()

    # No se crea el directorio padre: no es la convención actual del
    # proyecto (ni save_project ni load_project lo hacen en ningún
    # otro camino). Si no existe, mkstemp falla con el mismo tipo de
    # error (FileNotFoundError) que antes fallaba save_project al
    # intentar abrir el destino directamente: no es una regresión.
    #
    # El sufijo debe ser ".antsim" (no ".tmp"): save_project valida la
    # extensión del archivo que recibe, y solo escribe sobre la ruta
    # temporal (nunca sobre el destino directamente).
    temp_descriptor, temp_name = tempfile.mkstemp(
        prefix=".antsim-import-",
        suffix=".antsim",
        dir=str(destination_path.parent),
    )
    temp_path = Path(temp_name)

    try:
        os.close(temp_descriptor)  # cerrado antes de que save_project abra el archivo

        save_project(result.project, temp_path)

        _check_destination()  # el destino pudo haber cambiado mientras escribíamos

        os.replace(temp_path, destination_path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise

    return destination_path
