# AGENTS.md

## Project overview

YAAS (Yet Another Antenna Simulator) is an open-source antenna
simulator written in Python.

AntSim was the development name used for this project up to and
including version 0.2.0. The rename to YAAS happened before the first
external publication (no remote repository, no published package and
no external users yet), so there is no `antsim`/`.antsim` alias or
compatibility layer: see `docs/decisions/0008-rename-to-yaas.md` for
the full decision record.

Its current simulation engine is PyNEC/NEC2++. The main objective is
to provide simulation, measurement analysis and interoperability tools
for radio amateurs through a CLI and a future desktop GUI.

The architecture deliberately separates:

- domain models and calculations;
- simulation engines;
- project serialization;
- importers;
- exporters;
- reusable application-layer use cases (for example, simulation/
  measurement comparison);
- command-line presentation;
- the future graphical interface.

Do not introduce dependencies between presentation code and the core
domain.

## Current project status

Implemented capabilities include:

- impedance and SWR calculations;
- single-frequency simulations;
- linear frequency sweeps;
- approximate resonance detection;
- minimum SWR detection;
- sampled SWR bandwidth calculation;
- versioned `.yaas` project files;
- CSV sweep export;
- NEC single-frequency export;
- NEC linear-sweep export;
- Touchstone S1P import;
- Touchstone `RI`, `MA` and `DB` formats;
- Hz, kHz, MHz and GHz frequency units;
- S11 conversion to impedance and SWR;
- simulation/measurement comparison (`compare_sweeps`,
  `ComparisonPoint`, `SweepComparison`) with linear resistance/
  reactance interpolation over the measured grid inside the simulated
  range, and no extrapolation;
- a reusable application-layer comparison workflow
  (`yaas.application.comparison.compare_project_measurement`);
- comparison CSV export;
- CLI `compare` command;
- MMANA-GAL (`.maa`) import: structural parsing, encoding detection,
  semantic compatibility analysis, conversion to `AntennaProject`
  using a uniform `lambda/160` NEC segmentation density (ADR 0007), a
  reusable and atomic application-layer import workflow, and the CLI
  `import-mmana` command;
- an environment model (`FreeSpaceEnvironment`,
  `PerfectGroundEnvironment`, `RealGroundEnvironment` with
  `RealGroundModel.SOMMERFELD_NORTON`), propagated through
  `SimulationRequest`/`SweepRequest`/`AntennaProject`, with domain
  validation of conductors against the z=0 ground plane and of
  permittivity/conductivity/model for real ground (permittivity must
  be finite and > 0; conductivity must be finite and >= 0, with `0.0`
  allowed as a lossless dielectric rather than "no ground"; `model`
  must be an actual `RealGroundModel` instance, never a raw string or
  integer);
- perfect-ground support in `PyNecEngine`
  (`geometry_complete(1)`/`gn_card(1, ...)`) and in the NEC exporters
  (`GE 1`/`GN 1 0 0 0 0 0 0 0`, always after the last `GW` and before
  `EX`/`FR`), alongside byte-identical free-space output (`GE 0`, no
  `GN` card);
- real-ground (Sommerfeld-Norton) support in `PyNecEngine`
  (`geometry_complete(1)`/`gn_card(2, 0, relative_permittivity,
  conductivity_s_per_m, 0, 0, 0, 0)`) and in the NEC exporters
  (`GE 1`/`GN 2 0 0 0 relative_permittivity conductivity_s_per_m
  0 0 0 0` — ten fields, four ground-type/radial-count integers
  followed by six ground-parameter floats, distinct from
  `gn_card()`'s eight positional arguments and never copied literally
  from it); `PyNecEngine.simulate_sweep` creates one NEC2++ context
  per frequency for real ground instead of reusing a single context
  for the whole sweep (a single reused context was found to introduce
  a small but measurable discrepancy versus independent per-frequency
  results for geometries close to the ground plane), while free space
  and perfect ground keep the historical single-context sweep;
- radiation-pattern domain models (`AngularSweep`,
  `RadiationPatternRequest`, `RadiationPatternSample`,
  `RadiationPatternResult`), which reject non-positive angular counts
  and `theta > 90` over any ground plane before PyNEC is reached, and
  single-frequency pattern calculation through
  `PyNecEngine.simulate_radiation_pattern` (total gain in dBi as a
  `(n_theta, n_phi)` matrix; the NEC `-999.99` null sentinel becomes
  `None`);
- radiation-pattern exports: NEC with a textual `RP` card after `FR`
  (`radiation_pattern_request_to_nec`, `export_radiation_pattern_nec`)
  and a flat CSV (`radiation_pattern_to_csv`,
  `export_radiation_pattern_csv`; one row per direction, null gains as
  empty cells);
- CLI `pattern` command (summary, plus `--csv` to save the same result
  without recalculating) and `export-nec --pattern` (mutually
  exclusive with `--sweep`, never runs PyNEC), with the schema 4
  example `examples/dipole-20m-radiation-pattern.yaas`; the GUI can
  also open a project and calculate and draw its pattern (see below);
- `.yaas` schema version 4 (ADR 0009,
  `docs/decisions/0009-add-radiation-pattern-schema-v4.md`), with
  `simulation.environment` mandatory (`free_space`, `perfect_ground`
  or `real_ground`) and an optional `simulation.radiation_pattern`
  (`theta`/`phi` axes, each with exactly `start_deg`, `count` and
  `step_deg`); the reader accepts schema 1, 2, 3 and 4 and keeps the
  original `schema_version` in memory; schema 1 files are interpreted
  as free space, schema 2 files admit `free_space`/`perfect_ground`
  only, and schema 1, 2 and 3 files reject `radiation_pattern`; the
  writer always emits schema 4, so re-saving an older project migrates
  it (without a pattern) and never mutates the loaded object;
