"""Procesos limpios para que imports previos de pytest no oculten el defecto."""

import subprocess
import sys
from pathlib import Path

import pytest


def run_without_pynec(code, error_type="ModuleNotFoundError"):
    blocker = '''
import importlib.abc
import sys
class MissingPyNec(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "PyNEC" or fullname.startswith("PyNEC."):
            raise ModuleNotFoundError("PyNEC unavailable for test")
sys.meta_path.insert(0, MissingPyNec())
'''
    blocker = blocker.replace("raise ModuleNotFoundError", f"raise {error_type}")
    return subprocess.run(
        [sys.executable, "-B", "-c", blocker + code],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=30,
    )


def test_cli_and_engine_contract_import_without_pynec():
    result = run_without_pynec('''
import antsim.cli.main
from antsim.engines import SimulationEngine
assert "PyNEC" not in sys.modules
assert "antsim.engines.pynec" not in sys.modules
''')
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("language", ["es", "en"])
@pytest.mark.parametrize("error_type", ["ModuleNotFoundError", "OSError"])
def test_doctor_reports_missing_pynec_without_traceback(language, error_type):
    result = run_without_pynec(f'''
from antsim.cli.main import main
sys.exit(main(["--language", "{language}", "doctor"]))
''', error_type=error_type)
    assert result.returncode == 1
    assert "PyNEC: ERROR" in result.stdout
    assert "unavailable for test" in result.stdout
    assert "Traceback" not in result.stderr


def test_validating_project_does_not_require_pynec():
    result = run_without_pynec('''
from antsim.cli.main import main
sys.exit(main(["--language", "en", "validate", "examples/dipole-20m.antsim"]))
''')
    assert result.returncode == 0, result.stderr
    assert "Valid project:" in result.stdout


def test_public_engine_import_remains_available_but_loads_on_demand():
    result = run_without_pynec('''
import antsim.engines
try:
    from antsim.engines import PyNecEngine
except ModuleNotFoundError as error:
    assert "unavailable for test" in str(error)
else:
    raise AssertionError("The explicit engine request must load PyNEC")
''')
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("arguments", [
    ["simulate-dipole"],
    ["sweep-dipole", "--points", "2"],
    ["simulate", "examples/dipole-20m.antsim"],
    ["sweep", "examples/dipole-20m.antsim"],
])
def test_simulation_commands_request_engine_only_when_invoked(arguments):
    result = run_without_pynec(f'''
from antsim.cli.main import main
assert "antsim.engines.pynec" not in sys.modules
try:
    main({arguments!r})
except ModuleNotFoundError as error:
    assert "unavailable for test" in str(error)
else:
    raise AssertionError("Simulation did not request the engine")
''')
    assert result.returncode == 0, result.stderr
