"""Configuración de Qt offscreen para las pruebas (sin Qt).

La configuración de Windows se prueba con un ``WINDIR`` falso dentro de
``tmp_path``: no depende de que la máquina tenga una letra de unidad ni
una ruta concretas, y corre en cualquier sistema.
"""

import sys
from pathlib import Path

import pytest

from qt_offscreen import (
    configure_offscreen,
    offscreen_environment,
    windows_font_directory,
)

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def fake_windir(tmp_path):
    windir = tmp_path / "Windows"
    (windir / "Fonts").mkdir(parents=True)
    return windir


def test_windows_offscreen_uses_the_windir_fonts(fake_windir):
    environment = {"WINDIR": str(fake_windir)}

    configure_offscreen(environment, platform="win32")

    assert environment["QT_QPA_PLATFORM"] == "offscreen"
    assert environment["QT_QPA_FONTDIR"] == str(fake_windir / "Fonts")


def test_windows_font_directory_must_exist(tmp_path):
    environment = {"WINDIR": str(tmp_path / "Windows")}

    with pytest.raises(RuntimeError, match="font directory does not exist"):
        configure_offscreen(environment, platform="win32")
    assert "QT_QPA_FONTDIR" not in environment


def test_windows_requires_windir():
    with pytest.raises(RuntimeError, match="WINDIR is not set"):
        windows_font_directory({})


def test_explicit_non_offscreen_platform_is_left_alone(fake_windir):
    environment = {"WINDIR": str(fake_windir), "QT_QPA_PLATFORM": "windows"}

    configure_offscreen(environment, platform="win32")

    assert environment == {"WINDIR": str(fake_windir), "QT_QPA_PLATFORM": "windows"}


def test_linux_keeps_its_configuration_without_windows_paths():
    # Sin WINDIR: en Linux no se busca ninguna ruta de Windows.
    environment = {"HOME": "/home/tester"}

    configure_offscreen(environment, platform="linux")

    assert environment == {"HOME": "/home/tester", "QT_QPA_PLATFORM": "offscreen"}


def test_subprocess_environment_is_a_copy_forced_to_offscreen(fake_windir):
    base = {"WINDIR": str(fake_windir), "QT_QPA_PLATFORM": "windows"}

    environment = offscreen_environment(base, platform="win32")

    assert environment["QT_QPA_PLATFORM"] == "offscreen"
    assert environment["QT_QPA_FONTDIR"] == str(fake_windir / "Fonts")
    assert base == {"WINDIR": str(fake_windir), "QT_QPA_PLATFORM": "windows"}


def test_linux_subprocess_environment_has_no_font_directory():
    environment = offscreen_environment({}, platform="linux")

    assert environment == {"QT_QPA_PLATFORM": "offscreen"}


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_real_windows_environment_points_to_the_system_fonts():
    import os

    environment = offscreen_environment()

    fonts = Path(environment["QT_QPA_FONTDIR"])
    # Derivado de WINDIR, sin suponer la letra de unidad.
    assert fonts == Path(os.environ["WINDIR"]) / "Fonts"
    assert fonts.is_dir()


def test_windows_build_script_sets_and_restores_the_font_directory():
    script = (REPO / "scripts" / "build_gui_windows.ps1").read_text(
        encoding="utf-8-sig"
    )

    assert 'Join-Path $env:WINDIR "Fonts"' in script
    assert "Test-Path $windowsFontDirectory -PathType Container" in script
    assert "$env:QT_QPA_FONTDIR = $windowsFontDirectory" in script
    assert "$env:QT_QPA_FONTDIR = $previousQtFontDir" in script


def test_linux_build_script_does_not_configure_windows_fonts():
    script = (REPO / "scripts" / "build_gui_linux.sh").read_text(encoding="utf-8")

    assert "QT_QPA_FONTDIR" not in script
    assert "WINDIR" not in script