- Spanish and English CLI output;
- standalone Windows executable built with PyInstaller;
- an experimental GUI skeleton (phase 9, in progress): optional `gui`
  extra (`PySide6-Essentials` and Matplotlib), a separate `yaas-gui`
  entry point (`yaas-gui [PROJECT]`) and a minimal window that opens
  and shows `.yaas` projects of schema 1-4 through a
  `ProjectController` over `yaas.application.open_project`, and
  calculates the open project's radiation pattern in the background
  (*Calculate > Radiation pattern*: `SimulationRunner`, a `QThread`
  with a worker `QObject`, running
  `yaas.application.calculate_radiation_pattern` with a `PyNecEngine`
  created inside the worker), drawing the first available cut on a
  "Radiation pattern" tab backed by a Matplotlib adapter (azimuth as a
  polar plot, vertical as cartesian, PNG/SVG/PDF export); it does not
  edit or save projects, and has no cut selector yet.

NEC export was externally validated with 4nec2 5.9.3, including
Sommerfeld-Norton real ground
(`docs/validation/real-ground-dipole-4nec2.md`).

YAAS's own code is licensed under GPL-3.0-only (`LICENSE`), a
definitive decision recorded with its evidence in
`docs/decisions/0004-project-license.md` (ADR 0004). Third-party
dependencies and their licenses are inventoried in
`THIRD_PARTY_NOTICES.md`. The first public release will publish only
this repository's source code; `dist\yaas.exe` must not be published
as a downloadable release asset until the compliance package described
in `docs/packaging/windows-release-compliance.md` is complete, because
it embeds PyNEC/NEC2++ and Eigen.

## Development environment

Primary supported development environment:

- Windows x64
- Python 3.13
- PowerShell
- Git
- Visual C++ Build Tools
- Visual Studio Code

Project location normally used during development:

```text
C:\dev\antenna-simulator
```

The source code uses the `src` layout:

```text
src\yaas
```

The existing virtual environment is:

```text
.venv
```

Activate it in PowerShell with:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install the project in editable mode with development dependencies:

```powershell
python -m pip install -e ".[dev]"
```

Do not recreate or replace the virtual environment unless explicitly
requested.

## Required initial inspection

Before modifying code:

1. Read this file.
2. Read `README.md`.
3. Read `pyproject.toml`.
4. Inspect the relevant documents in:
   - `docs/decisions`
   - `docs/phases`
   - `docs/validation`
5. Inspect the relevant source and test modules.
6. Run:

```powershell
git status
```

Preserve all existing user changes.

If the working tree is not clean, identify which changes already exist
before editing. Do not discard or overwrite unrelated modifications.

## Architecture boundaries

### Domain

Location:

```text
src/yaas/domain
```

Responsibilities:

- immutable domain models;
- electrical calculations;
- validation of domain invariants;
- engine-independent simulation requests and results;
- measured sweep models;
- future comparison models.

The domain must not import:

- CLI modules;
- GUI modules;
- PyNEC;
- filesystem-specific importers or exporters.

Prefer pure functions for electrical calculations.

Use frozen dataclasses for immutable domain values.

Validate invariants in `__post_init__`.

### Simulation engines

Location:

```text
src/yaas/engines
```

Responsibilities:

- adapt domain requests to simulation engines;
- execute simulations;
- convert engine output into domain results.

PyNEC must remain behind the engine adapter.

Do not modify the PyNEC or NEC2++ source code.

Do not expose NumPy values outside the adapter when native Python
numbers are sufficient.

### Projects

Location:

```text
src/yaas/projects
```

Responsibilities:

- load and save `.yaas` files;
- validate the schema version;
- convert project data to domain requests.

The current schema is version 4 (see ADR 0009,
`docs/decisions/0009-add-radiation-pattern-schema-v4.md`): the reader
accepts versions 1-4, the writer always emits version 4, and
`simulation.radiation_pattern` is optional in version 4 only. The
historical examples in `examples/` intentionally remain at schema 1, 2
and 3; do not rewrite them.

Do not change the `.yaas` schema without:

- explicit authorization;
- a documented schema-version decision;
- backward-compatibility analysis;
- migration or compatibility tests.

### Importers

Location:

```text
src/yaas/importers
```

Responsibilities:

- read external formats;
- validate external input;
- convert external data into domain models;
- report format errors clearly.

Current Touchstone scope:

- one-port `.s1p` files;
- S parameters;
- `RI`, `MA` and `DB`;
- Hz, kHz, MHz and GHz;
- a single reference impedance.

Do not silently accept unsupported Touchstone features.

NEC import is postponed and must not be implemented unless explicitly
requested.

Current MMANA-GAL (`.maa`) scope:

- structural parsing, independent of localized or irregular
  section-header text (`src/yaas/importers/mmana.py`);
- encoding detection: UTF-8 (with or without BOM) is preferred;
  CP1251/CP1252 are auto-resolved only when a decisive byte settles
  the ambiguity; a genuinely ambiguous file requires an explicit
  `legacy_encoding` and is never guessed (see
  `docs/research/mmana-format-characterization.md`);
- semantic compatibility analysis, reporting both blocking errors and
  non-blocking warnings (`src/yaas/importers/mmana_compatibility.py`).

An incompatible MMANA-GAL document is always rejected with
`MmanaCompatibilityError`; it is never imported partially or ignored
silently.

