import pytest
import json
from pathlib import Path
from antsim.cli.main import main

from antsim.exporters import sweep_request_to_nec
from antsim.projects import load_project

@pytest.fixture(autouse=True)
def use_spanish_cli(monkeypatch):
    """Ejecuta las pruebas existentes en español."""
    monkeypatch.setenv("ANTSIM_LANGUAGE", "es")


def test_cli_reports_version(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])

    output = capsys.readouterr().out

    assert exit_info.value.code == 0
    assert "antsim 0.0.1" in output


def test_cli_doctor_reports_healthy_environment(capsys):
    exit_code = main(["doctor"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Python:" in output
    assert "PyNEC: OK" in output
    assert "Entorno: OK" in output


def test_cli_simulates_reference_dipole(capsys):
    exit_code = main(["simulate-dipole"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Frecuencia: 14.150 MHz" in output
    assert "Impedancia:" in output
    assert "ROE respecto de 50 ohm:" in output

def test_cli_executes_reference_sweep(capsys):
    exit_code = main(
        [
            "sweep-dipole",
            "--start",
            "13",
            "--stop",
            "16",
            "--points",
            "13",
        ]
    )

    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Barrido: 13.000-16.000 MHz" in output
    assert "Puntos: 13" in output
    assert "Resonancia aproximada:" in output
    assert "ROE mínima:" in output
    assert "Ancho de banda para ROE <= 2.00:" in output
 

def test_cli_rejects_invalid_sweep(capsys):
    exit_code = main(
        [
            "sweep-dipole",
            "--start",
            "16",
            "--stop",
            "13",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 2
    assert "Error:" in captured.err

def test_cli_exports_sweep_csv(tmp_path, capsys):
    destination = tmp_path / "resultados.csv"

    exit_code = main(
        [
            "sweep-dipole",
            "--start",
            "13",
            "--stop",
            "16",
            "--points",
            "5",
            "--output",
            str(destination),
        ]
    )

    output = capsys.readouterr().out

    assert exit_code == 0
    assert destination.exists()
    assert "Archivo CSV:" in output

def test_cli_rejects_invalid_swr_limit(capsys):
    exit_code = main(
        [
            "sweep-dipole",
            "--swr-limit",
            "0.5",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 2
    assert "límite de ROE" in captured.err

def test_cli_doctor_can_use_english(capsys):
    exit_code = main(
        [
            "--language",
            "en",
            "doctor",
        ]
    )

    output = capsys.readouterr().out

    assert exit_code == 0
    assert "System:" in output
    assert "Environment: OK" in output

def test_cli_sweep_can_use_english(capsys):
    exit_code = main(
        [
            "--language",
            "en",
            "sweep-dipole",
            "--start",
            "13",
            "--stop",
            "16",
            "--points",
            "13",
        ]
    )

    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Sweep: 13.000-16.000 MHz" in output
    assert "Approximate resonance:" in output
    assert "Minimum SWR:" in output
    assert "Bandwidth for SWR <= 2.00:" in output

def test_cli_validates_project(capsys):
    exit_code = main(
        [
            "validate",
            "examples/dipole-20m.antsim",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Proyecto válido:" in captured.out
    assert "Nombre del proyecto:" in captured.out
    assert "Versión del esquema: 1" in captured.out
    assert "Conductores: 1" in captured.out
    assert captured.err == ""


def test_cli_rejects_missing_project(
    tmp_path,
    capsys,
):
    missing_project = tmp_path / "missing.antsim"

    exit_code = main(
        [
            "validate",
            str(missing_project),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.out == ""
    assert "Proyecto inválido:" in captured.err


def test_cli_validates_project_in_english(capsys):
    exit_code = main(
        [
            "--language",
            "en",
            "validate",
            "examples/dipole-20m.antsim",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Valid project:" in captured.out
    assert "Project name:" in captured.out
    assert "Schema version: 1" in captured.out
    assert "Wires: 1" in captured.out
    assert captured.err == ""

def test_cli_rejects_malformed_project(
    tmp_path,
    capsys,
):
    project_path = tmp_path / "malformed.antsim"
    project_path.write_text(
        '{"schema_version": 1,',
        encoding="utf-8",
    )

    exit_code = main(
        [
            "validate",
            str(project_path),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.out == ""
    assert "Proyecto inválido:" in captured.err


def test_cli_rejects_unsupported_schema_version(
    tmp_path,
    capsys,
):
    source_path = Path(
        "examples/dipole-20m.antsim"
    )
    project_data = json.loads(
        source_path.read_text(encoding="utf-8")
    )
    project_data["schema_version"] = 999

    project_path = tmp_path / "future.antsim"
    project_path.write_text(
        json.dumps(project_data),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "validate",
            str(project_path),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.out == ""
    assert "Proyecto inválido:" in captured.err

def test_cli_simulates_project(capsys):
    exit_code = main(
        [
            "simulate",
            "examples/dipole-20m.antsim",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert (
        "Simulando proyecto: Dipolo de 20 metros"
        in captured.out
    )
    assert "Frecuencia: 14.150 MHz" in captured.out
    assert "Impedancia: 67.43 -31.25j ohm" in captured.out
    assert "ROE respecto de 50 ohm: 1.83" in captured.out
    assert captured.err == ""


def test_cli_project_simulation_matches_reference(
    capsys,
):
    reference_exit_code = main(
        ["simulate-dipole"]
    )
    reference_output = capsys.readouterr()

    project_exit_code = main(
        [
            "simulate",
            "examples/dipole-20m.antsim",
        ]
    )
    project_output = capsys.readouterr()

    assert reference_exit_code == 0
    assert project_exit_code == 0

    project_lines = project_output.out.splitlines()
    reference_lines = reference_output.out.splitlines()

    # La primera línea adicional identifica el proyecto.
    assert project_lines[1:] == reference_lines


def test_cli_rejects_missing_project_for_simulation(
    tmp_path,
    capsys,
):
    missing_project = tmp_path / "missing.antsim"

    exit_code = main(
        [
            "simulate",
            str(missing_project),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.out == ""
    assert "Proyecto inválido:" in captured.err

def test_cli_sweeps_project(capsys):
    exit_code = main(
        [
            "sweep",
            "examples/dipole-20m.antsim",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert (
        "Ejecutando barrido del proyecto: "
        "Dipolo de 20 metros"
        in captured.out
    )
    assert "Barrido:" in captured.out
    assert "Puntos:" in captured.out
    assert "Resonancia aproximada:" in captured.out
    assert "ROE mínima:" in captured.out
    assert "Ancho de banda" in captured.out
    assert captured.err == ""


def test_cli_exports_project_sweep_csv(
    tmp_path,
    capsys,
):
    output_path = tmp_path / "project-sweep.csv"

    exit_code = main(
        [
            "sweep",
            "examples/dipole-20m.antsim",
            "--output",
            str(output_path),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert output_path.is_file()
    assert output_path.stat().st_size > 0
    assert "Archivo CSV:" in captured.out
    assert str(output_path.resolve()) in captured.out
    assert captured.err == ""


def test_cli_rejects_missing_project_for_sweep(
    tmp_path,
    capsys,
):
    missing_project = tmp_path / "missing.antsim"

    exit_code = main(
        [
            "sweep",
            str(missing_project),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.out == ""
    assert "Proyecto inválido:" in captured.err


def test_cli_sweeps_project_in_english(capsys):
    exit_code = main(
        [
            "--language",
            "en",
            "sweep",
            "examples/dipole-20m.antsim",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert (
        "Sweeping project: Dipolo de 20 metros"
        in captured.out
    )
    assert "Sweep:" in captured.out
    assert "Points:" in captured.out
    assert "Approximate resonance:" in captured.out
    assert "Minimum SWR:" in captured.out
    assert "Bandwidth" in captured.out
    assert captured.err == ""

def test_cli_exports_project_to_nec(
    tmp_path,
    capsys,
):
    output_path = tmp_path / "dipole.nec"

    exit_code = main(
        [
            "export-nec",
            "examples/dipole-20m.antsim",
            str(output_path),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert output_path.is_file()
    assert (
        f"Archivo NEC: {output_path.resolve()}"
        in captured.out
    )
    assert captured.err == ""

    nec_text = output_path.read_text(
        encoding="utf-8"
    )

    assert nec_text.startswith(
        "CM Dipolo de 20 metros\nCE\n"
    )
    assert (
        "GW 1 101 -5.03 0 0 5.03 0 0 0.001\n"
        in nec_text
    )
    assert "GE 0\n" in nec_text
    assert "EX 0 1 51 0 1 0\n" in nec_text
    assert "FR 0 1 0 0 14.15 0\n" in nec_text
    assert nec_text.endswith("EN\n")


def test_cli_rejects_missing_project_for_nec_export(
    tmp_path,
    capsys,
):
    missing_project = tmp_path / "missing.antsim"
    output_path = tmp_path / "output.nec"

    exit_code = main(
        [
            "export-nec",
            str(missing_project),
            str(output_path),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 2
    assert not output_path.exists()
    assert captured.out == ""
    assert "Proyecto inválido:" in captured.err


def test_cli_exports_project_to_nec_in_english(
    tmp_path,
    capsys,
):
    output_path = tmp_path / "dipole.nec"

    exit_code = main(
        [
            "--language",
            "en",
            "export-nec",
            "examples/dipole-20m.antsim",
            str(output_path),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert output_path.is_file()
    assert (
        f"NEC file: {output_path.resolve()}"
        in captured.out
    )
    assert captured.err == ""

def test_cli_exports_project_sweep_to_nec(
    tmp_path,
    capsys,
):
    project_path = Path(
        "examples/dipole-20m.antsim"
    )
    output_path = tmp_path / "dipole-sweep.nec"

    exit_code = main(
        [
            "export-nec",
            "--sweep",
            str(project_path),
            str(output_path),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert output_path.is_file()
    assert (
        f"Archivo NEC: {output_path.resolve()}"
        in captured.out
    )
    assert captured.err == ""

    project = load_project(project_path)
    expected_text = sweep_request_to_nec(
        request=project.to_sweep_request(),
        title=project.metadata.name,
    )

    assert (
        output_path.read_text(encoding="utf-8")
        == expected_text
    )

def create_touchstone_measurement(
    destination: Path,
) -> None:
    destination.write_text(
        "! AntSim test measurement\n"
        "# MHz S RI R 50\n"
        "14.000 0.20 -0.10\n"
        "14.100 0.10 -0.05\n"
        "14.200 0.00 0.00\n"
        "14.300 0.10 0.05\n",
        encoding="utf-8",
    )


def test_cli_inspects_touchstone_measurement(
    tmp_path,
    capsys,
):
    measurement_path = tmp_path / "measurement.s1p"
    create_touchstone_measurement(measurement_path)

    exit_code = main(
        [
            "inspect-s1p",
            str(measurement_path),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert (
        f"Medición: {measurement_path.resolve()}"
        in captured.out
    )
    assert (
        "Rango de frecuencias: "
        "14.000-14.300 MHz"
        in captured.out
    )
    assert "Puntos: 4" in captured.out
    assert (
        "Impedancia de referencia: 50.00 ohm"
        in captured.out
    )
    assert "Resonancia aproximada:" in captured.out
    assert "Frecuencia: 14.200 MHz" in captured.out
    assert "ROE mínima:" in captured.out
    assert captured.err == ""


def test_cli_rejects_invalid_touchstone_measurement(
    tmp_path,
    capsys,
):
    measurement_path = tmp_path / "invalid.s1p"
    measurement_path.write_text(
        "14.0 0.0 0.0\n",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "inspect-s1p",
            str(measurement_path),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.out == ""
    assert "Medición inválida:" in captured.err


def test_cli_inspects_touchstone_in_english(
    tmp_path,
    capsys,
):
    measurement_path = tmp_path / "measurement.s1p"
    create_touchstone_measurement(measurement_path)

    exit_code = main(
        [
            "--language",
            "en",
            "inspect-s1p",
            str(measurement_path),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert (
        f"Measurement: {measurement_path.resolve()}"
        in captured.out
    )
    assert (
        "Frequency range: 14.000-14.300 MHz"
        in captured.out
    )
    assert "Points: 4" in captured.out
    assert (
        "Reference impedance: 50.00 ohm"
        in captured.out
    )
    assert "Approximate resonance:" in captured.out
    assert "Minimum SWR:" in captured.out
    assert captured.err == ""
    