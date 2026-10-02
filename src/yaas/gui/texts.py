"""Textos visibles de la GUI experimental, centralizados.

La GUI todavía no tiene infraestructura de traducción: sus textos están
en inglés y se reúnen aquí para no dispersarlos entre widgets y
controladores. Este módulo no importa Qt.
"""

WINDOW_TITLE = "YAAS"
FULL_NAME = "Yet Another Antenna Simulator"
# Separador del título con proyecto: "YAAS — <nombre>".
TITLE_SEPARATOR = " — "

FILE_MENU = "&File"
OPEN_ACTION = "&Open…"
CLOSE_PROJECT_ACTION = "&Close project"
EXIT_ACTION = "E&xit"

OPEN_DIALOG_TITLE = "Open project"
PROJECT_FILE_FILTER = "YAAS projects (*.yaas)"
OPEN_ERROR_TITLE = "Could not open project"

RADIATION_PATTERN_TAB = "Radiation pattern"

CALCULATE_MENU = "&Calculate"
CALCULATE_PATTERN_ACTION = "Radiation &pattern"
CANCEL_CALCULATION_ACTION = "&Cancel calculation"
CALCULATION_ERROR_TITLE = "Radiation pattern calculation failed"

CALCULATION_STATUS_EMPTY = "Open a project with a radiation pattern to calculate it."
CALCULATION_STATUS_READY = "Ready to calculate the radiation pattern."
CALCULATION_STATUS_CALCULATING = "Calculating the radiation pattern…"
CALCULATION_STATUS_CANCELLING = (
    "Cancelling… The calculation already running inside the engine "
    "cannot be interrupted; its result will be discarded when it finishes."
)
CALCULATION_STATUS_ERROR = "Calculation failed: {message}"
CALCULATION_STATUS_NO_MAXIMUM = "Calculated: every gain is null."
CALCULATION_STATUS_RESULT = (
    "Calculated: maximum {gain:.2f} dBi at theta = {theta:g} deg, "
    "phi = {phi:g} deg."
)
# Patrones con varios cortes: todavía no hay selector.
CALCULATION_STATUS_MORE_CUTS = (
    "Showing the vertical cut at phi = {phi:g} deg; a cut selector is not "
    "available yet."
)

PROJECT_PANEL_TITLE = "Project"
NO_PROJECT_LOADED = "No project loaded"

FIELD_NAME = "Name"
FIELD_PATH = "Path"
FIELD_SCHEMA_VERSION = "Schema version"
FIELD_CONDUCTORS = "Conductors"
FIELD_FREQUENCY = "Frequency"
FIELD_REFERENCE_IMPEDANCE = "Reference impedance"
FIELD_ENVIRONMENT = "Environment"
FIELD_SWEEP = "Sweep available"
FIELD_RADIATION_PATTERN = "Radiation pattern available"
FIELD_THETA = "theta"
FIELD_PHI = "phi"

YES = "Yes"
NO = "No"

ENVIRONMENT_FREE_SPACE = "Free space"
ENVIRONMENT_PERFECT_GROUND = "Perfect ground"
ENVIRONMENT_REAL_GROUND = "Real ground"
REAL_GROUND_MODEL_SOMMERFELD_NORTON = "Sommerfeld-Norton"


def window_title(project_name: str | None) -> str:
    """Título de la ventana, con el nombre del proyecto si hay uno."""
    if project_name is None:
        return WINDOW_TITLE
    return f"{WINDOW_TITLE}{TITLE_SEPARATOR}{project_name}"


def frequency_text(frequency_mhz: float) -> str:
    return f"{frequency_mhz:g} MHz"


def impedance_text(impedance_ohm: float) -> str:
    return f"{impedance_ohm:g} ohm"


def yes_no(value: bool) -> str:
    return YES if value else NO


def angular_axis_text(
    start_deg: float, stop_deg: float, count: int, step_deg: float
) -> str:
    """Descripción de un eje angular; theta se muestra como theta."""
    return (
        f"start {start_deg:g} deg, stop {stop_deg:g} deg, "
        f"count {count}, step {step_deg:g} deg"
    )