MMANA-GAL import does not support yet: more than one source,
concentrated loads, non-free-space environments, or any per-conductor
segmentation mode other than `segment_override=-1` (the only mode
observed in the real corpus studied so far). Do not extend this scope
without explicit authorization.

### Exporters

Location:

```text
src/yaas/exporters
```

Responsibilities:

- export domain information to external formats;
- avoid simulation-engine dependencies;
- return the path of generated files when appropriate.

Current formats:

- CSV sweep results;
- NEC single-frequency models;
- NEC linear frequency sweeps;
- NEC single-frequency radiation patterns (an `RP` card after `FR`:
  ten fields, `I4` written as the single token `0000`, unlike the
  thirteen arguments of `PyNEC.rp_card()`; no `XQ`);
- CSV radiation patterns (`frequency_mhz,theta_deg,phi_deg,gain_db`).

Preserve compatibility with the NEC subset already validated using
4nec2.

### Application

Location:

```text
src/yaas/application
```

Responsibilities:

- reusable use-case functions that orchestrate domain, project and
  engine APIs (for example, simulating a project's sweep and
  comparing it against a measurement in
  `yaas.application.comparison.compare_project_measurement`);
- translate expected domain failures into application-specific
  exceptions (for example, `ComparisonRequestError`, raised only from
  the `ValueError` produced by `compare_sweeps`) while leaving
  simulation-engine failures unmodified;
- another example: converting a compatible MMANA-GAL document into an
  `AntennaProject`
  (`yaas.application.mmana_conversion.convert_mmana_to_project`,
  `derive_nec_segments`) and atomically writing it as a project file
  (`yaas.application.mmana_import.prepare_mmana_import`,
  `write_mmana_import`), reused as-is by the CLI `import-mmana`
  command;
- radiation patterns (`yaas.application.radiation_pattern`):
  `prepare_radiation_pattern_request` (validates the project without
  any engine and raises `MissingRadiationPatternError`, a
  `ValueError`, when it has no pattern), `calculate_radiation_pattern`
  (runs the engine once and returns a `RadiationPatternAnalysis` with
  the result and its `RadiationPatternSummary`),
  `summarize_radiation_pattern` (valid/null counts and the
  deterministic maximum: first theta-major sample, absolute 1e-9 dB
  tie tolerance) and `export_project_radiation_pattern_nec`; CSV
  export of a computed result needs no wrapper and uses
  `yaas.exporters.export_radiation_pattern_csv` directly. The CLI
  `pattern` and `export-nec --pattern` commands only format, translate
  and map errors to exit codes;
- opening a project (`yaas.application.project`): `open_project(path)`
  returns a frozen `OpenedProject(path, project)`; it converts the path
  with `Path(path)` (no resolving), delegates exclusively to
  `load_project`, keeps the original `schema_version`, never migrates
  or saves, and lets `ProjectFormatError` and `OSError` propagate
  untranslated. The GUI's `ProjectController` uses it.

This layer may import:

- domain models and functions such as `compare_sweeps`;
- the `SimulationEngine` protocol;
- project models;
- exporters (for example, `export_radiation_pattern_nec`).

This layer must not import:

- `argparse`;
- CLI modules;
- `gettext`;
- a concrete simulation engine (for example, `PyNecEngine`);
- numpy or any GUI or plotting library.

The CLI and the future GUI must call this layer instead of
reimplementing the same orchestration.

### CLI

Location:

```text
src/yaas/cli
```

Responsibilities:

- parse arguments;
- invoke application-layer use cases instead of orchestrating engines
  and projects directly;
- present translated messages;
- convert expected user errors into appropriate exit codes.

The CLI must not contain electrical calculations or file-format parsing
logic.

Keep existing commands backward compatible unless a breaking change is
explicitly authorized.

Expected exit-code convention:

- `0`: success;
- `1`: unhealthy environment or execution failure;
- `2`: invalid user input or invalid external file.

### Future GUI

The future GUI will use PySide6 (with Matplotlib for 2D plots; see
ADR 0010, `docs/decisions/0010-adopt-pyside6-matplotlib-gui.md`). Only
a skeleton exists (`src/yaas/gui`, phase 9): Qt and Matplotlib are
imported lazily and only inside `yaas.gui`; no other package may
import PySide6 or Matplotlib, no plotting logic may live in the domain
or application layers, and `yaas`, `yaas.cli` and every core layer
must keep working without the optional `gui` extra.

GUI code must call the same domain, project, importer, exporter,
engine and application-layer APIs used by the CLI (for example,
`yaas.application.comparison.compare_project_measurement`).

Do not duplicate simulation, validation or conversion logic inside GUI
widgets.

## Internationalization

English is the source language for translatable CLI messages.

Spanish translations use GNU gettext.

Translation files are stored under:

```text
src/yaas/locales
```

When modifying user-visible CLI messages:

1. Update the source English message.
2. Update the Spanish `.po` catalog.
3. Compile the `.mo` catalog.
4. Test both Spanish and English output.

Compile translations with:

```powershell
pybabel compile `
    --directory src\yaas\locales `
    --domain yaas `
    --locale es
