"""Cálculos eléctricos independientes del motor de simulación."""

import math


def calculate_swr(
    impedance: complex,
    reference_impedance: float = 50.0,
) -> float:
    """Calcula la ROE respecto de una impedancia resistiva.

    Args:
        impedance: Impedancia compleja de la carga.
        reference_impedance: Impedancia característica del sistema.

    Returns:
        Relación de ondas estacionarias. Devuelve infinito para
        un circuito abierto, un cortocircuito o cuando el módulo
        del coeficiente de reflexión es igual o mayor que uno.

    Raises:
        ValueError: Si algún valor de entrada no es válido.
    """
    if not math.isfinite(reference_impedance):
        raise ValueError(
            "La impedancia de referencia debe ser finita."
        )

    if reference_impedance <= 0:
        raise ValueError(
            "La impedancia de referencia debe ser positiva."
        )

    if math.isnan(impedance.real) or math.isnan(impedance.imag):
        raise ValueError(
            "La impedancia no puede contener valores NaN."
        )

    # Una impedancia infinita representa un circuito abierto.
    if math.isinf(impedance.real) or math.isinf(impedance.imag):
        return math.inf

    denominator = impedance + reference_impedance

    # Z = -Z0 provocaría una división por cero.
    if denominator == 0:
        return math.inf

    reflection_coefficient = (
        impedance - reference_impedance
    ) / denominator

    magnitude = abs(reflection_coefficient)

    if magnitude >= 1:
        return math.inf

    return (1 + magnitude) / (1 - magnitude)

def reflection_coefficient_to_impedance(
    reflection_coefficient: complex,
    reference_impedance: float = 50.0,
) -> complex:
    """Convierte un coeficiente de reflexión en impedancia.

    Utiliza:

        Z = Z0 * (1 + gamma) / (1 - gamma)

    Un coeficiente de reflexión igual a 1 representa un
    circuito abierto.
    """
    if not math.isfinite(reference_impedance):
        raise ValueError(
            "La impedancia de referencia debe ser finita."
        )

    if reference_impedance <= 0:
        raise ValueError(
            "La impedancia de referencia debe ser positiva."
        )

    if (
        not math.isfinite(reflection_coefficient.real)
        or not math.isfinite(
            reflection_coefficient.imag
        )
    ):
        raise ValueError(
            "El coeficiente de reflexión debe ser finito."
        )

    denominator = 1 - reflection_coefficient

    if denominator == 0:
        return complex(math.inf, 0.0)

    return (
        reference_impedance
        * (1 + reflection_coefficient)
        / denominator
    )