"""Infraestructura de internacionalización."""

import gettext
import locale
import os
from pathlib import Path


TRANSLATION_DOMAIN = "antsim"
SUPPORTED_LANGUAGES = ("en", "es")
FALLBACK_LANGUAGE = "en"

LOCALES_DIRECTORY = (
    Path(__file__).resolve().parent / "locales"
)

_current_language = FALLBACK_LANGUAGE
_translation: gettext.NullTranslations = (
    gettext.NullTranslations()
)


def normalize_language(
    language: str | None,
) -> str | None:
    """Normaliza nombres como es_AR, es-AR o Spanish_Argentina."""
    if language is None:
        return None

    normalized = language.strip().lower()

    if not normalized:
        return None

    if normalized.startswith("spanish"):
        return "es"

    if normalized.startswith("english"):
        return "en"

    normalized = normalized.replace("-", "_")
    language_code = normalized.split("_", maxsplit=1)[0]

    if language_code in SUPPORTED_LANGUAGES:
        return language_code

    return None


def detect_language() -> str:
    """Detecta el idioma solicitado o configurado en el sistema."""
    environment_language = normalize_language(
        os.environ.get("ANTSIM_LANGUAGE")
    )

    if environment_language is not None:
        return environment_language

    system_language = normalize_language(
        locale.getlocale()[0]
    )

    if system_language is not None:
        return system_language

    return FALLBACK_LANGUAGE


def set_language(
    language: str | None = None,
) -> str:
    """Selecciona el idioma activo.

    Args:
        language: Código solicitado. Si es None, se detecta
            desde el entorno y el sistema operativo.

    Returns:
        Código del idioma finalmente seleccionado.

    Raises:
        ValueError: Si se solicita un idioma no soportado.
    """
    global _current_language
    global _translation

    if language is None:
        selected_language = detect_language()
    else:
        selected_language = normalize_language(language)

        if selected_language is None:
            raise ValueError(
                f"Unsupported language: {language}"
            )

    _current_language = selected_language

    if selected_language == FALLBACK_LANGUAGE:
        _translation = gettext.NullTranslations()
    else:
        _translation = gettext.translation(
            TRANSLATION_DOMAIN,
            localedir=LOCALES_DIRECTORY,
            languages=[selected_language],
            fallback=True,
        )

    return selected_language


def get_language() -> str:
    """Devuelve el código del idioma activo."""
    return _current_language


def translate(message: str) -> str:
    """Traduce un mensaje utilizando el catálogo activo."""
    return _translation.gettext(message)


# Selecciona automáticamente un idioma durante la importación.
set_language()