```

Do not translate:

- command names;
- option names;
- JSON keys;
- CSV headers;
- Touchstone tokens;
- NEC cards;
- filesystem paths.

Avoid Unicode technical punctuation in console output when an ASCII
equivalent exists. Prefer:

```text
<=
-
```

instead of Unicode variants that may fail in Windows console
encodings.

Files containing PowerShell scripts must preserve the encoding already
used by the project. `scripts/build_windows.ps1` is expected to remain
compatible with Windows PowerShell 5.1.

## Code style

Follow the style already present in the repository.

General rules:

- Use type annotations for public functions and methods.
- Use descriptive names.
- Keep functions focused.
- Prefer explicit code over clever abstractions.
- Avoid unnecessary inheritance.
- Avoid global mutable state.
- Avoid unrelated refactors.
- Keep public APIs small.
- Preserve existing imports and exports unless change is required.
- Update `__all__` when adding a public package API.
- Use `pathlib.Path` for filesystem paths.
- Use UTF-8 for text data unless a format requires otherwise.
- Include a final newline in text files.
- Do not add dependencies without explicit approval.
- Do not change package versions unless explicitly requested.
- Do not rename the application unless explicitly requested.

Internal exception messages may provide technical detail, but
user-facing CLI messages must remain clear.

## Testing requirements

The test framework is pytest.

Run focused tests while developing.

Examples:

```powershell
python -m pytest `
    tests\unit\test_measurement_models.py `
    -v
```

```powershell
python -m pytest `
    tests\unit\test_touchstone_importer.py `
    -v
```

```powershell
python -m pytest `
    tests\unit\test_mmana_compatibility.py `
    tests\unit\test_mmana_conversion.py `
    tests\unit\test_mmana_import_workflow.py `
    -v
```

Before completing any code task, run the complete suite:

```powershell
python -m pytest
```

Every new capability must include tests for:

- successful operation;
- invalid input;
- boundary conditions;
- domain invariants;
- appropriate CLI exit codes, when applicable;
- Spanish and English output, when user-visible messages change.

Use pytest's `tmp_path` fixture for temporary files.

Unit tests must not require PyNEC unless they are explicitly integration
tests.

Avoid relying on user-specific absolute paths in tests.

Do not weaken, skip or delete a failing test merely to make the suite
pass.

When a test fails:

1. identify whether the implementation or expectation is wrong;
2. explain the cause;
3. correct the appropriate side;
4. run the focused test again;
5. run the complete suite.

Avoid duplicate test filenames in different non-package directories,
because pytest may import them with the same module name.

## Windows executable

The Windows executable is built with:

```powershell
.\scripts\build_windows.ps1
```

The expected output is:

```text
dist\yaas.exe
```

Run the build script when changing:

- runtime dependencies;
- PyInstaller configuration;
- CLI commands;
- translations or package data;
- project loading;
- importers used by the executable;
- exporters used by the executable;
- engine-loading behavior.

The build script must clean up its temporary smoke-test files through
`try`/`finally`.

Preserve Windows PowerShell 5.1 compatibility.

Before editing nested `try`/`finally` blocks, inspect their complete
structure. After editing, syntax can be checked with:

```powershell
$errors = $null

[System.Management.Automation.Language.Parser]::ParseFile(
    (Resolve-Path .\scripts\build_windows.ps1),
    [ref]$null,
    [ref]$errors
) | Out-Null

