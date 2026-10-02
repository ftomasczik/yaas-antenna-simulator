"""Motores falsos y esperas para las pruebas del cálculo en segundo plano.

No importa Qt ni PyNEC. `wait_until` recibe la función que procesa los
eventos de Qt, para que este módulo siga sin depender de PySide6.
"""

import threading
import time
from collections.abc import Callable

from yaas.domain import RadiationPatternRequest, RadiationPatternResult

WAIT_TIMEOUT_S = 10.0


def wait_until(
    predicate: Callable[[], bool],
    process_events: Callable[[], None],
    timeout_s: float = WAIT_TIMEOUT_S,
) -> None:
    """Procesa eventos hasta que ``predicate()`` sea verdadero."""
    deadline = time.monotonic() + timeout_s
    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError("timed out waiting for the condition")
        process_events()
        time.sleep(0.002)


def pattern_result(request: RadiationPatternRequest) -> RadiationPatternResult:
    """Resultado determinista con la grilla de la solicitud."""
    theta = request.theta.angles_deg
    phi = request.phi.angles_deg
    return RadiationPatternResult(
        frequency_mhz=request.frequency_mhz,
        theta_angles_deg=theta,
        phi_angles_deg=phi,
        gain_db=tuple(
            tuple(2.0 - 0.01 * i - 0.001 * j for j in range(len(phi)))
            for i in range(len(theta))
        ),
    )


class FakeEngine:
    """Motor falso: opcionalmente bloquea (como una llamada nativa) o falla.

    ``gate``: si se indica, la "llamada nativa" espera a que se libere.
    ``started``: se activa cuando la llamada empezó.
    """

    def __init__(
        self,
        *,
        gate: threading.Event | None = None,
        error: Exception | None = None,
        result: Callable[[RadiationPatternRequest], RadiationPatternResult]
        | None = None,
    ) -> None:
        self.gate = gate
        self.error = error
        self.result = result or pattern_result
        self.started = threading.Event()
        self.calls: list[RadiationPatternRequest] = []
        self.call_threads: list[int] = []

    def simulate_radiation_pattern(
        self, request: RadiationPatternRequest
    ) -> RadiationPatternResult:
        self.calls.append(request)
        self.call_threads.append(threading.get_ident())
        self.started.set()
        if self.gate is not None and not self.gate.wait(WAIT_TIMEOUT_S):
            raise TimeoutError("gate never released")
        if self.error is not None:
            raise self.error
        return self.result(request)

    def simulate(self, request):  # pragma: no cover - no se usa
        raise NotImplementedError

    def simulate_sweep(self, request):  # pragma: no cover - no se usa
        raise NotImplementedError


class EngineFactory:
    """Fábrica falsa que registra en qué hilo se crea el motor."""

    def __init__(
        self,
        engine: FakeEngine | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        self.engine = engine or FakeEngine()
        # Si se indica, la creación del motor falla (como un PyNEC roto).
        self.error = error
        self.created_in: list[int] = []

    def __call__(self) -> FakeEngine:
        self.created_in.append(threading.get_ident())
        if self.error is not None:
            raise self.error
        return self.engine
