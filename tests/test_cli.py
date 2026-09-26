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

def test_cli_warns_about_incomplete_measurement_range(
    tmp_path,
    capsys,
):
    measurement_path = tmp_path / "limited-range.s1p"
    measurement_path.write_text(
        "# MHz S RI R 50\n"
        "14.0 0.20 -0.40\n"
        "14.1 0.10 -0.30\n"
        "14.2 0.05 -0.20\n",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "inspect-s1p",
            str(measurement_path),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert (
        "Advertencia: la reactancia no cruza por cero "
        "dentro del rango medido."
        in captured.out
    )
    assert (
        "Advertencia: la ROE mínima está en un extremo "
        "del rango medido."
        in captured.out
    )
    assert captured.err == ""


@pytest.mark.parametrize("language", ["es", "en"])
@pytest.mark.parametrize(
    "rows, missing_crossing, boundary",
    [
        ("14 0.2 -0.4\n15 0.1 -0.3\n16 0.05 -0.2\n", True, True),
        ("14 0 -0.3\n15 0 0\n16 0 0.3\n", False, False),
        ("14 0 -0.3\n15 0 -0.1\n16 0 -0.2\n", True, False),
        ("14 0 -0.3\n15 0 0\n16 0 0\n", False, True),
        ("14 1 0\n", True, True),
    ],
)
def test_cli_measurement_diagnostics_are_independent_and_translated(
    tmp_path, capsys, language, rows, missing_crossing, boundary,
):
    measurement_path = tmp_path / "diagnostics.s1p"
    measurement_path.write_text("# MHz S RI R 50\n" + rows, encoding="utf-8")

    exit_code = main([
        "--language", language, "inspect-s1p", str(measurement_path),
    ])
    captured = capsys.readouterr()
    warnings = {
        "es": (
            "Advertencia: la reactancia no cruza por cero dentro del rango medido.",
            "Advertencia: la ROE mínima está en un extremo del rango medido.",
        ),
        "en": (
            "Warning: reactance does not cross zero within the measured range.",
            "Warning: minimum SWR is at the edge of the measured range.",
        ),
    }
    crossing_warning, boundary_warning = warnings[language]
    assert (crossing_warning in captured.out) is missing_crossing
    assert (boundary_warning in captured.out) is boundary
    other_language = "en" if language == "es" else "es"
    assert all(message not in captured.out for message in warnings[other_language])
    assert exit_code == 0
    assert captured.err == ""


@pytest.mark.parametrize("language", ["es", "en"])
@pytest.mark.parametrize("case", [
    "not_json", "wrong_root", "numeric_name", "missing_field",
    "wrong_nested_type", "schema", "extension", "encoding",
])
def test_validate_invalid_inputs_have_controlled_exit(tmp_path, capsys, language, case):
    data = json.loads(Path("examples/dipole-20m.antsim").read_text(encoding="utf-8"))
    if case == "numeric_name":
        data["project"]["name"] = 123
    elif case == "missing_field":
        del data["simulation"]["sweep"]["points"]
    elif case == "wrong_nested_type":
        data["simulation"] = []
    elif case == "schema":
        data["schema_version"] = 999
    elif case == "wrong_root":
        data = []
    source = tmp_path / ("invalid.json" if case == "extension" else "invalid.antsim")
    contents = b"\xff" if case == "encoding" else (
        b"not JSON" if case == "not_json" else json.dumps(data).encode("utf-8")
    )
    source.write_bytes(contents)
    assert main(["--language", language, "validate", str(source)]) == 2
    captured = capsys.readouterr()
    assert ("Proyecto inválido:" if language == "es" else "Invalid project:") in captured.err
    assert str(source) in captured.err
    assert "Traceback" not in captured.err
    assert captured.out == ""


@pytest.mark.parametrize("language", ["es", "en"])
@pytest.mark.parametrize("only_open", [False, True])
def test_cli_does_not_present_open_circuit_as_resonance(tmp_path, capsys, language, only_open):
    source = tmp_path / "open.s1p"
    source.write_text(
        "# MHz S RI R 50\n14 1 0\n" + ("15 1 0\n" if only_open else "15 0.1 0.2\n"),
        encoding="utf-8",
    )
    assert main(["--language", language, "inspect-s1p", str(source)]) == 0
    captured = capsys.readouterr()
    minimum_heading = "ROE mínima:" if language == "es" else "Minimum SWR:"
    resonance_section = captured.out.split(minimum_heading)[0]
    unavailable = (
        "Resonancia aproximada: no disponible; no hay puntos con impedancia finita."
        if language == "es" else
        "Approximate resonance: unavailable; no points have finite impedance."
    )
    assert (unavailable in resonance_section) is only_open
    assert "inf" not in resonance_section
    if not only_open:
        assert "15.000 MHz" in resonance_section
        assert "14.000 MHz" not in resonance_section
    assert minimum_heading in captured.out
    assert captured.err == ""


def create_comparison_measurement(destination: Path) -> None:
    # 13.0 y 16.0 quedan fuera del barrido del proyecto (13.5-15.5 MHz).
    # 14.0125 cae entre dos frecuencias simuladas y requiere interpolación.
    destination.write_text(
        "! AntSim comparison measurement\n"
        "# MHz S RI R 50\n"
        "13.000 0.10 0.02\n"
        "13.500 0.15 -0.05\n"
        "14.0125 0.05 0.03\n"
        "15.500 0.20 0.04\n"
        "16.000 0.10 -0.02\n",
        encoding="utf-8",
    )


def test_cli_compares_project_with_measurement(tmp_path, capsys):
    measurement_path = tmp_path / "measurement.s1p"
    create_comparison_measurement(measurement_path)

    exit_code = main(
        [
            "compare",
            "examples/dipole-20m.antsim",
            str(measurement_path),
            "--reference-impedance",
            "50",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert (
        "Comparando proyecto: Dipolo de 20 metros"
        in captured.out
    )
    assert (
        f"Archivo de medición: {measurement_path.resolve()}"
        in captured.out
    )
    assert "Impedancia de referencia: 50.00 ohm" in captured.out
    assert "Puntos comparados: 3" in captured.out
    assert (
        "Puntos medidos excluidos (fuera de rango): 2"
        in captured.out
    )
    assert (
        "Puntos que requirieron interpolación: 1"
        in captured.out
    )
    assert "Mayor diferencia de ROE:" in captured.out
    assert "Archivo CSV:" not in captured.out
    assert captured.err == ""


def test_cli_compares_project_with_measurement_in_english(
    tmp_path, capsys,
):
    measurement_path = tmp_path / "measurement.s1p"
    create_comparison_measurement(measurement_path)

    exit_code = main(
        [
            "--language",
            "en",
            "compare",
            "examples/dipole-20m.antsim",
            str(measurement_path),
            "--reference-impedance",
            "50",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert (
        "Comparing project: Dipolo de 20 metros"
        in captured.out
    )
    assert (
        f"Measurement file: {measurement_path.resolve()}"
        in captured.out
    )
    assert "Reference impedance: 50.00 ohm" in captured.out
    assert "Compared points: 3" in captured.out
    assert (
        "Measured points excluded (out of range): 2"
        in captured.out
    )
    assert (
        "Points requiring interpolation: 1" in captured.out
    )
    assert "Largest SWR difference:" in captured.out
    assert captured.err == ""


def test_cli_exports_comparison_csv(tmp_path, capsys):
    measurement_path = tmp_path / "measurement.s1p"
    create_comparison_measurement(measurement_path)
    output_path = tmp_path / "comparison.csv"

    exit_code = main(
        [
            "compare",
            "examples/dipole-20m.antsim",
            str(measurement_path),
            "--reference-impedance",
            "50",
            "--output",
            str(output_path),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert output_path.is_file()
    assert "Archivo CSV:" in captured.out
    assert str(output_path.resolve()) in captured.out
    assert captured.err == ""

    header = output_path.read_text(
        encoding="utf-8"
    ).splitlines()[0]
    assert header == (
        "frequency_mhz,simulated_resistance_ohm,"
        "simulated_reactance_ohm,measured_resistance_ohm,"
        "measured_reactance_ohm,simulated_swr,measured_swr,"
        "resistance_difference_ohm,reactance_difference_ohm,"
        "swr_difference,interpolated"
    )


def test_cli_rejects_invalid_reference_impedance_for_comparison(
    tmp_path, capsys,
):
    measurement_path = tmp_path / "measurement.s1p"
    create_comparison_measurement(measurement_path)

    exit_code = main(
        [
            "compare",
            "examples/dipole-20m.antsim",
            str(measurement_path),
            "--reference-impedance",
            "0",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.out == ""
    assert "Comparación inválida:" in captured.err


def test_cli_rejects_missing_project_for_comparison(
    tmp_path, capsys,
):
    measurement_path = tmp_path / "measurement.s1p"
    create_comparison_measurement(measurement_path)
    missing_project = tmp_path / "missing.antsim"

    exit_code = main(
        [
            "compare",
            str(missing_project),
            str(measurement_path),
            "--reference-impedance",
            "50",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.out == ""
    assert "Proyecto inválido:" in captured.err


def test_cli_rejects_invalid_measurement_for_comparison(
    tmp_path, capsys,
):
    measurement_path = tmp_path / "invalid.s1p"
    measurement_path.write_text(
        "14.0 0.0 0.0\n",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "compare",
            "examples/dipole-20m.antsim",
            str(measurement_path),
            "--reference-impedance",
            "50",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.out == ""
    assert "Medición inválida:" in captured.err


def test_cli_rejects_comparison_without_overlap(
    tmp_path, capsys,
):
    measurement_path = tmp_path / "no-overlap.s1p"
    measurement_path.write_text(
        "# MHz S RI R 50\n"
        "20.000 0.10 0.00\n"
        "21.000 0.10 0.00\n",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "compare",
            "examples/dipole-20m.antsim",
            str(measurement_path),
            "--reference-impedance",
            "50",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.out == ""
    assert "Comparación inválida:" in captured.err


def test_cli_converts_comparison_request_error_to_exit_code_2(
    tmp_path, capsys, monkeypatch,
):
    """La CLI debe reaccionar a ComparisonRequestError, no a ValueError."""
    measurement_path = tmp_path / "measurement.s1p"
    create_comparison_measurement(measurement_path)

    import antsim.cli.main as cli_main
    from antsim.application import ComparisonRequestError

    def _raise_comparison_request_error(**_kwargs):
        raise ComparisonRequestError("motivo de prueba")

    monkeypatch.setattr(
        cli_main,
        "compare_project_measurement",
        _raise_comparison_request_error,
    )

    exit_code = main(
        [
            "compare",
            "examples/dipole-20m.antsim",
            str(measurement_path),
            "--reference-impedance",
            "50",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.out == ""
    assert (
        "Comparación inválida: motivo de prueba"
        in captured.err
    )


@pytest.mark.parametrize("language", ["es", "en"])
def test_simulation_summary_handles_unavailable_resonance(capsys, language):
    from antsim.cli.main import create_reference_sweep_request, print_sweep_summary
    from antsim.domain import SweepPoint, SweepResult
    from antsim.i18n import set_language

    set_language(language)
    result = SweepResult((SweepPoint(14, complex(float("inf"), 0), float("inf")),))
    print_sweep_summary(create_reference_sweep_request(14, 15, 2), result, 2)
    output = capsys.readouterr().out
    assert ("no disponible" if language == "es" else "unavailable") in output


# ---------------------------------------------------------------------------
# import-mmana
# ---------------------------------------------------------------------------


def create_mmana_dipole(
    path: Path,
    *,
    title: str = "Dipolo importado",
    loads: str = "0,\t0\n",
    phase_degrees: float = 0.0,
    encoding: str = "utf-8",
) -> Path:
    """Reproduce un .maa mínimo compatible (00-base-dipole.maa)."""
    text = (
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
    path.write_bytes(text.encode(encoding))
    return path


IMPORT_MMANA_SWEEP_ARGS = [
    "--sweep-start", "13.5",
    "--sweep-stop", "15.5",
    "--sweep-points", "81",
    "--swr-limit", "2.0",
]


def test_cli_import_mmana_help_in_spanish(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["import-mmana", "--help"])

    output = capsys.readouterr().out

    assert exit_info.value.code == 0
    assert "import-mmana" in output


def test_cli_import_mmana_help_in_english(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["--language", "en", "import-mmana", "--help"])

    output = capsys.readouterr().out

    assert exit_info.value.code == 0
    assert "import-mmana" in output


def test_cli_imports_mmana_utf8_file(tmp_path, capsys):
    source = create_mmana_dipole(tmp_path / "dipole.maa")
    destination = tmp_path / "dipole.antsim"

    exit_code = main(
        ["import-mmana", str(source), str(destination)]
        + IMPORT_MMANA_SWEEP_ARGS
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert destination.is_file()
    assert captured.err == ""

    reloaded = load_project(destination)
    assert reloaded.metadata.name == "Dipolo importado"
    assert reloaded.sweep.points == 81


def test_cli_import_mmana_prints_spanish_summary(tmp_path, capsys):
    source = create_mmana_dipole(tmp_path / "dipole.maa")
    destination = tmp_path / "dipole.antsim"

    exit_code = main(
        ["import-mmana", str(source), str(destination)]
        + IMPORT_MMANA_SWEEP_ARGS
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "importado" in captured.out.lower()
    assert f"{source.resolve()}" in captured.out
    assert f"{destination.resolve()}" in captured.out
    assert "Frecuencia: 14.150 MHz" in captured.out
    # La geometria de prueba usa segment_override=-1 (unico modo
    # observado en el corpus real) y AzEl != 0: ambos generan
    # advertencias de por si, por lo que "compatible" no implica cero
    # advertencias (ver test_mmana_compatibility.py).
    assert "Advertencias: 2" in captured.out


def test_cli_import_mmana_prints_english_summary(tmp_path, capsys):
    source = create_mmana_dipole(tmp_path / "dipole.maa")
    destination = tmp_path / "dipole.antsim"

    exit_code = main(
        ["--language", "en", "import-mmana", str(source), str(destination)]
        + IMPORT_MMANA_SWEEP_ARGS
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "imported successfully" in captured.out
    assert "Frequency: 14.150 MHz" in captured.out
    assert "Warnings: 2" in captured.out


def test_cli_import_mmana_requires_all_sweep_options(tmp_path, capsys):
    source = create_mmana_dipole(tmp_path / "dipole.maa")
    destination = tmp_path / "dipole.antsim"

    with pytest.raises(SystemExit) as exit_info:
        main(["import-mmana", str(source), str(destination)])

    assert exit_info.value.code == 2
    assert not destination.exists()


def test_cli_import_mmana_rejects_invalid_sweep_settings(tmp_path, capsys):
    source = create_mmana_dipole(tmp_path / "dipole.maa")
    destination = tmp_path / "dipole.antsim"

    exit_code = main(
        [
            "import-mmana", str(source), str(destination),
            "--sweep-start", "16", "--sweep-stop", "13",
            "--sweep-points", "5", "--swr-limit", "2.0",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 2
    assert "Invalid sweep settings" not in captured.err  # es por defecto
    assert "barrido inválida" in captured.err
    assert not destination.exists()


def test_cli_import_mmana_rejects_incompatible_model(tmp_path, capsys):
    source = create_mmana_dipole(
        tmp_path / "dipole.maa",
        loads="1,\t0\nw1c,\t1,\t50.0,\t0.0\n",
    )
    destination = tmp_path / "dipole.antsim"

    exit_code = main(
        ["import-mmana", str(source), str(destination)]
        + IMPORT_MMANA_SWEEP_ARGS
    )

    captured = capsys.readouterr()

    assert exit_code == 2
    assert "Modelo MMANA-GAL incompatible" in captured.err
    assert "loads-present" in captured.err
    assert not destination.exists()


def test_cli_import_mmana_rejects_structurally_invalid_file(tmp_path, capsys):
    source = tmp_path / "broken.maa"
    text = (
        "Titulo\n"
        "?\n"  # marcador invalido: debe ser "*"
        "14.15\n"
    )
    source.write_text(text, encoding="utf-8")
    destination = tmp_path / "dipole.antsim"

    exit_code = main(
        ["import-mmana", str(source), str(destination)]
        + IMPORT_MMANA_SWEEP_ARGS
    )

    captured = capsys.readouterr()

    assert exit_code == 2
    assert "MMANA-GAL inválido" in captured.err
    assert not destination.exists()


def test_cli_import_mmana_rejects_missing_source_file(tmp_path, capsys):
    source = tmp_path / "does-not-exist.maa"
    destination = tmp_path / "dipole.antsim"

    exit_code = main(
        ["import-mmana", str(source), str(destination)]
        + IMPORT_MMANA_SWEEP_ARGS
    )

    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.err.strip() != ""
    assert not destination.exists()


def test_cli_import_mmana_rejects_ambiguous_legacy_encoding(tmp_path, capsys):
    source = create_mmana_dipole(
        tmp_path / "legacy.maa", title="café", encoding="cp1252",
    )
    destination = tmp_path / "dipole.antsim"

    exit_code = main(
        ["import-mmana", str(source), str(destination)]
        + IMPORT_MMANA_SWEEP_ARGS
    )

    captured = capsys.readouterr()

    assert exit_code == 2
    assert not destination.exists()


@pytest.mark.parametrize("legacy_encoding", ["cp1251", "cp1252"])
def test_cli_import_mmana_accepts_explicit_legacy_encoding(
    tmp_path, capsys, legacy_encoding,
):
    source = create_mmana_dipole(
        tmp_path / "legacy.maa", title="café", encoding="cp1252",
    )
    destination = tmp_path / "dipole.antsim"

    exit_code = main(
        [
            "import-mmana", str(source), str(destination),
            "--legacy-encoding", legacy_encoding,
        ]
        + IMPORT_MMANA_SWEEP_ARGS
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert destination.is_file()
    assert legacy_encoding in captured.out


def test_cli_import_mmana_refuses_to_overwrite_existing_destination(
    tmp_path, capsys,
):
    source = create_mmana_dipole(tmp_path / "dipole.maa")
    destination = tmp_path / "dipole.antsim"
    destination.write_text("contenido previo", encoding="utf-8")

    exit_code = main(
        ["import-mmana", str(source), str(destination)]
        + IMPORT_MMANA_SWEEP_ARGS
    )

    captured = capsys.readouterr()

    assert exit_code == 2
    assert "ya existe" in captured.err
    assert "--force" in captured.err
    assert destination.read_text(encoding="utf-8") == "contenido previo"


def test_cli_import_mmana_overwrites_with_force(tmp_path, capsys):
    source = create_mmana_dipole(tmp_path / "dipole.maa")
    destination = tmp_path / "dipole.antsim"
    destination.write_text("contenido previo", encoding="utf-8")

    exit_code = main(
        ["import-mmana", str(source), str(destination), "--force"]
        + IMPORT_MMANA_SWEEP_ARGS
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    reloaded = load_project(destination)
    assert reloaded.metadata.name == "Dipolo importado"


def test_cli_import_mmana_rejects_source_equal_to_destination(tmp_path, capsys):
    source = create_mmana_dipole(tmp_path / "dipole.maa")
    original_bytes = source.read_bytes()

    exit_code = main(
        ["import-mmana", str(source), str(source), "--force"]
        + IMPORT_MMANA_SWEEP_ARGS
    )

    captured = capsys.readouterr()

    assert exit_code == 2
    assert source.read_bytes() == original_bytes


def test_cli_import_mmana_displays_warnings(tmp_path, capsys):
    source = create_mmana_dipole(tmp_path / "dipole.maa", phase_degrees=45.0)
    destination = tmp_path / "dipole.antsim"

    exit_code = main(
        ["import-mmana", str(source), str(destination)]
        + IMPORT_MMANA_SWEEP_ARGS
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Advertencias: 3" in captured.out
    assert "source-phase-nonzero" in captured.out


def test_cli_import_mmana_does_not_require_pynec(tmp_path, capsys, monkeypatch):
    from antsim.engines import pynec as pynec_module

    def _fail_init(self):
        raise AssertionError(
            "PyNecEngine no debe instanciarse para import-mmana."
        )

    monkeypatch.setattr(pynec_module.PyNecEngine, "__init__", _fail_init)

    source = create_mmana_dipole(tmp_path / "dipole.maa")
    destination = tmp_path / "dipole.antsim"

    exit_code = main(
        ["import-mmana", str(source), str(destination)]
        + IMPORT_MMANA_SWEEP_ARGS
    )

    assert exit_code == 0
    assert destination.is_file()
