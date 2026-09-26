from pathlib import Path

import pytest

from antsim.application import (
    MmanaImportResult,
    prepare_mmana_import,
    write_mmana_import,
)
from antsim.importers import MmanaCompatibilityError, MmanaFormatError
from antsim.projects import SweepSettings, load_project


def _sweep() -> SweepSettings:
    return SweepSettings(start_frequency_mhz=13.5, stop_frequency_mhz=15.5, points=81)


def _maa_text(
    *,
    title: str = "TEST_01",
    loads: str = "0,\t0\n",
    phase_degrees: float = 0.0,
) -> str:
    """Reproduce 00-base-dipole.maa (C:\\dev\\mmana-experiments)."""
    return (
        f"{title}\n"
        "*\n"
        "14.15\n"
        "***Wires***\n"
        "1\n"
        "-5.03,\t0.0,\t0.0,\t5.03,\t0.0,\t0.0,\t0.001,\t-1\n"
        "***Source***\n"
        "1,\t0\n"
        f"w1c,\t{phase_degrees},\t1.0\n"
        "***Load***\n"
        f"{loads}"
        "***Segmentation***\n"
        "800,\t80,\t2.0,\t2\n"
        "***G/H/M/R/AzEl/X***\n"
        "0,\t5.0,\t0,\t50.0,\t120,\t60,\t0.0\n"
    )


def _write_maa(path: Path, text: str, encoding: str = "utf-8") -> Path:
    path.write_bytes(text.encode(encoding))
    return path


# ---------------------------------------------------------------------------
# prepare_mmana_import
# ---------------------------------------------------------------------------


def test_prepare_import_from_utf8_file(tmp_path):
    source = _write_maa(tmp_path / "dipole.maa", _maa_text())

    result = prepare_mmana_import(source, sweep=_sweep())

    assert isinstance(result, MmanaImportResult)
    assert result.source_path == source
    assert result.detected_encoding == "utf-8"
    assert result.compatibility_report.is_compatible


def test_prepare_import_resulting_project_is_correct(tmp_path):
    source = _write_maa(tmp_path / "dipole.maa", _maa_text(title="Dipolo de 20 metros"))

    result = prepare_mmana_import(source, sweep=_sweep())
    project = result.project

    assert project.metadata.name == "Dipolo de 20 metros"
    assert project.frequency_mhz == 14.15
    assert project.reference_impedance == 50.0
    assert len(project.wires) == 1
    assert project.wires[0].segments == 77  # lambda/160, ver ADR 0007
    assert project.source.wire_tag == 1
    assert project.source.segment == 39


def test_prepare_import_uses_the_given_sweep_as_is(tmp_path):
    source = _write_maa(tmp_path / "dipole.maa", _maa_text())
    sweep = _sweep()

    result = prepare_mmana_import(source, sweep=sweep)

    assert result.project.sweep is sweep


@pytest.mark.parametrize("legacy_encoding", ["cp1251", "cp1252"])
def test_prepare_import_respects_explicit_legacy_encoding(tmp_path, legacy_encoding):
    # "café" solo usa el byte 0xE9, definido tanto en CP1251 como en
    # CP1252 (ver antsim.importers.detect_mmana_encoding): es el caso
    # ambiguo que exige legacy_encoding explícito.
    source = _write_maa(
        tmp_path / "legacy.maa", _maa_text(title="café"), encoding="cp1252"
    )

    result = prepare_mmana_import(
        source, sweep=_sweep(), legacy_encoding=legacy_encoding
    )

    assert result.detected_encoding == legacy_encoding
    if legacy_encoding == "cp1252":
        assert result.project.metadata.name == "café"
    else:
        # Mismos bytes, reinterpretados como CP1251: un título distinto.
        assert result.project.metadata.name != "café"


def test_prepare_import_rejects_ambiguous_legacy_encoding_without_selection(tmp_path):
    source = _write_maa(
        tmp_path / "legacy.maa", _maa_text(title="café"), encoding="cp1252"
    )

    with pytest.raises(MmanaFormatError, match="ambiguo"):
        prepare_mmana_import(source, sweep=_sweep())


def test_prepare_import_rejects_structurally_invalid_file(tmp_path):
    # Marcador de la segunda línea invalido ("*" reemplazado por "?").
    text = _maa_text().replace("\n*\n", "\n?\n", 1)
    source = _write_maa(tmp_path / "broken.maa", text)

    with pytest.raises(MmanaFormatError):
        prepare_mmana_import(source, sweep=_sweep())


