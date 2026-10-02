"""Entorno de Qt ``offscreen`` para las pruebas de la GUI.

Solo para pruebas y subprocesos de prueba: la aplicación GUI normal no
usa este módulo ni cambia su entorno.

En Windows, el plugin ``offscreen`` de Qt no usa las fuentes del
sistema y busca un directorio de fuentes propio (que el wheel de
PySide6 no trae), así que puede escribir avisos de ``QFontDatabase`` en
stderr. Las pruebas comparan stderr de forma estricta, por eso en
Windows se le indica el directorio real de fuentes del sistema,
``%WINDIR%\\Fonts``, validando que exista. Esos avisos **no** se
agregan a ninguna lista de mensajes tolerados. En Linux no se toca
nada: el plugin usa fontconfig y no depende de rutas de Windows.

No importa Qt.
"""

import os
import sys
from collections.abc import Mapping, MutableMapping
from pathlib import Path

OFFSCREEN = "offscreen"


def windows_font_directory(environment: Mapping[str, str]) -> Path:
    """``%WINDIR%\\Fonts`` según ``environment``, validado.

    Raises:
        RuntimeError: Si ``WINDIR`` no está definido o el directorio de
            fuentes no existe.
    """
    windir = environment.get("WINDIR")
    if not windir:
        raise RuntimeError(
            "WINDIR is not set: cannot locate the Windows font directory "
            "for Qt offscreen tests."
        )
    fonts = Path(windir) / "Fonts"
    if not fonts.is_dir():
        raise RuntimeError(
            f"The Windows font directory does not exist: {fonts}"
        )
    return fonts


def configure_offscreen(
    environment: MutableMapping[str, str] | None = None,
    *,
    platform: str | None = None,
) -> MutableMapping[str, str]:
    """Configura ``environment`` (por defecto, ``os.environ``) para Qt offscreen.

    Respeta una plataforma Qt ya elegida (como el ``setdefault``
    anterior). Si la plataforma efectiva es ``offscreen`` y el sistema
    es Windows, fija ``QT_QPA_FONTDIR`` al directorio de fuentes de
    Windows. ``platform`` (por defecto ``sys.platform``) existe para
    probar la configuración de Windows desde cualquier sistema.
    """
    environment = os.environ if environment is None else environment
    platform = sys.platform if platform is None else platform

    environment.setdefault("QT_QPA_PLATFORM", OFFSCREEN)
    if environment["QT_QPA_PLATFORM"] == OFFSCREEN and platform == "win32":
        environment["QT_QPA_FONTDIR"] = str(windows_font_directory(environment))
    return environment


def offscreen_environment(
    base: Mapping[str, str] | None = None,
    *,
    platform: str | None = None,
) -> dict[str, str]:
    """Copia de ``base`` (por defecto, ``os.environ``) para un subproceso offscreen.

    Fuerza ``QT_QPA_PLATFORM=offscreen`` (como el
    ``dict(os.environ, QT_QPA_PLATFORM="offscreen")`` anterior) y aplica
    la misma configuración de fuentes que `configure_offscreen`. No
    modifica ``base``.
    """
    environment = dict(os.environ if base is None else base)
    environment["QT_QPA_PLATFORM"] = OFFSCREEN
    return dict(configure_offscreen(environment, platform=platform))