$errors
```

If no errors are displayed, the script is syntactically valid.

## Linux executable (experimental)

An experimental, ephemeral Linux executable is built with:

```bash
bash scripts/build_linux.sh
```

The expected output is `dist/yaas`. Unlike
`scripts/build_windows.ps1`, this script does not require an
activated virtual environment: it targets a CI job where
`actions/setup-python` already resolves `python`/`pip` on `PATH`
without a local `.venv` to activate.

This build is verified automatically in CI (`.github/workflows/tests.yml`,
job `build-linux`, `runs-on: ubuntu-24.04`, gated behind
`test-ubuntu-24`), and can be reproduced locally following
`docs/building-linux.md`. It is not published as a release asset and
is not part of any binary-distribution compliance package yet (see
`docs/packaging/windows-release-compliance.md` for the equivalent,
still-pending policy on the Windows side).

## GUI executables (experimental)

The GUI has its own, separate executables, so the CLI executable never
carries Qt:

```powershell
.\scripts\build_gui_windows.ps1
```

```bash
bash scripts/build_gui_linux.sh
```

The expected outputs are `dist\yaas-gui.exe` (onefile, windowed) and
`dist/yaas-gui`. Both scripts require the `gui` extra
(`python -m pip install -e ".[dev,gui]"`), do not require an activated
virtual environment, run the GUI tests with `QT_QPA_PLATFORM=offscreen`,
clean only `dist/yaas-gui[.exe]`, `build/yaas-gui/` and
`yaas-gui.spec`, include Matplotlib and numpy, declare
`matplotlib.backends.backend_svg` and `backend_pdf` as hidden imports
(`savefig` loads them dynamically, so without them SVG/PDF export
fails only in the frozen executable), include PyNEC (the GUI
calculates patterns; `yaas.engines.pynec` is declared as a hidden
import because it is only imported inside the worker), exclude
`PySide6.QtNetwork` and pyqtgraph, and check `--version`,
`--smoke-test` and `--smoke-test --smoke-export` (PNG, SVG and PDF
into a temporary directory that is always removed), `--smoke-test
PROJECT` with the four examples (schema 1-4), which must succeed, and
with a missing and a damaged project, which must fail, and
`--smoke-test --smoke-calculate` (a real PyNEC calculation in the
worker) with the schema 4 example, exporting the drawn cut, which must
succeed, and with the schema 1 example (no pattern), which must fail.
They also fail if the PyInstaller analysis picked up pyqtgraph, the
`QtNetwork` module or any library from an unrelated installation such
as XAMPP, or if it did not pick up PyNEC (`PyNEC` and its `_PyNEC`
extension), and report the executable size. The windowed Windows executable has no console, so its
checks use exit codes; text output is checked before freezing. They
run in CI (jobs `test-gui-windows` and `test-gui-ubuntu-24`) and are
never published (see `docs/packaging/gui-release-compliance.md`).

## Git workflow

Before editing:

```powershell
git status
```

After editing:

```powershell
git diff --stat
git diff
```

Do not stage or commit changes unless explicitly requested.

Do not use destructive commands such as:

```text
git reset --hard
git checkout -- .
```

Do not remove or overwrite user changes.

Prefer small, cohesive commits.

Commit-message examples:

```text
feat: compare simulated and measured sweeps
fix: handle open-circuit S11 measurements
test: cover Touchstone frequency alignment
docs: record comparison phase decisions
build: verify comparison command in Windows executable
```

Suggested branch naming:

```text
feat/comparison-model
feat/comparison-cli
fix/touchstone-parser
docs/comparison-phase
```

## Agent workflow

For every implementation task, follow this sequence.

### Before changes

1. Inspect the relevant files.
2. Check Git status.
3. Explain the proposed implementation.
4. Identify the files expected to change.
5. Call out assumptions and compatibility risks.

### During changes

1. Make the smallest cohesive change.
2. Preserve unrelated user edits.
3. Add or update tests with the implementation.
4. Avoid expanding the task without authorization.
5. Report blockers instead of inventing missing requirements.

### After changes

1. Review the diff.
2. Run focused tests.
3. Run the complete suite.
4. Run the Windows build when required.
5. Summarize:
   - files changed;
   - behavior added or corrected;
   - tests executed;
   - test results;
   - known limitations;
   - recommended next step.

Do not create a commit unless explicitly requested.

## Human review

All agent-generated changes require human review before integration.

Present code changes in a way that allows the user to understand:

- what changed;
- why it changed;
- how it was tested;
- what remains unsupported.

The user is technically experienced but is returning to some parts of
the Python ecosystem after time away. Explanations should be clear,
incremental and concrete without assuming familiarity with every tool.

## Current roadmap

### Completed: simulation and measurement comparison

Implemented:

- `ComparisonPoint` and `SweepComparison`
  (`src/yaas/domain/comparison.py`);
- `compare_sweeps`, with a mandatory, resistive, positive, finite
  common reference impedance (ADR 0005);
- linear interpolation of resistance and reactance over the measured
  grid inside the simulated range; SWR is recalculated after
  interpolating impedance, never interpolated directly;
- no extrapolation: measurements outside the simulated range are
  excluded and counted, never silently dropped;
- a reusable application-layer workflow,
  `yaas.application.comparison.compare_project_measurement`, that
  orchestrates project loading, engine simulation and
  `compare_sweeps`;
- `ComparisonRequestError`, which wraps only the `ValueError` raised
  by `compare_sweeps` and leaves simulation-engine failures
  unmodified;
- comparison CSV export (`yaas.exporters.comparison_csv`);
- the CLI `compare` command.

See `docs/phases/phase-5-comparison.md`,
`docs/decisions/0005-sweep-comparison.md` (ADR 0005) and
`docs/decisions/0006-finite-resonance-candidates.md` (ADR 0006).

### Completed: MMANA-GAL import

Implemented:

- structural parsing of `.maa` files and an encoding-detection policy
  that never guesses a genuinely ambiguous CP1251/CP1252 file
  (`src/yaas/importers/mmana.py`);
- semantic compatibility analysis, distinguishing blocking errors from
  non-blocking warnings (`src/yaas/importers/mmana_compatibility.py`);
- a uniform NEC segmentation density (`lambda/160`) selected through a
  reproducible convergence study, and
  `yaas.application.mmana_conversion.derive_nec_segments` /
  `convert_mmana_to_project`, which apply it and refuse to convert any
  document `analyze_mmana_compatibility` marks incompatible;
- a reusable, atomic application-layer import workflow
  (`yaas.application.mmana_import.prepare_mmana_import`,
  `write_mmana_import`), which never leaves a partially written
  `.yaas` file behind;
- the bilingual CLI `import-mmana` command, which requires its four
  sweep options explicitly (the MMANA-GAL format carries no sweep
  definition of its own) and maps compatibility issue codes to
  translatable messages entirely inside the CLI layer (the codes
  themselves are never translated).

See `docs/phases/phase-6-mmana-import.md`,
`docs/research/mmana-format-characterization.md`,
`docs/research/nec-segmentation-convergence.md` and
`docs/decisions/0007-use-uniform-nec-segmentation.md` (ADR 0007).

### Completed: perfect ground (phase 7A)

Implemented:

- `FreeSpaceEnvironment` and `PerfectGroundEnvironment`
  (`src/yaas/domain/models.py`), propagated unchanged through
  `SimulationRequest`, `SweepRequest` and `AntennaProject`;
- a domain-level invariant rejecting any conductor whose endpoints
  cross or lie below the z=0 ground plane, or lie entirely on it,
  whenever the environment is not free space;
- `PyNecEngine` support for perfect ground
  (`geometry_complete(1)` + `gn_card(1, 0, 0, 0, 0, 0, 0, 0)`),
  verified empirically against the reference dipole via image theory
  before implementation
  (`docs/research/nec-ground-configuration.md`);
- `.yaas` schema version 2: `simulation.environment` is mandatory
  (`{"kind": "free_space"}` or `{"kind": "perfect_ground"}`); schema 1
  files (without that key) keep loading, are interpreted as free
  space, and keep reporting `schema_version == 1` in memory; the
  writer always emits schema 2, so re-saving a schema-1 project
  migrates it;
- NEC export of both environments: free space keeps its exact
  historical output (`GE 0`, no `GN` card); perfect ground adds
  `GE 1` followed by `GN 1 0 0 0 0 0 0 0`, always after every `GW`
  and before `EX`/`FR`;
- the example project
  `examples/monopole-20m-perfect-ground.yaas` and its
  cross-validation against image theory and 4nec2 V5.9.3
  (`docs/validation/monopole-perfect-ground-4nec2.md`);
- Windows executable smoke tests covering both the historical
  free-space project and the new perfect-ground one.

See `docs/phases/phase-7a-perfect-ground.md`,
`docs/research/nec-ground-configuration.md` and
`docs/validation/monopole-perfect-ground-4nec2.md`.

### Completed: real ground (phase 7B)

Implemented:

- `RealGroundModel` (`src/yaas/domain/models.py`), a `str, Enum`
  with a single member so far, `SOMMERFELD_NORTON`;
- `RealGroundEnvironment` (frozen dataclass, added to the
  `Environment` union), with `relative_permittivity` (finite, > 0),
  `conductivity_s_per_m` (finite, >= 0; `0.0` allowed as a lossless
  dielectric) and `model` (must be a `RealGroundModel` instance; no
  silent conversion from a string, integer or unknown enum); the
  existing z=0 ground-plane conductor validation applies to it
  automatically, since that check only special-cases
  `FreeSpaceEnvironment`;
- `PyNecEngine` support for Sommerfeld-Norton
  (`geometry_complete(1)` + `gn_card(2, 0, relative_permittivity,
  conductivity_s_per_m, 0, 0, 0, 0)`), and a dedicated sweep strategy:
  free space and perfect ground keep reusing a single NEC2++ context
  for the whole sweep, but real ground creates one context per
  frequency (`PyNecEngine._simulate_sweep_per_frequency`), because a
  single reused context was found to introduce a small but measurable
  discrepancy versus independently computed per-frequency results for
  geometries close to the ground plane
  (`docs/research/nec-real-ground.md`); the per-point strategy costs
  no more in practice, since the Sommerfeld-Norton computation itself
  dominates the time either way (~40 ms/point);
- `.yaas` schema version 3: `simulation.environment` still
  mandatory, now admitting a third `kind`, `real_ground`, with
  `model`, `relative_permittivity` and `conductivity_s_per_m`; schema
  1 and 2 files keep loading exactly as before (schema 2 still
  rejects `real_ground`), and the writer always emits schema 3, so
  re-saving a schema 1 or 2 project migrates it;
- NEC export of real ground: `GE 1` followed by `GN 2 0 0 0
  relative_permittivity conductivity_s_per_m 0 0 0 0` — ten fields
  (four ground-type/radial-count integers, then six ground-parameter
  floats), always after the last `GW` and before `EX`/`FR`; this
  differs from `PyNEC.gn_card()`'s eight positional arguments
  (`ground_type, rad_wire_count, F1..F6`, no I3/I4), which must not be
  copied literally into the NEC card text;
- the example project `examples/dipole-20m-real-ground.yaas`
  (schema 3, horizontal dipole 10 m above the ground plane) and its
  cross-validation against 4nec2 V5.9.3
  (`docs/validation/real-ground-dipole-4nec2.md`);
- Windows executable smoke tests covering the free-space,
  perfect-ground and real-ground example projects (schema 1, 2 and 3),
  including field-by-field validation of the `GN` card, not just
  substring checks.

See `docs/phases/phase-7b-real-ground.md`,
`docs/research/nec-real-ground.md` and
`docs/validation/real-ground-dipole-4nec2.md`.

### Completed: radiation patterns (phase 8)

Implemented:

- the research and the external 4nec2 validation of the angular
  convention, the safe `theta` domain and the `(n_theta, n_phi)`
  orientation (`docs/research/nec-radiation-patterns.md`,
  `docs/validation/radiation-patterns-4nec2.md`);
- the domain models `AngularSweep`, `RadiationPatternRequest`,
  `RadiationPatternSample` and `RadiationPatternResult`;
- `SimulationEngine.simulate_radiation_pattern` and its
  single-frequency `PyNecEngine` implementation (one fresh NEC2++
  context per request; `fr_card -> ex_card -> rp_card`, without
  `xq_card`);
- `.yaas` schema version 4 with an optional
  `simulation.radiation_pattern`, `RadiationPatternSettings` and
  `AntennaProject.to_radiation_pattern_request()` (ADR 0009,
  `docs/decisions/0009-add-radiation-pattern-schema-v4.md`);
- NEC export with a textual `RP` card and CSV export of a
  `RadiationPatternResult`;
- the bilingual CLI `pattern` command (with `--csv`) and
  `export-nec --pattern`, the schema 4 example
  `examples/dipole-20m-radiation-pattern.yaas`, and Windows/Linux
  executable smoke tests for all of them;
- a deterministic direction of maximum: gains within an absolute
  1e-9 dB count as tied and the first theta-major sample wins (floating
  point noise of ~3.6e-15 dB between `theta=0` and `theta=180` made
  Ubuntu 24.04 report a different direction than Windows).

Not included (see the limits in the phase document): plots, the GUI,
frequency sweeps of patterns, several patterns per project, RP import,
conductor losses, and polarization or `E_theta`/`E_phi` components.

See `docs/phases/phase-8-radiation-patterns.md`,
`docs/research/nec-radiation-patterns.md`,
`docs/validation/radiation-patterns-4nec2.md` and
`docs/decisions/0009-add-radiation-pattern-schema-v4.md`.

### In progress: GUI foundation (phase 9)

Architecture decided in ADR 0010
(`docs/decisions/0010-adopt-pyside6-matplotlib-gui.md`), based on
`docs/research/gui-radiation-visualization.md`.

Implemented so far (the foundation only):

- `PySide6-Essentials` verified to be enough for `QtCore`/`QtGui`/
  `QtWidgets` (6.11.2, Python 3.13, Windows; it only pulls
  `shiboken6`); optional extra `gui = ["PySide6-Essentials>=6.11.2,<7",
  "matplotlib>=3.11.2,<4"]` (Matplotlib 3.11.2 verified with the
  `QtAgg` backend over PySide6-Essentials); `pip install -e .` and
  `.[dev]` install no Qt, shiboken6 or Matplotlib;
- a separate `yaas-gui = "yaas.gui.main:main"` entry point that loads
  Qt lazily; without the extra it exits with code 1 and a short hint to
  install `yet-another-antenna-simulator[gui]`, without a traceback;
  `--version`, `--help` and `--smoke-test` (opens, processes the event
  loop and closes the window through `QTimer`; exit code 0 only if the
  window and the plot canvas were shown and no engine module was
  loaded), plus `--smoke-export IMAGE` (repeatable, requires
  `--smoke-test`) that draws a small synthetic cut and exports it;
  that synthetic data exists only for the smoke test;
- `RadiationPatternPlotAdapter` and the frozen, validated
  `RadiationPatternPlotSummary` (`src/yaas/gui/plots/radiation_pattern.py`):
  `plot_azimuth(result, *, theta_index, floor_db)` draws a polar plot
  with 0 deg to the East and angles increasing counterclockwise
  (verified through Matplotlib transforms in the tests);
  `plot_vertical(result, *, phi_index, floor_db)` draws `theta` (deg)
  versus dBi on cartesian axes; one private helper prepares the data:
  `None` becomes NaN (a gap, counted as null) and finite gains below
  `floor_db` are drawn on the floor and counted as clipped, so they
  are never lost; an all-null cut draws an empty plot without
  failing; each call reuses the same figure and canvas without
  accumulating artists; `save_image(destination)` chooses PNG, SVG or
  PDF from the extension (case-insensitive), raises `ValueError` for
  anything else and never creates directories; the result is never
  modified;
- `RadiationPatternPlotWidget` (`src/yaas/gui/widgets/`), with
  `show_azimuth`, `show_vertical`, `clear` and an explicit empty state;
- `MainWindow` (`src/yaas/gui/window.py`): title, name and version,
  plus a "Radiation pattern" tab with that widget, empty in
  production (no synthetic data); no engine or exporters;
- project loading: `ProjectViewState` (`yaas.gui.controllers.project_state`,
  frozen, Qt-free, semantic data only: path, name, schema version,
  conductor count, frequency, reference impedance, the domain
  `Environment`, `has_sweep`, and the pattern's `theta`/`phi`
  `AngularSweep`s or `None`; `theta` is never turned into elevation);
  `ProjectController` (`yaas.gui.controllers.project`, a `QObject`
  with an injectable opener, default `open_project`) keeps the current
  `OpenedProject`, exposes read-only `opened_project`, `state` and
  `has_project`, and emits `project_opened(ProjectViewState)`,
  `project_closed()` and `error_occurred(title, message)`; it catches
  only `ProjectFormatError` and `OSError` (anything else propagates), a
  failed open keeps the previous project, and it never shows dialogs,
  reads JSON, saves or runs the engine; `MainWindow` owns the *File*
  menu (*Open…*, *Close project*, disabled without a project, *Exit*),
  `QFileDialog` (filter `YAAS projects (*.yaas)`; cancelling changes
  nothing) and `QMessageBox.critical` for errors (replaceable through
  `error_presenter`), shows a `ProjectSummaryWidget` ("No project
  loaded" when empty) and the title `YAAS — <project name>`, and
  clears the pattern widget on open and close; visible GUI strings
  live in `yaas.gui.texts` (English only, no translation
  infrastructure yet); `yaas-gui [PROJECT]` opens the project at
  startup (an error shows the dialog over an empty window), and
  `--smoke-test PROJECT` exits with 1 when the project cannot be
  opened;
- pattern calculation (no main-thread blocking):
  `SimulationRunner` (`src/yaas/gui/runner.py`) runs one job at a time
  in a new `QThread` with a worker `QObject` (`moveToThread`), delivers
  `succeeded(job_id, result)`, `failed(job_id, message, traceback)` or
  `cancelled(job_id)` to the main thread through queued connections,
  and rejects a second `submit` while busy; cancellation is
  cooperative (`CancellationToken.raise_if_cancelled` between calls),
  a native call already running cannot be interrupted and its result
  (or error) is discarded when it finishes, `QThread.terminate()` is
  never used, and `shutdown()` (idempotent, harmless without a job)
  cancels and waits so no thread is left; when `finished` arrives the
  runner first calls `thread.wait()` (the thread is already ending, so
  it returns at once) and only then drops its references, because
  `finished` is emitted just before the thread processes the worker's
  `deleteLater` and dropping them earlier let PySide destroy the
  worker from the main thread concurrently (reproduced as an access
  violation or `abort()` when chaining thousands of short jobs; see the
  subprocess stress test in `tests/gui/test_simulation_runner.py`); the worker is destroyed in
  its own thread (`QThread.finished -> worker.deleteLater`) and the
  `QThread` on the main thread; a thread the system cannot start makes
  `submit` raise `RuntimeError` without leaving the runner busy (the
  controller then goes to `ERROR`), and a worker that ends without
  reporting a result is reported as failed, so no path stays
  "calculating" forever;
  `RadiationPatternController` (`src/yaas/gui/controllers/pattern.py`)
  has the states `EMPTY` (no project, or no pattern), `READY`,
  `CALCULATING`, `CANCELLING`, `RESULT` and `ERROR`, calls
  `prepare_radiation_pattern_request` on the main thread (a project
  without pattern becomes `ERROR` without creating an engine) and, in
  the worker, creates the engine through an injectable factory
  (default `create_pynec_engine`, the only place that imports
  `yaas.engines.pynec`) and runs `calculate_radiation_pattern`; it
  emits `result_ready(RadiationPatternAnalysis)` before
  `state_changed(RESULT)`, keeps the previous result when a
  recalculation is cancelled, and discards the result when the project
  changes during a calculation; `pattern_cut.choose_initial_cut`
  (Qt-free) draws the vertical cut for `n_theta > 1, n_phi == 1`, the
  azimuth cut for `n_theta == 1, n_phi > 1`, and the first vertical
  cut (`phi` index 0) when both are greater than one, flagging that a
  future cut selector is needed; the plot floor is 40 dB below the
  summary maximum; `MainWindow` adds the *Calculate* menu
  (*Radiation pattern*, F5, and *Cancel calculation*), a status line
  for each state, disables *Open*, *Close project* and *Radiation
  pattern* while calculating, and its `closeEvent` calls `shutdown()`
  (a deliberate decision: it blocks until the running native call
  ends, without a confirmation dialog yet); the plot floor only
  affects the drawing, and `RadiationPatternAnalysis` keeps every
  original value; `yaas-gui
  --smoke-test --smoke-calculate PROJECT` calculates for real and
  exits with 1 unless the pattern is drawn;
- tests without Qt (`tests/test_gui_entry_point.py`: no layer loads
  PySide6, the CLI works, clean failure, extras and CI jobs declared;
  `tests/test_gui_project_state.py`;
  `tests/unit/test_project_application.py`) and with Qt
  (`tests/gui/test_gui_smoke.py`, `tests/gui/test_radiation_pattern_plot.py`,
  `tests/gui/test_project_controller.py`,
  `tests/gui/test_main_window_project.py`,
  `tests/gui/test_simulation_runner.py`,
  `tests/gui/test_pattern_controller.py`,
  `tests/gui/test_main_window_pattern.py` (fake engines from
  `tests/gui/pattern_fakes.py`, `QThread.terminate` forbidden) and one
  real-engine integration test,
  `tests/gui/test_pattern_calculation_pynec.py`; plus the Qt-free
  `tests/test_gui_pattern_cut.py`; offscreen, skipped when
  PySide6 is not installed; plots are checked structurally through
  line data and transforms, never by comparing pixels; dialogs are
  monkeypatched and signals use direct connections, without
  pytest-qt);
- separate GUI executables and CI jobs (see "GUI executables
  (experimental)"); with Matplotlib the windowed Windows executable
  measured 63.4 MB (34.1 MB before), and 63.8 MB once it also carried
  PyNEC; the CLI executable built with Qt and Matplotlib installed
  still carries neither (19.6 MB);
- `THIRD_PARTY_NOTICES.md` (section 4) and
  `docs/packaging/gui-release-compliance.md` for the incorporated Qt,
  Matplotlib and transitive components; the PySide6 wheel ships no
  LGPL/GPL text, and PyInstaller copies no license text of Matplotlib
  or its dependencies other than numpy, so a binary release would have
  to provide them.

Still pending in this phase: a cut selector for patterns with several
cuts, and impedance or sweep calculation from the GUI. A separate
process stays an alternative to `QThread` if real tests show
unacceptable pauses, since PyNEC held the GIL in the native calls
measured so far (the UI can pause for the duration of one native
call). Only `create_pynec_engine`, inside the worker, imports the
engine; the GUI never imports `nec_context`, never reads `.yaas` JSON
or builds NEC cards by hand, and never runs the engine on the UI
thread.

3D patterns and a geometry editor stay in later phases.

### Later phases

- comparison plots;
- PNG export;
- PySide6 desktop GUI beyond the phase 9 foundation;
- geometry visualization;
- radiation-pattern plots (2D cuts first) and frequency sweeps of
  patterns;
- radiation-pattern polarization and `E_theta`/`E_phi` field
  components;
- reflection-coefficient (fast/Fresnel) real-ground method;
- ground screens/radials and buried (or ground-plane-contained)
  conductors, for any ground type;
- progress reporting or cancellation for long-running sweeps;
- loads and additional geometry;
- greater MMANA-GAL compatibility (multiple sources, concentrated
  loads, non-free-space environments, tapering-aware segmentation);
- NEC import;
- Touchstone multi-port support.

## Explicitly postponed work

Do not implement these items unless specifically requested:

- NEC import;
- Touchstone `.s2p` or multi-port support;
- the reflection-coefficient (fast/Fresnel) real-ground method
  (Sommerfeld-Norton is implemented; `RealGroundModel` only has one
  member for now);
- ground screens/radials and buried (or ground-plane-contained)
  conductors, for any ground type;
- progress reporting or cancellation for long-running sweeps (most
  relevant to real-ground sweeps, which create one NEC2++ context per
  frequency and can take several seconds for 81+ points);
- accepting non-free-space MMANA-GAL environments for import
  (perfect ground or real ground);
- replacement of PyNEC;
- modifications to NEC2++;
- GUI features beyond the phase 9 foundation (impedance or sweep
  calculation, editing, saving, new projects, recent files,
  drag-and-drop, interactive tooltips, a cut selector, 3D, themes,
  preferences, a separate calculation process) unless the current task
  asks for them; do not add pyqtgraph or pytest-qt;
- automatic dependency upgrades;
- application renaming;
- breaking CLI changes.