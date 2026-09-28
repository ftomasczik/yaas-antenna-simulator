import pytest

from yaas.i18n import (
    get_language,
    normalize_language,
    set_language,
    translate,
)


@pytest.fixture(autouse=True)
def restore_english():
    """Evita que un test deje modificado el idioma global."""
    set_language("en")

    yield

    set_language("en")


def test_normalizes_regional_language_codes():
    assert normalize_language("es_AR") == "es"
    assert normalize_language("es-ES") == "es"
    assert normalize_language("en_US") == "en"


def test_normalizes_windows_language_names():
    assert normalize_language(
        "Spanish_Argentina"
    ) == "es"

    assert normalize_language(
        "English_United States"
    ) == "en"


def test_uses_english_as_source_language():
    selected = set_language("en")

    assert selected == "en"
    assert get_language() == "en"
    assert translate("Environment: OK") == (
        "Environment: OK"
    )


def test_translates_message_to_spanish():
    selected = set_language("es")

    assert selected == "es"
    assert get_language() == "es"
    assert translate("Environment: OK") == (
        "Entorno: OK"
    )


def test_rejects_unsupported_language():
    with pytest.raises(ValueError):
        set_language("fr")
        