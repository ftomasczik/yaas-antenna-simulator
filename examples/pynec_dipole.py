"""Prueba directa de PyNEC con un dipolo de media onda."""

from PyNEC import nec_context


FREQUENCY_MHZ = 14.15
DIPOLE_LENGTH_M = 10.06
WIRE_RADIUS_M = 0.001
SEGMENTS = 101
FEED_SEGMENT = 51


def simulate_dipole() -> complex:
    """Simula un dipolo horizontal en espacio libre.

    Returns:
        La impedancia compleja en el punto de alimentación.
    """
    context = nec_context()
    geometry = context.get_geometry()

    half_length = DIPOLE_LENGTH_M / 2

    # Dipolo horizontal sobre el eje X, centrado en el origen.
    geometry.wire(
        1,                  # Identificador del conductor
        SEGMENTS,           # Cantidad de segmentos
        -half_length,       # X inicial
        0.0,                # Y inicial
        0.0,                # Z inicial
        half_length,        # X final
        0.0,                # Y final
        0.0,                # Z final
        WIRE_RADIUS_M,      # Radio del conductor
        1.0,                # Relación de longitud inicial
        1.0,                # Relación de longitud final
    )

    # Finaliza la definición de la geometría.
    # El valor 0 indica que no hay plano de tierra.
    context.geometry_complete(0)

    # Condición de espacio libre.
    context.gn_card(
        -1,     # Sin tierra
        0,      # Sin radiales
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
    )

    # Configura una única frecuencia, expresada en MHz.
    context.fr_card(
        0,                  # Barrido lineal
        1,                  # Una frecuencia
        FREQUENCY_MHZ,      # Frecuencia inicial
        0.0,                # Sin incremento
    )

    # Fuente de tensión en el segmento central del dipolo.
    context.ex_card(
        0,                  # Fuente de tensión aplicada
        1,                  # Etiqueta del conductor
        FEED_SEGMENT,       # Segmento alimentado
        0,
        1.0,                # Parte real de la tensión
        0.0,                # Parte imaginaria de la tensión
        0.0,
        0.0,
        0.0,
        0.0,
    )

    # Ejecuta la simulación.
    context.xq_card(0)

    # Obtiene la impedancia calculada por NEC2++.
    raw_impedance = context.get_input_parameters(0).get_impedance()

    # PyNEC devuelve un ndarray de NumPy incluso cuando existe
    # una única excitación. Lo normalizamos a un complex de Python.
    return complex(raw_impedance.item())


def calculate_swr(
    impedance: complex,
    reference_impedance: float = 50.0,
) -> float:
    """Calcula la ROE para una impedancia de referencia.

    Args:
        impedance: Impedancia compleja de la antena.
        reference_impedance: Impedancia característica del sistema.

    Returns:
        Relación de ondas estacionarias.
    """
    reflection_coefficient = (
        (impedance - reference_impedance)
        / (impedance + reference_impedance)
    )

    magnitude = abs(reflection_coefficient)

    return (1 + magnitude) / (1 - magnitude)


def main() -> None:
    """Ejecuta y muestra la simulación de referencia."""
    impedance = simulate_dipole()
    swr = calculate_swr(impedance)

    print(f"Frecuencia: {FREQUENCY_MHZ:.3f} MHz")
    print(f"Longitud: {DIPOLE_LENGTH_M:.3f} m")
    print(
        "Impedancia: "
        f"{impedance.real:.2f} "
        f"{impedance.imag:+.2f}j ohm"
    )
    print(f"ROE respecto de 50 ohm: {swr:.2f}")


if __name__ == "__main__":
    main()