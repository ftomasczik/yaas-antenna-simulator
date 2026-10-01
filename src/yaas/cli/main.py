"""Interfaz de línea de comandos del simulador."""

import argparse
import math
import platform
import sys
from collections.abc import Sequence
from pathlib import Path

import yaas
from yaas.application import (
    ComparisonRequestError,
    MissingRadiationPatternError,
    RadiationPatternAnalysis,
    calculate_radiation_pattern,
    compare_project_measurement,
    export_project_radiation_pattern_nec,
    prepare_mmana_import,
    prepare_radiation_pattern_request,
    write_mmana_import,
)

from yaas.domain import (
    Point3D,
    SimulationRequest,
    SweepComparison,
    SweepRequest,
    SweepResult,
    VoltageSource,
    Wire,
)

from yaas.exporters import (
    export_comparison_csv,
    export_nec,
    export_radiation_pattern_csv,
    export_sweep_csv,
    export_sweep_nec,
)

from yaas.i18n import (
    SUPPORTED_LANGUAGES,
    set_language,
    translate as _,
)

from yaas.projects import (
    AntennaProject,
    ProjectFormatError,
    SweepSettings,
    load_project,
)

from yaas.importers import (
    MmanaCompatibilityError,
    MmanaFormatError,
    TouchstoneFormatError,
    load_touchstone_s1p,
)
def create_reference_dipole() -> Wire:
    """Crea la geometría del dipolo de referencia."""
    return Wire(
        tag=1,
        start=Point3D(-5.03, 0.0, 0.0),
        end=Point3D(5.03, 0.0, 0.0),
        radius_m=0.001,
        segments=101,
    )


def create_reference_dipole_request() -> SimulationRequest:
    """Crea una simulación simple del dipolo de referencia."""
    return SimulationRequest(
        frequency_mhz=14.15,
        wires=(create_reference_dipole(),),
        source=VoltageSource(
            wire_tag=1,
            segment=51,
        ),
        reference_impedance=50.0,
    )


def create_reference_sweep_request(
    start_frequency_mhz: float,
    stop_frequency_mhz: float,
    points: int,
) -> SweepRequest:
    """Crea un barrido para el dipolo de referencia."""
    return SweepRequest(
        start_frequency_mhz=start_frequency_mhz,
        stop_frequency_mhz=stop_frequency_mhz,
        points=points,
        wires=(create_reference_dipole(),),
        source=VoltageSource(
            wire_tag=1,
            segment=51,
        ),
        reference_impedance=50.0,
    )


def run_doctor(
    _arguments: argparse.Namespace,
) -> int:
    """Comprueba los componentes fundamentales del programa."""
    print(
        _("YAAS version: {version}").format(
            version=yaas.__version__
        )
    )
    print(
        _("Python version: {version}").format(
            version=platform.python_version()
        )
    )
    print(
        _("System: {system} {machine}").format(
            system=platform.system(),
            machine=platform.machine(),
        )
    )

    try:
        from yaas.engines.pynec import check_runtime

        check_runtime()
    except Exception as error:
        print(
            _("PyNEC: ERROR - {error}").format(
                error=error
            )
        )
        return 1

    print(_("PyNEC: OK"))
    print(_("Environment: OK"))

    return 0


def run_reference_dipole(
    _arguments: argparse.Namespace,
) -> int:
    """Simula y presenta el dipolo de referencia."""
    from yaas.engines.pynec import PyNecEngine

    request = create_reference_dipole_request()
    engine = PyNecEngine()
    result = engine.simulate(request)

    print(
        _("Frequency: {frequency:.3f} MHz").format(
            frequency=result.frequency_mhz
        )
    )
    print(
        _(
            "Impedance: {real:.2f} "
            "{imag:+.2f}j ohm"
        ).format(
            real=result.impedance.real,
            imag=result.impedance.imag,
        )
    )
    print(
        _(
            "SWR relative to {reference:.0f} ohm: "
            "{swr:.2f}"
        ).format(
            reference=request.reference_impedance,
            swr=result.swr,
        )
    )

    return 0

