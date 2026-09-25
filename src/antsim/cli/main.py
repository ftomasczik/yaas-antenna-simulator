"""Interfaz de línea de comandos del simulador."""

import argparse
import math
import platform
import sys
from collections.abc import Sequence
from pathlib import Path

import antsim
from antsim.domain import (
    Point3D,
    SimulationRequest,
    SweepRequest,
    SweepResult,
    VoltageSource,
    Wire,
)

from antsim.exporters import (
    export_nec,
    export_sweep_csv,
    export_sweep_nec,
)

from antsim.i18n import (
    SUPPORTED_LANGUAGES,
    set_language,
    translate as _,
)

from antsim.projects import (
    ProjectFormatError,
    load_project,
)

from antsim.importers import (
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
        _("AntSim version: {version}").format(
            version=antsim.__version__
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
        from antsim.engines.pynec import check_runtime

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
    from antsim.engines.pynec import PyNecEngine

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

    print()

    if bandwidth is None:
        print(
            _(
                "Bandwidth: no interval with "
                "SWR <= {limit:.2f}"
            ).format(limit=swr_limit)
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

    from antsim.engines.pynec import PyNecEngine

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
    """Valida un archivo de proyecto AntSim."""
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
    """Carga y simula un proyecto AntSim."""
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

    from antsim.engines.pynec import PyNecEngine

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
    """Carga y ejecuta el barrido de un proyecto AntSim."""
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

    from antsim.engines.pynec import PyNecEngine

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

def create_parser() -> argparse.ArgumentParser:
    """Construye el analizador de argumentos."""
    parser = argparse.ArgumentParser(
        prog="antsim",
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
        version=f"%(prog)s {antsim.__version__}",
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
        help=_("Validate an AntSim project file."),
    )

    validate_parser.add_argument(
        "project",
        type=Path,
        help=_("AntSim project file to validate."),
    )

    validate_parser.set_defaults(
        handler=run_validate_project
    )

    simulate_parser = commands.add_parser(
        "simulate",
        help=_("Simulate an AntSim project file."),
    )

    simulate_parser.add_argument(
        "project",
        type=Path,
        help=_("AntSim project file to simulate."),
    )

    project_sweep_parser = commands.add_parser(
        "sweep",
        help=_("Sweep frequencies for an AntSim project."),
    )

    project_sweep_parser.add_argument(
        "project",
        type=Path,
        help=_("AntSim project file to sweep."),
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
        help=_("Export an AntSim project as a NEC file."),
    )

    export_nec_parser.add_argument(
        "project",
        type=Path,
        help=_("AntSim project file to export."),
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
    
    export_nec_parser.set_defaults(
        handler=run_export_nec
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

    return parser

def run_export_nec(
    arguments: argparse.Namespace,
) -> int:
    """Exporta un proyecto AntSim como archivo NEC."""
    try:
        project = load_project(arguments.project)

        if arguments.sweep:
            request = project.to_sweep_request()
        else:
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
        if arguments.sweep:
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
