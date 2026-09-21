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
    VoltageSource,
    Wire,
)
from antsim.engines import PyNecEngine
from antsim.exporters import export_sweep_csv


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


def run_doctor(_: argparse.Namespace) -> int:
    """Comprueba los componentes fundamentales del programa."""
    print(f"AntSim: {antsim.__version__}")
    print(f"Python: {platform.python_version()}")
    print(f"Sistema: {platform.system()} {platform.machine()}")

    try:
        from PyNEC import nec_context

        context = nec_context()
        del context
    except Exception as error:
        print(f"PyNEC: ERROR — {error}")
        return 1

    print("PyNEC: OK")
    print("Entorno: OK")

    return 0


def run_reference_dipole(_: argparse.Namespace) -> int:
    """Simula y presenta el dipolo de referencia."""
    request = create_reference_dipole_request()
    engine = PyNecEngine()
    result = engine.simulate(request)

    print(f"Frecuencia: {result.frequency_mhz:.3f} MHz")
    print(
        "Impedancia: "
        f"{result.impedance.real:.2f} "
        f"{result.impedance.imag:+.2f}j ohm"
    )
    print(
        "ROE respecto de "
        f"{request.reference_impedance:.0f} ohm: "
        f"{result.swr:.2f}"
    )

    return 0


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
                "El límite de ROE debe ser finito "
                "y mayor o igual a 1."
            )

        request = create_reference_sweep_request(
            start_frequency_mhz=arguments.start,
            stop_frequency_mhz=arguments.stop,
            points=arguments.points,
        )
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2

    engine = PyNecEngine()
    result = engine.simulate_sweep(request)

    resonance = result.resonance_point
    minimum_swr = result.minimum_swr_point
    bandwidth = result.swr_bandwidth(
        arguments.swr_limit
    )

    print(
        "Barrido: "
        f"{request.start_frequency_mhz:.3f}–"
        f"{request.stop_frequency_mhz:.3f} MHz"
    )
    print(f"Puntos: {len(result.points)}")

    print()
    print("Resonancia aproximada:")
    print(
        f"  Frecuencia: "
        f"{resonance.frequency_mhz:.3f} MHz"
    )
    print(
        "  Impedancia: "
        f"{resonance.impedance.real:.2f} "
        f"{resonance.impedance.imag:+.2f}j ohm"
    )
    print(f"  ROE: {resonance.swr:.2f}")

    print()
    print("ROE mínima:")
    print(
        f"  Frecuencia: "
        f"{minimum_swr.frequency_mhz:.3f} MHz"
    )
    print(
        "  Impedancia: "
        f"{minimum_swr.impedance.real:.2f} "
        f"{minimum_swr.impedance.imag:+.2f}j ohm"
    )
    print(f"  ROE: {minimum_swr.swr:.2f}")

    print()

    if bandwidth is None:
        print(
            "Ancho de banda: no existe un intervalo "
            f"con ROE ≤ {arguments.swr_limit:.2f}"
        )
    else:
        print(
            "Ancho de banda para "
            f"ROE ≤ {arguments.swr_limit:.2f}:"
        )
        print(
            "  Frecuencia inferior: "
            f"{bandwidth.lower_frequency_mhz:.3f} MHz"
        )
        print(
            "  Frecuencia superior: "
            f"{bandwidth.upper_frequency_mhz:.3f} MHz"
        )
        print(
            f"  Ancho: {bandwidth.bandwidth_khz:.1f} kHz"
        )
        print(
            "  Ancho porcentual: "
            f"{bandwidth.fractional_bandwidth_percent:.2f} %"
        )

    if arguments.output is not None:
        output_path = export_sweep_csv(
            result=result,
            destination=arguments.output,
        )

        print()
        print(f"Archivo CSV: {output_path.resolve()}")

    return 0


def create_parser() -> argparse.ArgumentParser:
    """Construye el analizador de argumentos."""
    parser = argparse.ArgumentParser(
        prog="antsim",
        description="Simulador de antenas basado en NEC2++.",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {antsim.__version__}",
    )

    commands = parser.add_subparsers(
        title="comandos",
        dest="command",
        required=True,
    )

    doctor_parser = commands.add_parser(
        "doctor",
        help="Comprueba el entorno de ejecución.",
    )
    doctor_parser.set_defaults(handler=run_doctor)

    dipole_parser = commands.add_parser(
        "simulate-dipole",
        help="Simula el dipolo interno de referencia.",
    )
    dipole_parser.set_defaults(
        handler=run_reference_dipole
    )

    sweep_parser = commands.add_parser(
        "sweep-dipole",
        help="Barre frecuencias sobre el dipolo de referencia.",
    )

    sweep_parser.add_argument(
        "--start",
        type=float,
        default=13.0,
        help=(
            "Frecuencia inicial en MHz "
            "(predeterminado: 13.0)."
        ),
    )

    sweep_parser.add_argument(
        "--stop",
        type=float,
        default=16.0,
        help=(
            "Frecuencia final en MHz "
            "(predeterminado: 16.0)."
        ),
    )

    sweep_parser.add_argument(
        "--points",
        type=int,
        default=61,
        help=(
            "Cantidad de puntos "
            "(predeterminado: 61)."
        ),
    )

    sweep_parser.add_argument(
        "--swr-limit",
        type=float,
        default=2.0,
        help=(
            "Límite de ROE para el ancho de banda "
            "(predeterminado: 2.0)."
        ),
    )

    sweep_parser.add_argument(
        "--output",
        type=Path,
        help="Archivo CSV donde guardar el barrido.",
    )

    sweep_parser.set_defaults(
        handler=run_reference_sweep
    )

    return parser


def main(
    arguments: Sequence[str] | None = None,
) -> int:
    """Punto de entrada de la CLI."""
    parser = create_parser()
    namespace = parser.parse_args(arguments)

    return namespace.handler(namespace)


if __name__ == "__main__":
    sys.exit(main())