def print_sweep_summary(
    request: SweepRequest,
    result: SweepResult,
    swr_limit: float,
) -> None:
    """Presenta el resumen de un barrido."""
    resonance = result.resonance_point
    minimum_swr = result.minimum_swr_point
    bandwidth = result.swr_bandwidth(swr_limit)

    print(
        _("Sweep: {start:.3f}-{stop:.3f} MHz").format(
            start=request.start_frequency_mhz,
            stop=request.stop_frequency_mhz,
        )
    )
    print(
        _("Points: {points}").format(
            points=len(result.points)
        )
    )

    print()
    if resonance is None:
        print(_(
            "Approximate resonance: unavailable; no points have finite impedance."
        ))
    else:
        if result.resonance_is_at_boundary:
            print(
                _(
                    "Approximate resonance: at the edge of the "
                    "sweep; the actual resonance may lie outside "
                    "the swept range."
                )
            )
        else:
            print(f"{_('Approximate resonance')}:")
        print(
            f"  {_('Frequency')}: "
            f"{resonance.frequency_mhz:.3f} MHz"
        )
        print(
            f"  {_('Impedance')}: "
            f"{resonance.impedance.real:.2f} "
            f"{resonance.impedance.imag:+.2f}j ohm"
        )
        print(f"  {_('SWR')}: {resonance.swr:.2f}")

    print()
    if result.minimum_swr_is_at_boundary:
        print(f"{_('Minimum SWR observed at the edge of the sweep')}:")
    else:
        print(f"{_('Minimum SWR')}:")
    print(
        f"  {_('Frequency')}: "
        f"{minimum_swr.frequency_mhz:.3f} MHz"
    )
    print(
        f"  {_('Impedance')}: "
        f"{minimum_swr.impedance.real:.2f} "
        f"{minimum_swr.impedance.imag:+.2f}j ohm"
    )
    print(f"  {_('SWR')}: {minimum_swr.swr:.2f}")

    print()

    if bandwidth is None:
        print(
            _(
                "Bandwidth: no interval with "
                "SWR <= {limit:.2f}"
            ).format(limit=swr_limit)
        )
    elif bandwidth.truncated_below or bandwidth.truncated_above:
        print(
            _(
                "Bandwidth for SWR <= {limit:.2f}: truncated; "
                "the interval may extend beyond the sweep."
            ).format(limit=swr_limit)
        )
        print(
            f"  {_('Lower frequency')}: "
            + (
                _("outside the sweep")
                if bandwidth.truncated_below
                else f"{bandwidth.lower_frequency_mhz:.3f} MHz"
            )
        )
        print(
            f"  {_('Upper frequency')}: "
            + (
                _("outside the sweep")
                if bandwidth.truncated_above
                else f"{bandwidth.upper_frequency_mhz:.3f} MHz"
            )
        )
    else:
        print(
            _(
                "Bandwidth for SWR <= {limit:.2f}"
            ).format(limit=swr_limit)
            + ":"
        )
        print(
            f"  {_('Lower frequency')}: "
            f"{bandwidth.lower_frequency_mhz:.3f} MHz"
        )
        print(
            f"  {_('Upper frequency')}: "
            f"{bandwidth.upper_frequency_mhz:.3f} MHz"
        )
        print(
            f"  {_('Bandwidth')}: "
            f"{bandwidth.bandwidth_khz:.1f} kHz"
        )
        print(
            f"  {_('Fractional bandwidth')}: "
            f"{bandwidth.fractional_bandwidth_percent:.2f} %"
        )

def run_reference_sweep(
    arguments: argparse.Namespace,
) -> int:
    """Ejecuta un barrido del dipolo de referencia."""
    try:
        if (
            not math.isfinite(arguments.swr_limit)
            or arguments.swr_limit < 1.0
        ):
            raise ValueError(
                _(
                    "The SWR limit must be finite "
                    "and greater than or equal to 1."
                )
            )

        request = create_reference_sweep_request(
            start_frequency_mhz=arguments.start,
            stop_frequency_mhz=arguments.stop,
            points=arguments.points,
        )
    except ValueError as error:
        print(
            _("Error: {error}").format(
                error=error
            ),
            file=sys.stderr,
        )
        return 2

    from yaas.engines.pynec import PyNecEngine

    engine = PyNecEngine()
    result = engine.simulate_sweep(request)

    print_sweep_summary(
        request=request,
        result=result,
        swr_limit=arguments.swr_limit,
    )

    if arguments.output is not None:
        output_path = export_sweep_csv(
            result=result,
            destination=arguments.output,
        )

        print()
        print(
            f"{_('CSV file')}: "
            f"{output_path.resolve()}"
        )

    return 0

def run_validate_project(
    arguments: argparse.Namespace,
) -> int:
    """Valida un archivo de proyecto YAAS."""
    try:
        project = load_project(arguments.project)
    except (OSError, ProjectFormatError) as error:
        print(
            _("Invalid project: {error}").format(
                error=error
            ),
            file=sys.stderr,
        )
        return 2

    print(
        _("Valid project: {path}").format(
            path=arguments.project.resolve()
        )
    )
    print(
        _("Project name: {name}").format(
            name=project.metadata.name
        )
    )
    print(
        _("Schema version: {version}").format(
            version=project.schema_version
        )
    )
    print(
        _("Wires: {count}").format(
            count=len(project.wires)
        )
    )

    return 0

