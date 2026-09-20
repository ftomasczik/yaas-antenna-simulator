"""Interfaz de línea de comandos del simulador."""

import argparse
import platform
import sys
from collections.abc import Sequence

import antsim
from antsim.domain import (
    Point3D,
    SimulationRequest,
    VoltageSource,
    Wire,
)
from antsim.engines import PyNecEngine


def create_reference_dipole_request() -> SimulationRequest:
    """Crea el dipolo utilizado como modelo de referencia."""
    dipole = Wire(
        tag=1,
        start=Point3D(-5.03, 0.0, 0.0),
        end=Point3D(5.03, 0.0, 0.0),
        radius_m=0.001,
        segments=101,
    )

    return SimulationRequest(
        frequency_mhz=14.15,
        wires=(dipole,),
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
    dipole_parser.set_defaults(handler=run_reference_dipole)

    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    """Punto de entrada de la CLI."""
    parser = create_parser()
    namespace = parser.parse_args(arguments)

    return namespace.handler(namespace)


if __name__ == "__main__":
    sys.exit(main())
    