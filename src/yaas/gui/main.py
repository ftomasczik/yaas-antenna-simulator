"""Punto de entrada `yaas-gui` de la interfaz gráfica experimental.

Qt se carga de forma perezosa: `--version` y `--help` funcionan sin el
extra opcional `gui`, y la falta de PySide6 se informa con un mensaje
breve, sin traceback.

Códigos de salida (misma convención que la CLI):

- 0: la ventana se ejecutó y se cerró correctamente;
- 1: Qt no está instalado o no pudo cargarse, o la prueba de humo
  falló.
"""

import argparse
import sys
from collections.abc import Sequence

import yaas

INSTALL_HINT = (
    "yaas-gui: the graphical interface requires the optional 'gui' "
    "dependencies. Install them with: "
    'python -m pip install "yet-another-antenna-simulator[gui]"'
)

# Módulos que la GUI nunca debe cargar: no usa el motor. (numpy sí se
# carga: lo usa Matplotlib.)
_ENGINE_MODULES = ("PyNEC", "yaas.engines.pynec")

# Paquetes del extra opcional "gui": si falta cualquiera, se pide
# instalar el extra en vez de mostrar un traceback.
_GUI_PACKAGES = ("PySide6", "shiboken6", "matplotlib")


def _create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="yaas-gui",
        description=(
            "Experimental YAAS graphical interface. It does not open "
            "projects or run simulations yet."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {yaas.__version__}",
    )
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help=(
            "Open the main window, process the event loop once and "
            "close it automatically (for automated checks)."
        ),
    )
    parser.add_argument(
        "--smoke-export",
        action="append",
        default=[],
        metavar="IMAGE",
        help=(
            "With --smoke-test, draw a built-in synthetic cut and save "
            "it to IMAGE (.png, .svg or .pdf); can be repeated. Only "
            "for automated checks of the plotting stack."
        ),
    )
    return parser


def _is_gui_import_error(error: ImportError) -> bool:
    """Indica si el error proviene de una dependencia del extra gui."""
    name = error.name or ""
    return name.split(".")[0] in _GUI_PACKAGES


def _smoke_pattern():
    """Corte sintético solo para --smoke-export (con un nulo y un recorte)."""
    from yaas.domain import RadiationPatternResult

    return RadiationPatternResult(
        frequency_mhz=14.15,
        theta_angles_deg=(90.0,),
        phi_angles_deg=(0.0, 90.0, 180.0, 270.0, 360.0),
        gain_db=((None, 2.0, -60.0, 1.0, None),),
    )


def _run_window(
    smoke_test: bool,
    qt_arguments: list[str],
    smoke_exports: Sequence[str] = (),
) -> int:
    from pathlib import Path

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from yaas.gui.window import MainWindow

    application = QApplication.instance() or QApplication(qt_arguments)
    window = MainWindow()
    window.show()

    if not smoke_test:
        return application.exec()

    observed: dict[str, bool] = {}

    def finish() -> None:
        # Siempre cierra y sale: una excepción dentro de un callback de
        # Qt no interrumpe el event loop, y sin quit() el proceso
        # quedaría colgado.
        try:
            observed["visible"] = window.isVisible()
            plot = window.radiation_pattern_plot
            observed["canvas"] = plot.adapter.canvas.isVisible()
            if smoke_exports:
                plot.show_azimuth(
                    _smoke_pattern(), theta_index=0, floor_db=-40.0
                )
                observed["exported"] = all(
                    plot.adapter.save_image(path).stat().st_size > 0
                    for path in smoke_exports
                )
        except Exception as error:  # noqa: BLE001 - se informa y se sale con 1
            observed["error"] = True
            print(f"yaas-gui: smoke test failed: {error}", file=sys.stderr)
        finally:
            window.close()
            application.quit()

    QTimer.singleShot(0, finish)
    application.exec()

    engine_loaded = any(name in sys.modules for name in _ENGINE_MODULES)
    exported = observed.get("exported", True) and all(
        Path(path).is_file() for path in smoke_exports
    )
    if (
        not observed.get("error")
        and observed.get("visible")
        and observed.get("canvas")
        and exported
        and not window.isVisible()
        and not engine_loaded
    ):
        return 0
    return 1


def main(arguments: Sequence[str] | None = None) -> int:
    """Ejecuta la interfaz gráfica.

    Args:
        arguments: Argumentos sin el nombre del programa; ``None`` usa
            ``sys.argv[1:]``.

    Returns:
        Código de salida del proceso.
    """
    raw_arguments = sys.argv[1:] if arguments is None else list(arguments)
    parser = _create_parser()
    namespace = parser.parse_args(raw_arguments)
    if namespace.smoke_export and not namespace.smoke_test:
        parser.error("--smoke-export requires --smoke-test")

    try:
        return _run_window(
            smoke_test=namespace.smoke_test,
            qt_arguments=[sys.argv[0] if sys.argv else "yaas-gui"],
            smoke_exports=namespace.smoke_export,
        )
    except ModuleNotFoundError as error:
        if not _is_gui_import_error(error):
            raise
        print(INSTALL_HINT, file=sys.stderr)
        return 1
    except ImportError as error:
        # La dependencia está instalada pero no se pudo cargar (por
        # ejemplo, una biblioteca de sistema de Qt ausente en Linux).
        if not _is_gui_import_error(error):
            raise
        print(f"yaas-gui: could not load the GUI libraries: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