def run_project_simulation(
    arguments: argparse.Namespace,
) -> int:
    """Carga y simula un proyecto YAAS."""
    try:
        project = load_project(arguments.project)
        request = project.to_simulation_request()
    except (OSError, ProjectFormatError) as error:
        print(
            _("Invalid project: {error}").format(
                error=error
            ),
            file=sys.stderr,
        )
        return 2

    from yaas.engines.pynec import PyNecEngine

    engine = PyNecEngine()
    result = engine.simulate(request)

    print(
        _("Simulating project: {name}").format(
            name=project.metadata.name
        )
    )
    print(
        _("Frequency: {frequency:.3f} MHz").format(
            frequency=result.frequency_mhz
        )
    )
    print(
        _("Impedance: {real:.2f} {imag:+.2f}j ohm").format(
            real=result.impedance.real,
            imag=result.impedance.imag,
        )
    )
    print(
        _(
            "SWR relative to {reference:.0f} ohm: "
            "{swr:.2f}"
        ).format(
            reference=request.reference_impedance,
            swr=result.swr,
        )
    )

    return 0

def run_project_sweep(
    arguments: argparse.Namespace,
) -> int:
    """Carga y ejecuta el barrido de un proyecto YAAS."""
    try:
        project = load_project(arguments.project)
        request = project.to_sweep_request()
    except (OSError, ProjectFormatError) as error:
        print(
            _("Invalid project: {error}").format(
                error=error
            ),
            file=sys.stderr,
        )
        return 2

    from yaas.engines.pynec import PyNecEngine

    engine = PyNecEngine()
    result = engine.simulate_sweep(request)

    print(
        _("Sweeping project: {name}").format(
            name=project.metadata.name
        )
    )

    print_sweep_summary(
        request=request,
        result=result,
        swr_limit=project.sweep.swr_limit,
    )

    if arguments.output is not None:
        output_path = export_sweep_csv(
            result=result,
            destination=arguments.output,
        )

        print()
        print(
            f"{_('CSV file')}: "
            f"{output_path.resolve()}"
        )

    return 0


def print_radiation_pattern_summary(
    project: AntennaProject,
    analysis: RadiationPatternAnalysis,
) -> None:
    """Presenta el resumen de un patrón de radiación.

    Los conteos y el máximo provienen de
    ``yaas.application.summarize_radiation_pattern``; aquí solo se
    formatean y traducen.
    """
    result = analysis.result
    summary = analysis.summary
    maximum = summary.maximum

    print(
        _("Calculating radiation pattern: {name}").format(
            name=project.metadata.name
        )
    )
    print(
        _("Frequency: {frequency:.3f} MHz").format(
            frequency=result.frequency_mhz
        )
    )
    print(
        _(
            "Grid: {n_theta} x {n_phi} ({points} points)"
        ).format(
            n_theta=result.n_theta,
            n_phi=result.n_phi,
            points=summary.total_points,
        )
    )
    print(
        _("Valid points: {count}").format(
            count=summary.valid_points
        )
    )
    print(
        _("Null points: {count}").format(count=summary.null_points)
    )

    if maximum is None:
        print(
            _(
                "Maximum gain: unavailable; the pattern has no "
                "finite gain values."
            )
        )
        return

    print(
        _("Maximum gain: {gain:.2f} dBi").format(
            gain=maximum.gain_db
        )
    )
    print(
        _(
            "Direction of maximum: theta={theta:.2f} deg, "
            "phi={phi:.2f} deg"
        ).format(
            theta=maximum.theta_deg,
            phi=maximum.phi_deg,
        )
    )


def _print_missing_radiation_pattern() -> None:
    """Informa que el proyecto no define un patrón de radiación."""
    print(
        _(
            "Invalid project: the project does not define a "
            "radiation pattern (simulation.radiation_pattern)."
        ),
        file=sys.stderr,
    )


def run_radiation_pattern(
    arguments: argparse.Namespace,
) -> int:
    """Calcula el patrón de radiación configurado en un proyecto YAAS."""
    try:
        project = load_project(arguments.project)
    except (OSError, ProjectFormatError) as error:
        print(
            _("Invalid project: {error}").format(
                error=error
            ),
            file=sys.stderr,
        )
        return 2

    try:
        # Se valida antes de construir el motor: un proyecto sin patrón
        # nunca carga PyNEC.
        request = prepare_radiation_pattern_request(project)
    except MissingRadiationPatternError:
        _print_missing_radiation_pattern()
        return 2

    from yaas.engines.pynec import PyNecEngine

    engine = PyNecEngine()

    try:
        analysis = calculate_radiation_pattern(request, engine=engine)
    except (RuntimeError, ValueError) as error:
        print(
            _(
                "Radiation pattern calculation failed: {error}"
            ).format(error=error),
            file=sys.stderr,
        )
        return 1

    print_radiation_pattern_summary(project=project, analysis=analysis)

    if arguments.csv is not None:
        # Se exporta el mismo resultado ya calculado: el motor no se
        # vuelve a ejecutar.
        try:
            output_path = export_radiation_pattern_csv(
                result=analysis.result,
                destination=arguments.csv,
            )
        except OSError as error:
            print(
                _("Could not write CSV file: {error}").format(
                    error=error
                ),
                file=sys.stderr,
            )
            return 2

        print()
        print(
            f"{_('CSV file')}: "
            f"{output_path.resolve()}"
        )

    return 0


