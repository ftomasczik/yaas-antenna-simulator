"""Punto de entrada `yaas-gui` de la interfaz gráfica experimental.

Qt se carga de forma perezosa: `--version` y `--help` funcionan sin el
extra opcional `gui`, y la falta de PySide6 se informa con un mensaje
breve, sin traceback.

Uso: ``yaas-gui [PROJECT]``. Con un proyecto, la ventana lo abre al
iniciar; si no puede abrirse, lo informa con un diálogo y queda vacía.
El patrón de radiación se calcula desde el menú Calculate, fuera del
hilo principal; PyNEC recién se carga al iniciar ese cálculo.

Códigos de salida (misma convención que la CLI):

- 0: la ventana se ejecutó y se cerró correctamente;
- 1: Qt no está instalado o no pudo cargarse, o la prueba de humo
  falló (incluido no poder abrir el proyecto indicado);
- 2: argumentos inválidos.
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

# Módulos del motor: la GUI solo los carga al calcular un patrón (dentro
# del worker). (numpy sí se carga siempre: lo usa Matplotlib.)
_ENGINE_MODULES = ("PyNEC", "yaas.engines.pynec")

# Tiempo máximo de --smoke-calculate antes de darlo por fallido.
_SMOKE_CALCULATION_TIMEOUT_MS = 120_000

# Paquetes del extra opcional "gui": si falta cualquiera, se pide
# instalar el extra en vez de mostrar un traceback.
_GUI_PACKAGES = ("PySide6", "shiboken6", "matplotlib")


def _create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="yaas-gui",
        description=(
            "Experimental YAAS graphical interface. It can open .yaas "
            "projects and calculate their radiation pattern."
        ),
    )
    parser.add_argument(
        "project",
        nargs="?",
        metavar="PROJECT",
        help="Optional .yaas project to open at startup.",
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
            "Open the main window (and PROJECT, if given), process the "
            "event loop once and close it automatically (for automated "
            "checks). Fails if PROJECT cannot be opened."
        ),
    )
    parser.add_argument(
        "--smoke-export",
        action="append",
        default=[],
        metavar="IMAGE",
        help=(
            "With --smoke-test, draw a built-in synthetic cut (or, with "
            "--smoke-calculate, the calculated one) and save it to IMAGE "
            "(.png, .svg or .pdf); can be repeated. Only for automated "
            "checks of the plotting stack."
        ),
    )
    parser.add_argument(
        "--smoke-calculate",
        action="store_true",
        help=(
            "With --smoke-test and PROJECT, calculate the project's "
            "radiation pattern in the background and fail unless it is "
            "drawn (for automated checks of the engine)."
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


def _report_smoke_error(title: str, message: str) -> None:
    # En la prueba de humo un diálogo modal bloquearía el proceso: el
    # error se informa por stderr y la prueba falla.
    print(f"yaas-gui: {title}: {message}", file=sys.stderr)


def _run_window(
    smoke_test: bool,
    qt_arguments: list[str],
    smoke_exports: Sequence[str] = (),
    project: str | None = None,
    smoke_calculate: bool = False,
) -> int:
    from pathlib import Path

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from yaas.gui.controllers.pattern import PatternCalculationState
    from yaas.gui.window import MainWindow

    application = QApplication.instance() or QApplication(qt_arguments)
    window = MainWindow(
        error_presenter=_report_smoke_error if smoke_test else None
    )
    window.show()

    if not smoke_test:
        if project is not None:
            # Después de mostrar la ventana, para que un error aparezca
            # como diálogo sobre ella.
            QTimer.singleShot(0, lambda: window.open_project_path(project))
        return application.exec()

    observed: dict[str, bool] = {}
    plot = window.radiation_pattern_plot
    pattern = window.pattern_controller

    def fail(error: Exception | str) -> None:
        observed["error"] = True
        print(f"yaas-gui: smoke test failed: {error}", file=sys.stderr)

    def complete() -> None:
        # Siempre cierra y sale una sola vez: una excepción dentro de un
        # callback de Qt no interrumpe el event loop, y sin quit() el
        # proceso quedaría colgado. Cerrar la ventana también detiene
        # el worker (ver MainWindow.closeEvent).
        if observed.get("completed"):
            return
        observed["completed"] = True
        try:
            if smoke_exports:
                if not smoke_calculate:
                    plot.show_azimuth(
                        _smoke_pattern(), theta_index=0, floor_db=-40.0
                    )
                observed["exported"] = all(
                    plot.adapter.save_image(path).stat().st_size > 0
                    for path in smoke_exports
                )
        except Exception as error:  # noqa: BLE001 - se informa y se sale con 1
            fail(error)
        finally:
            window.close()
            application.quit()

    def on_calculation_state(state: PatternCalculationState) -> None:
        if pattern.is_busy:
            return
        observed["calculated"] = (
            state is PatternCalculationState.RESULT
            and plot.adapter.axes is not None
        )
        if not observed["calculated"]:
            fail(f"the radiation pattern was not calculated ({state.value})")
        complete()

    def on_timeout() -> None:
        if not observed.get("completed"):
            fail("the radiation pattern calculation timed out")
            complete()

    def start() -> None:
        try:
            observed["visible"] = window.isVisible()
            observed["canvas"] = plot.adapter.canvas.isVisible()
            if project is not None:
                observed["project"] = (
                    window.open_project_path(project)
                    and not window.project_summary.is_empty
                )
            if smoke_calculate and observed.get("project"):
                pattern.state_changed.connect(on_calculation_state)
                if pattern.calculate():
                    QTimer.singleShot(_SMOKE_CALCULATION_TIMEOUT_MS, on_timeout)
                    # complete() llega con el resultado.
                    return
                observed["calculated"] = False
        except Exception as error:  # noqa: BLE001 - se informa y se sale con 1
            fail(error)
        complete()

    QTimer.singleShot(0, start)
    application.exec()

    engine_loaded = any(name in sys.modules for name in _ENGINE_MODULES)
    exported = observed.get("exported", True) and all(
        Path(path).is_file() for path in smoke_exports
    )
    if (
        not observed.get("error")
        and observed.get("visible")
        and observed.get("canvas")
        and observed.get("project", True)
        and observed.get("calculated", not smoke_calculate)
        and exported
        and not window.isVisible()
        # Solo el cálculo puede cargar el motor, y no deja hilos vivos.
        and engine_loaded == smoke_calculate
        and pattern.runner.thread_count == 0
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
    if namespace.smoke_calculate and not (
        namespace.smoke_test and namespace.project
    ):
        parser.error("--smoke-calculate requires --smoke-test and PROJECT")

    try:
        return _run_window(
            smoke_test=namespace.smoke_test,
            qt_arguments=[sys.argv[0] if sys.argv else "yaas-gui"],
            smoke_exports=namespace.smoke_export,
            project=namespace.project,
            smoke_calculate=namespace.smoke_calculate,
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
