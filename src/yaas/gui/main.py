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

# Módulos que la ventana mínima nunca debe cargar: no usa el motor.
_ENGINE_MODULES = ("PyNEC", "yaas.engines.pynec", "numpy")

_QT_PACKAGES = ("PySide6", "shiboken6")


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
    return parser


def _is_qt_import_error(error: ImportError) -> bool:
    """Indica si el error proviene de PySide6/shiboken6 y no de YAAS."""
    name = error.name or ""
    return name.split(".")[0] in _QT_PACKAGES


def _run_window(smoke_test: bool, qt_arguments: list[str]) -> int:
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
        observed["visible"] = window.isVisible()
        window.close()
        application.quit()

    QTimer.singleShot(0, finish)
    application.exec()

    engine_loaded = any(name in sys.modules for name in _ENGINE_MODULES)
    if observed.get("visible") and not window.isVisible() and not engine_loaded:
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
    namespace = _create_parser().parse_args(raw_arguments)

    try:
        return _run_window(
            smoke_test=namespace.smoke_test,
            qt_arguments=[sys.argv[0] if sys.argv else "yaas-gui"],
        )
    except ModuleNotFoundError as error:
        if not _is_qt_import_error(error):
            raise
        print(INSTALL_HINT, file=sys.stderr)
        return 1
    except ImportError as error:
        # PySide6 está instalado pero no se pudo cargar (por ejemplo,
        # una biblioteca de sistema de Qt ausente en Linux).
        if not _is_qt_import_error(error):
            raise
        print(f"yaas-gui: could not load Qt: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