def run_inspect_s1p(
    arguments: argparse.Namespace,
) -> int:
    """Carga y presenta un archivo Touchstone S1P."""
    try:
        measurement = load_touchstone_s1p(
            arguments.measurement
        )
    except (OSError, TouchstoneFormatError) as error:
        print(
            _("Invalid measurement: {error}").format(
                error=error
            ),
            file=sys.stderr,
        )
        return 2

    resonance = measurement.resonance_point
    minimum_swr = measurement.minimum_swr_point

    print(
        _("Measurement: {path}").format(
            path=arguments.measurement.resolve()
        )
    )
    print(
        _(
            "Frequency range: {start:.3f}-"
            "{stop:.3f} MHz"
        ).format(
            start=measurement.start_frequency_mhz,
            stop=measurement.stop_frequency_mhz,
        )
    )
    print(
        _("Points: {points}").format(
            points=len(measurement.points)
        )
    )
    print(
        _(
            "Reference impedance: "
            "{reference:.2f} ohm"
        ).format(
            reference=(
                measurement.reference_impedance
            )
        )
    )

    print()
    if resonance is None:
        print(_(
            "Approximate resonance: unavailable; no points have finite impedance."
        ))
    else:
        print(f"{_('Approximate resonance')}:")
        print(
            f"  {_('Frequency')}: "
            f"{resonance.frequency_mhz:.3f} MHz"
        )
        print(
            f"  {_('Impedance')}: "
            f"{resonance.impedance.real:.2f} "
            f"{resonance.impedance.imag:+.2f}j ohm"
        )
        print(f"  {_('SWR')}: {resonance.swr:.2f}")

    print()
    print(f"{_('Minimum SWR')}:")
    print(
        f"  {_('Frequency')}: "
        f"{minimum_swr.frequency_mhz:.3f} MHz"
    )
    print(
        f"  {_('Impedance')}: "
        f"{minimum_swr.impedance.real:.2f} "
        f"{minimum_swr.impedance.imag:+.2f}j ohm"
    )
    print(f"  {_('SWR')}: {minimum_swr.swr:.2f}")

    if not measurement.has_reactance_zero_crossing:
        print()
        print(
            _(
                "Warning: reactance does not cross zero "
                "within the measured range."
            )
        )

    if measurement.minimum_swr_is_at_boundary:
        print()
        print(
            _(
                "Warning: minimum SWR is at the edge "
                "of the measured range."
            )
        )
        
    return 0

def print_comparison_summary(
    project: AntennaProject,
    measurement_path: Path,
    reference_impedance: float,
    comparison: SweepComparison,
) -> None:
    """Presenta el resumen de una comparación proyecto/medición."""
    interpolated_points = sum(
        1
        for point in comparison.points
        if point.interpolated
    )
    worst_point = max(
        comparison.points,
        key=lambda point: abs(point.swr_difference),
    )

    print(
        _("Comparing project: {name}").format(
            name=project.metadata.name
        )
    )
    print(
        _("Measurement file: {path}").format(
            path=measurement_path.resolve()
        )
    )
    print(
        _(
            "Reference impedance: {reference:.2f} ohm"
        ).format(
            reference=reference_impedance
        )
    )
    print(
        _("Compared points: {count}").format(
            count=len(comparison.points)
        )
    )
    print(
        _(
            "Measured points excluded (out of range): "
            "{count}"
        ).format(
            count=(
                comparison.excluded_measurement_points
            )
        )
    )
    print(
        _(
            "Points requiring interpolation: {count}"
        ).format(count=interpolated_points)
    )

    print()
    print(f"{_('Largest SWR difference')}:")
    print(
        f"  {_('Frequency')}: "
        f"{worst_point.frequency_mhz:.3f} MHz"
    )
    print(
        f"  {_('Magnitude')}: "
        f"{abs(worst_point.swr_difference):.2f}"
    )

