import pytest

from antsim.cli.main import main


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
    assert "Barrido: 13.000–16.000 MHz" in output
    assert "Puntos: 13" in output
    assert "Resonancia aproximada:" in output
    assert "ROE mínima:" in output


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

    