def test_prepare_import_rejects_incompatible_document(tmp_path):
    text = _maa_text(loads="1,\t0\nw1c,\t1,\t50.0,\t0.0\n")
    source = _write_maa(tmp_path / "with_load.maa", text)

    with pytest.raises(MmanaCompatibilityError):
        prepare_mmana_import(source, sweep=_sweep())


def test_prepare_import_result_keeps_warnings(tmp_path):
    # Fase distinta de cero: advertencia, no error (sigue siendo
    # compatible), pero debe conservarse para que la CLI/GUI la muestren.
    source = _write_maa(tmp_path / "phase.maa", _maa_text(phase_degrees=45.0))

    result = prepare_mmana_import(source, sweep=_sweep())

    assert result.compatibility_report.is_compatible
    assert any(
        issue.code == "source-phase-nonzero"
        for issue in result.compatibility_report.warnings
    )


# ---------------------------------------------------------------------------
# write_mmana_import
# ---------------------------------------------------------------------------


def test_write_creates_antsim_file(tmp_path):
    source = _write_maa(tmp_path / "dipole.maa", _maa_text())
    result = prepare_mmana_import(source, sweep=_sweep())
    destination = tmp_path / "dipole.antsim"

    written_path = write_mmana_import(result, destination)

    assert written_path == destination
    assert destination.is_file()


def test_write_then_reload_matches_original_project(tmp_path):
    source = _write_maa(tmp_path / "dipole.maa", _maa_text(title="Dipolo importado"))
    result = prepare_mmana_import(source, sweep=_sweep())
    destination = tmp_path / "dipole.antsim"

    write_mmana_import(result, destination)
    reloaded = load_project(destination)

    assert reloaded == result.project


def test_write_refuses_to_overwrite_existing_destination_by_default(tmp_path):
    source = _write_maa(tmp_path / "dipole.maa", _maa_text())
    result = prepare_mmana_import(source, sweep=_sweep())
    destination = tmp_path / "dipole.antsim"
    destination.write_text("contenido previo", encoding="utf-8")

    with pytest.raises(FileExistsError):
        write_mmana_import(result, destination)

    # El contenido previo no se toco.
    assert destination.read_text(encoding="utf-8") == "contenido previo"


def test_write_overwrites_when_explicitly_requested(tmp_path):
    source = _write_maa(tmp_path / "dipole.maa", _maa_text())
    result = prepare_mmana_import(source, sweep=_sweep())
    destination = tmp_path / "dipole.antsim"
    destination.write_text("contenido previo", encoding="utf-8")

    write_mmana_import(result, destination, overwrite=True)

    reloaded = load_project(destination)
    assert reloaded == result.project


def test_write_leaves_no_temporary_file_after_success(tmp_path):
    source = _write_maa(tmp_path / "dipole.maa", _maa_text())
    result = prepare_mmana_import(source, sweep=_sweep())
    destination = tmp_path / "dipole.antsim"

    write_mmana_import(result, destination)

    remaining = [p for p in tmp_path.iterdir() if p not in (source, destination)]
    assert remaining == []


def test_write_failure_propagates_keeps_previous_destination_and_leaves_no_temp(
    tmp_path, monkeypatch
):
    source = _write_maa(tmp_path / "dipole.maa", _maa_text())
    result = prepare_mmana_import(source, sweep=_sweep())
    destination = tmp_path / "dipole.antsim"
    destination.write_text("contenido previo", encoding="utf-8")

    def _fake_save_project(project, destination_arg):
        # Escribe contenido parcial en el temporal (simula una
        # escritura interrumpida) y despues falla con un error de E/S.
        Path(destination_arg).write_text("PARCIAL", encoding="utf-8")
        raise OSError("fallo simulado de disco")

    monkeypatch.setattr(
        "antsim.application.mmana_import.save_project", _fake_save_project
    )

    with pytest.raises(OSError, match="fallo simulado"):
        write_mmana_import(result, destination, overwrite=True)

    # El destino anterior permanece intacto: la excepcion original
    # (OSError) se propago sin modificarse.
    assert destination.read_text(encoding="utf-8") == "contenido previo"

    # No queda ningun archivo temporal, ni siquiera el que tenia
    # contenido parcial.
    remaining = [p for p in tmp_path.iterdir() if p not in (source, destination)]
    assert remaining == []


def test_write_rejects_source_equal_to_destination(tmp_path):
    source = _write_maa(tmp_path / "dipole.maa", _maa_text())
    result = prepare_mmana_import(source, sweep=_sweep())
    original_bytes = source.read_bytes()

    with pytest.raises(ValueError, match="mismo archivo"):
        write_mmana_import(result, source, overwrite=True)

    # El archivo de origen no se toco.
    assert source.read_bytes() == original_bytes