def run_compare(
    arguments: argparse.Namespace,
) -> int:
    """Compara el barrido de un proyecto con una medición Touchstone."""
    try:
        project = load_project(arguments.project)
    except (OSError, ProjectFormatError) as error:
        print(
            _("Invalid project: {error}").format(
                error=error
            ),
            file=sys.stderr,
        )
        return 2

    try:
        measurement = load_touchstone_s1p(
            arguments.measurement
        )
    except (OSError, TouchstoneFormatError) as error:
        print(
            _("Invalid measurement: {error}").format(
                error=error
            ),
            file=sys.stderr,
        )
        return 2

    from yaas.engines.pynec import PyNecEngine

    engine = PyNecEngine()

    try:
        comparison = compare_project_measurement(
            project=project,
            measurement=measurement,
            reference_impedance=(
                arguments.reference_impedance
            ),
            engine=engine,
        )
    except ComparisonRequestError as error:
        print(
            _("Invalid comparison: {error}").format(
                error=error
            ),
            file=sys.stderr,
        )
        return 2

    print_comparison_summary(
        project=project,
        measurement_path=arguments.measurement,
        reference_impedance=(
            arguments.reference_impedance
        ),
        comparison=comparison,
    )

    if arguments.output is not None:
        output_path = export_comparison_csv(
            comparison=comparison,
            destination=arguments.output,
        )

        print()
        print(
            f"{_('CSV file')}: "
            f"{output_path.resolve()}"
        )

    return 0

# Descripciones en inglés (idioma fuente) de cada código de
# incompatibilidad MMANA-GAL. Los códigos en sí (las claves) nunca se
# traducen; solo se traducen estas descripciones, y siempre en el
# momento de imprimir (llamando a ``_()`` recién al mostrarlas), nunca
# al construir este diccionario a nivel de módulo, para no quedar
# atadas al idioma activo quando el módulo se importó por primera vez.
_MMANA_ISSUE_DESCRIPTIONS: dict[str, str] = {
    "comment-empty": "The comment section is present but empty.",
    "environment-azel-not-preserved": (
        "The requested pattern azimuth and elevation will not be "
        "preserved."
    ),
    "environment-height-invalid": (
        "The additional height above ground is not a finite number."
    ),
    "environment-not-free-space": (
        "Only free-space models are supported; ground models cannot "
        "be imported."
    ),
    "frequency-invalid": (
        "The main frequency must be a finite, positive number."
    ),
    "loads-present": "Concentrated loads are not supported yet.",
    "reference-impedance-invalid": (
        "The reference impedance must be a finite, positive number."
    ),
    "section-header-noncanonical": (
        "A section header does not match any recognized variant."
    ),
    "segmentation-invalid": (
        "The global segmentation parameters (DM1, DM2, SC, EC) are "
        "invalid."
    ),
    "segmentation-taper-not-reproducible": (
        "MMANA-GAL tapered segmentation cannot be reproduced exactly; "
        "YAAS uses uniform segmentation instead."
    ),
    "source-count-invalid": "Exactly one source is required.",
    "source-not-centered": (
        "The source must be centered on its conductor, without any "
        "pulse offset."
    ),
    "source-phase-invalid": "The source phase must be a finite number.",
    "source-phase-nonzero": "The source phase is different from zero.",
    "source-voltage-invalid": (
        "The source voltage must be a finite number different from "
        "zero."
    ),
    "title-empty": "The document title is empty.",
    "wire-geometry-invalid": (
        "A conductor has non-finite coordinates or zero length."
    ),
    "wire-radius-invalid": (
        "A conductor radius must be a finite, positive number."
    ),
    "wire-reference-syntax-invalid": (
        "A source or load has an invalid conductor reference."
    ),
    "wire-reference-unknown": (
        "A source or load references a conductor that does not exist."
    ),
    "wire-segment-override-unsupported": (
        "This conductor's manual segmentation mode is not supported "
        "yet."
    ),
}

def _describe_mmana_issue(issue) -> str:
    """Traduce la explicación de una advertencia/error MMANA-GAL.

    El código (``issue.code``) nunca se traduce. Si el código no está
    en ``_MMANA_ISSUE_DESCRIPTIONS`` (por ejemplo, uno agregado a
    ``yaas.importers.mmana_compatibility`` sin actualizar este
    mapeo), se usa ``issue.message`` (el mensaje interno) como
    resguardo, para no ocultar información.
    """
    description = _MMANA_ISSUE_DESCRIPTIONS.get(issue.code)
    if description is None:
        return issue.message
    return _(description)

