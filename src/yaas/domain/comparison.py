"""Comparación de impedancias sobre la grilla medida, sin extrapolación."""

import math
from bisect import bisect_left
from dataclasses import dataclass

from yaas.domain.calculations import calculate_swr
from yaas.domain.models import MeasurementSweep, SweepResult


@dataclass(frozen=True)
class ComparisonPoint:
    """Valores normalizados; diferencias definidas como medición menos simulación."""

    frequency_mhz: float
    simulated_impedance: complex
    measured_impedance: complex
    simulated_swr: float
    measured_swr: float
    interpolated: bool

    @property
    def impedance_difference(self) -> complex:
        return self.measured_impedance - self.simulated_impedance

    @property
    def swr_difference(self) -> float:
        return self.measured_swr - self.simulated_swr


@dataclass(frozen=True)
class SweepComparison:
    """Comparación con Z₀ común y cantidad explícita de mediciones fuera de rango."""

    reference_impedance: float
    points: tuple[ComparisonPoint, ...]
    excluded_measurement_points: int


def _require_finite_impedance(value: complex) -> None:
    if not (math.isfinite(value.real) and math.isfinite(value.imag)):
        raise ValueError("La comparación requiere impedancias finitas.")


def compare_sweeps(
    simulation: SweepResult,
    measurement: MeasurementSweep,
    *,
    reference_impedance: float,
) -> SweepComparison:
    """Compara sobre frecuencias medidas incluidas en el rango simulado.

    Z₀ es obligatoria, resistiva, positiva y finita. Las ROE almacenadas
    en la simulación no se utilizan. Se interpolan R y X por separado
    entre muestras adyacentes; coincidencias exactas usan la muestra.
    No hay tolerancia implícita ni extrapolación. Un único punto común
    es válido. Se rechazan grillas inválidas, impedancias no finitas en
    cualquier entrada y ROE/diferencias no finitas en puntos comparados.
    """
    if not math.isfinite(reference_impedance) or reference_impedance <= 0:
        raise ValueError("La impedancia de referencia debe ser positiva y finita.")

    frequencies = []
    previous = 0.0
    for point in simulation.points:
        frequency = point.frequency_mhz
        if not math.isfinite(frequency) or frequency <= previous:
            raise ValueError("Las frecuencias simuladas deben ser positivas, finitas y crecientes.")
        _require_finite_impedance(point.impedance)
        frequencies.append(frequency)
        previous = frequency

    # Validar también fuera del solapamiento: no ocultar entradas inválidas.
    for point in measurement.points:
        _require_finite_impedance(point.impedance)

    points = []
    excluded = 0
    for point in measurement.points:
        frequency = point.frequency_mhz
        if frequency < frequencies[0] or frequency > frequencies[-1]:
            excluded += 1
            continue

        index = bisect_left(frequencies, frequency)
        interpolated = frequencies[index] != frequency
        if interpolated:
            left = simulation.points[index - 1]
            right = simulation.points[index]
            weight = (frequency - left.frequency_mhz) / (
                right.frequency_mhz - left.frequency_mhz
            )
            impedance = (1 - weight) * left.impedance + weight * right.impedance
        else:
            impedance = simulation.points[index].impedance
        _require_finite_impedance(impedance)

        simulated_swr = calculate_swr(impedance, reference_impedance)
        measured_swr = calculate_swr(point.impedance, reference_impedance)
        if not all(math.isfinite(value) for value in (simulated_swr, measured_swr)):
            raise ValueError("La comparación requiere ROE recalculadas finitas.")

        result = ComparisonPoint(
            frequency_mhz=frequency,
            simulated_impedance=impedance,
            measured_impedance=point.impedance,
            simulated_swr=simulated_swr,
            measured_swr=measured_swr,
            interpolated=interpolated,
        )
        _require_finite_impedance(result.impedance_difference)
        if not math.isfinite(result.swr_difference):
            raise ValueError("La comparación requiere diferencias finitas.")
        points.append(result)

    if not points:
        raise ValueError("No hay frecuencias medidas dentro del rango simulado.")

    return SweepComparison(reference_impedance, tuple(points), excluded)