def _group_mmana_issues(
    issues,
) -> list[tuple[str, str, int]]:
    """Agrupa issues MMANA-GAL por código y descripción ya traducida.

    Devuelve una lista de ``(code, description, occurrences)``, en el
    orden de primera aparición. La clave de agrupación es el par
    ``(código, descripción)``, no solo el código: dos issues con el
    mismo código pero una descripción realmente distinta (por
    ejemplo, el mensaje interno de resguardo de un código todavía no
    mapeado en ``_MMANA_ISSUE_DESCRIPTIONS``, que conserva el detalle
    propio de cada instancia en vez de un texto fijo) no se agrupan
    entre sí.
    """
    occurrences_by_key: dict[tuple[str, str], int] = {}
    order: list[tuple[str, str]] = []

    for issue in issues:
        key = (issue.code, _describe_mmana_issue(issue))
        if key not in occurrences_by_key:
            occurrences_by_key[key] = 0
            order.append(key)
        occurrences_by_key[key] += 1

    return [
        (code, description, occurrences_by_key[(code, description)])
        for code, description in order
    ]

def run_import_mmana(
    arguments: argparse.Namespace,
) -> int:
    """Importa un archivo MMANA-GAL .maa como proyecto YAAS."""
    try:
        sweep = SweepSettings(
            start_frequency_mhz=arguments.sweep_start,
            stop_frequency_mhz=arguments.sweep_stop,
            points=arguments.sweep_points,
            swr_limit=arguments.swr_limit,
        )
    except ValueError as error:
        print(
            _("Invalid sweep settings: {error}").format(
                error=error
            ),
            file=sys.stderr,
        )
        return 2

    try:
        result = prepare_mmana_import(
            arguments.source,
            sweep=sweep,
            legacy_encoding=arguments.legacy_encoding,
        )
    except OSError as error:
        print(
            _("MMANA-GAL import failed: {error}").format(
                error=error
            ),
            file=sys.stderr,
        )
        return 2
    except MmanaCompatibilityError as error:
        print(
            _("Incompatible MMANA-GAL model:"),
            file=sys.stderr,
        )
        for issue in error.issues:
            print(
                f"  - [{issue.code}] "
                f"{_describe_mmana_issue(issue)}",
                file=sys.stderr,
            )
        return 2
    except MmanaFormatError as error:
        print(
            _("Invalid MMANA-GAL file: {error}").format(
                error=error
            ),
            file=sys.stderr,
        )
        return 2

    try:
        written_path = write_mmana_import(
            result,
            arguments.destination,
            overwrite=arguments.force,
        )
    except FileExistsError:
        print(
            _("Destination already exists: {path}").format(
                path=arguments.destination
            ),
            file=sys.stderr,
        )
        print(
            _("Use --force to overwrite it."),
            file=sys.stderr,
        )
        return 2
    except (OSError, ValueError) as error:
        print(
            _("MMANA-GAL import failed: {error}").format(
                error=error
            ),
            file=sys.stderr,
        )
        return 2

    project = result.project

    print(_("MMANA-GAL project imported successfully."))
    print(f"{_('Source')}: {result.source_path.resolve()}")
    print(f"{_('Destination')}: {written_path.resolve()}")
    print(f"{_('Encoding')}: {result.detected_encoding}")
    print(f"{_('Project')}: {project.metadata.name}")
    print(
        _("Frequency: {frequency:.3f} MHz").format(
            frequency=project.frequency_mhz
        )
    )
    print(
        _("Wires: {count}").format(
            count=len(project.wires)
        )
    )

    warnings = result.compatibility_report.warnings
    grouped_warnings = _group_mmana_issues(warnings)

    print(
        _("Warnings: {count}").format(count=len(warnings))
    )
    print(
        _("Unique warnings: {count}").format(
            count=len(grouped_warnings)
        )
    )

    if warnings:
        for index, (code, description, occurrences) in enumerate(
            grouped_warnings
        ):
            print()
            if occurrences > 1:
                print(
                    _(
                        "Warning [{code}] "
                        "({occurrences} occurrences):"
                    ).format(code=code, occurrences=occurrences)
                )
            else:
                print(
                    _("Warning [{code}]:").format(code=code)
                )
            print(f"  {description}")

    return 0

def create_parser() -> argparse.ArgumentParser:
    """Construye el analizador de argumentos."""
    parser = argparse.ArgumentParser(
        prog="yaas",
        description=_(
            "Antenna simulator based on NEC2++."
        ),
    )

    parser.add_argument(
        "--language",
        choices=SUPPORTED_LANGUAGES,
        help=_(
            "Interface language: en or es."
        ),
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {yaas.__version__}",
    )

    commands = parser.add_subparsers(
        title=_("commands"),
        dest="command",
        required=True,
    )

    doctor_parser = commands.add_parser(
        "doctor",
        help=_(
            "Check the runtime environment."
        ),
    )
    doctor_parser.set_defaults(
        handler=run_doctor
    )

    dipole_parser = commands.add_parser(
        "simulate-dipole",
        help=_(
            "Simulate the built-in reference dipole."
        ),
    )
    dipole_parser.set_defaults(
        handler=run_reference_dipole
    )

    sweep_parser = commands.add_parser(
        "sweep-dipole",
        help=_(
            "Sweep frequencies over the reference dipole."
        ),
    )

    sweep_parser.add_argument(
        "--start",
        type=float,
        default=13.0,
        help=_(
            "Start frequency in MHz (default: 13.0)."
        ),
    )

    sweep_parser.add_argument(
        "--stop",
        type=float,
        default=16.0,
        help=_(
            "Stop frequency in MHz (default: 16.0)."
        ),
    )

    sweep_parser.add_argument(
        "--points",
        type=int,
        default=61,
        help=_(
            "Number of points (default: 61)."
        ),
    )

    sweep_parser.add_argument(
        "--swr-limit",
        type=float,
        default=2.0,
        help=_(
            "SWR limit for bandwidth calculation "
            "(default: 2.0)."
        ),
    )

    sweep_parser.add_argument(
        "--output",
        type=Path,
        help=_(
            "CSV file where the sweep will be saved."
        ),
    )

    sweep_parser.set_defaults(
        handler=run_reference_sweep
    )

    validate_parser = commands.add_parser(
        "validate",
        help=_("Validate a YAAS project file."),
    )

    validate_parser.add_argument(
        "project",
        type=Path,
        help=_("YAAS project file to validate."),
    )

    validate_parser.set_defaults(
        handler=run_validate_project
    )

    simulate_parser = commands.add_parser(
        "simulate",
        help=_("Simulate a YAAS project file."),
    )

    simulate_parser.add_argument(
        "project",
        type=Path,
        help=_("YAAS project file to simulate."),
    )

    project_sweep_parser = commands.add_parser(
        "sweep",
        help=_("Sweep frequencies for a YAAS project."),
    )

    project_sweep_parser.add_argument(
        "project",
        type=Path,
        help=_("YAAS project file to sweep."),
    )

    project_sweep_parser.add_argument(
        "--output",
        type=Path,
        help=_(
            "CSV file where the sweep will be saved."
        ),
    )

    project_sweep_parser.set_defaults(
        handler=run_project_sweep
    )
    simulate_parser.set_defaults(
        handler=run_project_simulation
    )

    export_nec_parser = commands.add_parser(
        "export-nec",
        help=_("Export a YAAS project as a NEC file."),
    )

    export_nec_parser.add_argument(
        "project",
        type=Path,
        help=_("YAAS project file to export."),
    )

    export_nec_parser.add_argument(
        "output",
        type=Path,
        help=_("Destination NEC file."),
    )

    export_nec_parser.add_argument(
        "--sweep",
        action="store_true",
        help=_(
            "Export the frequency sweep configured "
            "in the project."
        ),
    )

    # --pattern y --sweep son mutuamente excluyentes. No se usa
    # add_mutually_exclusive_group porque su mensaje de error proviene
    # del dominio gettext de argparse y no se traduciría con el
    # catálogo de YAAS: la exclusión se valida en run_export_nec.
    export_nec_parser.add_argument(
        "--pattern",
        action="store_true",
        help=_(
            "Export the radiation pattern configured "
            "in the project (adds an RP card). "
            "Cannot be combined with --sweep."
        ),
    )

    export_nec_parser.set_defaults(
        handler=run_export_nec
    )

    pattern_parser = commands.add_parser(
        "pattern",
        help=_(
            "Calculate the radiation pattern "
            "configured in a YAAS project."
        ),
    )

    pattern_parser.add_argument(
        "project",
        type=Path,
        help=_(
            "YAAS project file with a radiation "
            "pattern."
        ),
    )

    pattern_parser.add_argument(
        "--csv",
        type=Path,
        help=_(
            "CSV file where the radiation pattern "
            "will be saved."
        ),
    )

    pattern_parser.set_defaults(
        handler=run_radiation_pattern
    )

    inspect_s1p_parser = commands.add_parser(
        "inspect-s1p",
        help=_(
            "Inspect a Touchstone S1P measurement."
        ),
    )

    inspect_s1p_parser.add_argument(
        "measurement",
        type=Path,
        help=_(
            "Touchstone S1P file to inspect."
        ),
    )

    inspect_s1p_parser.set_defaults(
        handler=run_inspect_s1p
    )

    compare_parser = commands.add_parser(
        "compare",
        help=_(
            "Compare a YAAS project against a "
            "Touchstone measurement."
        ),
    )

    compare_parser.add_argument(
        "project",
        type=Path,
        help=_(
            "YAAS project file to compare."
        ),
    )

    compare_parser.add_argument(
        "measurement",
        type=Path,
        help=_(
            "Touchstone S1P file to compare against."
        ),
    )

    compare_parser.add_argument(
        "--reference-impedance",
        type=float,
        required=True,
        help=_(
            "Reference impedance used for the "
            "comparison, in ohms."
        ),
    )

    compare_parser.add_argument(
        "--output",
        type=Path,
        help=_(
            "CSV file where the comparison will "
            "be saved."
        ),
    )

    compare_parser.set_defaults(
        handler=run_compare
    )

    import_mmana_parser = commands.add_parser(
        "import-mmana",
        help=_(
            "Import a MMANA-GAL .maa file as a "
            "YAAS project."
        ),
    )

    import_mmana_parser.add_argument(
        "source",
        type=Path,
        help=_(
            "MMANA-GAL .maa file to import."
        ),
    )

    import_mmana_parser.add_argument(
        "destination",
        type=Path,
        help=_(
            "YAAS project file to create."
        ),
    )

    import_mmana_parser.add_argument(
        "--sweep-start",
        type=float,
        required=True,
        help=_(
            "Sweep start frequency, in MHz. The "
            "MMANA-GAL format does not carry a "
            "sweep definition, so this value must "
            "always be provided explicitly."
        ),
    )

    import_mmana_parser.add_argument(
        "--sweep-stop",
        type=float,
        required=True,
        help=_(
            "Sweep stop frequency, in MHz."
        ),
    )

    import_mmana_parser.add_argument(
        "--sweep-points",
        type=int,
        required=True,
        help=_(
            "Number of points in the sweep."
        ),
    )

    import_mmana_parser.add_argument(
        "--swr-limit",
        type=float,
        required=True,
        help=_(
            "SWR limit used for bandwidth "
            "calculations."
        ),
    )

    import_mmana_parser.add_argument(
        "--legacy-encoding",
        choices=("cp1251", "cp1252"),
        help=_(
            "Legacy 8-bit encoding to use when the "
            "file is not UTF-8 and the encoding is "
            "ambiguous between CP1251 and CP1252."
        ),
    )

    import_mmana_parser.add_argument(
        "--force",
        action="store_true",
        help=_(
            "Overwrite the destination file if it "
            "already exists."
        ),
    )

    import_mmana_parser.set_defaults(
        handler=run_import_mmana
    )

    return parser

def run_export_nec(
    arguments: argparse.Namespace,
) -> int:
    """Exporta un proyecto YAAS como archivo NEC."""
    if arguments.pattern and arguments.sweep:
        print(
            _(
                "Error: --pattern and --sweep cannot be "
                "used together."
            ),
            file=sys.stderr,
        )
        return 2

    try:
        project = load_project(arguments.project)

        if arguments.sweep:
            request = project.to_sweep_request()
        elif not arguments.pattern:
            request = project.to_simulation_request()
    except (OSError, ProjectFormatError) as error:
        print(
            _("Invalid project: {error}").format(
                error=error
            ),
            file=sys.stderr,
        )
        return 2

    try:
        if arguments.pattern:
            output_path = export_project_radiation_pattern_nec(
                project,
                arguments.output,
            )
        elif arguments.sweep:
            output_path = export_sweep_nec(
                request=request,
                destination=arguments.output,
                title=project.metadata.name,
            )
        else:
            output_path = export_nec(
                request=request,
                destination=arguments.output,
                title=project.metadata.name,
            )
    except MissingRadiationPatternError:
        # El caso de uso rechaza el proyecto antes de crear el archivo.
        _print_missing_radiation_pattern()
        return 2
    except OSError as error:
        print(
            _("Could not write NEC file: {error}").format(
                error=error
            ),
            file=sys.stderr,
        )
        return 2

    print(
        _("NEC file: {path}").format(
            path=output_path.resolve()
        )
    )

    return 0

def main(
    arguments: Sequence[str] | None = None,
) -> int:
    """Punto de entrada de la CLI."""
    if arguments is None:
        raw_arguments = sys.argv[1:]
    else:
        raw_arguments = list(arguments)

    # Se extrae el idioma antes de construir el parser principal
    # para que los textos de ayuda también puedan traducirse.
    language_parser = argparse.ArgumentParser(
        add_help=False
    )
    language_parser.add_argument(
        "--language",
        choices=SUPPORTED_LANGUAGES,
    )

    language_arguments, remaining_arguments = (
        language_parser.parse_known_args(raw_arguments)
    )

    set_language(language_arguments.language)

    parser = create_parser()
    namespace = parser.parse_args(
        remaining_arguments
    )

    return namespace.handler(namespace)


if __name__ == "__main__":
    sys.exit(main())
