"""Ejecución de trabajos fuera del hilo de la interfaz (ADR 0010).

`SimulationRunner` ejecuta un trabajo por vez en un `QThread` con un
worker `QObject` (`moveToThread`), y entrega el resultado al hilo
principal mediante señales encoladas.

Cancelación (ver docs/research/gui-radiation-visualization.md, §8):

- es **cooperativa**: el trabajo recibe un `CancellationToken` y lo
  revisa entre llamadas (`raise_if_cancelled`);
- una llamada nativa en curso (por ejemplo, el cálculo de NEC2++ dentro
  de PyNEC) **no puede interrumpirse**: hay que esperar a que termine,
  y su resultado se descarta;
- nunca se usa `QThread.terminate()`.

Este módulo importa PySide6.QtCore, pero no conoce widgets, proyectos
ni motores: el trabajo es una función que recibe el token.
"""

import threading
import traceback
from collections.abc import Callable

from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot


class JobCancelled(Exception):
    """El trabajo se detuvo porque se pidió su cancelación."""


class CancellationToken:
    """Solicitud de cancelación compartida entre hilos."""

    def __init__(self) -> None:
        self._event = threading.Event()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def cancel(self) -> None:
        self._event.set()

    def raise_if_cancelled(self) -> None:
        """Punto de cancelación cooperativa entre llamadas."""
        if self._event.is_set():
            raise JobCancelled()


Job = Callable[[CancellationToken], object]


class _SimulationWorker(QObject):
    """Ejecuta un trabajo dentro del hilo secundario."""

    succeeded = Signal(int, object)
    failed = Signal(int, str, str)
    cancelled = Signal(int)

    def __init__(self, job_id: int, job: Job, token: CancellationToken) -> None:
        super().__init__()
        self._job_id = job_id
        self._job = job
        self._token = token

    @Slot()
    def run(self) -> None:
        try:
            self._token.raise_if_cancelled()
            result = self._job(self._token)
            if self._token.is_cancelled:
                # La cancelación llegó durante una llamada que no podía
                # interrumpirse: su resultado se descarta.
                self.cancelled.emit(self._job_id)
            else:
                self.succeeded.emit(self._job_id, result)
        except JobCancelled:
            self.cancelled.emit(self._job_id)
        except Exception as error:  # noqa: BLE001 - se entrega como señal
            self.failed.emit(
                self._job_id,
                f"{type(error).__name__}: {error}",
                traceback.format_exc(),
            )
        finally:
            # quit() es seguro entre hilos y no depende del event loop
            # principal: wait() en shutdown() puede esperar sin bloquearse.
            QThread.currentThread().quit()


class SimulationRunner(QObject):
    """Un trabajo por vez en un `QThread`, con cancelación cooperativa.

    Señales (siempre emitidas en el hilo principal):

    - ``succeeded(job_id, result)``;
    - ``failed(job_id, message, traceback)``;
    - ``cancelled(job_id)``: el trabajo se detuvo o su resultado se
      descartó;
    - ``busy_changed(bool)``.

    Cada trabajo termina con exactamente una de las tres primeras.
    """

    succeeded = Signal(int, object)
    failed = Signal(int, str, str)
    cancelled = Signal(int)
    busy_changed = Signal(bool)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._next_job_id = 1
        self._active_job_id: int | None = None
        self._token: CancellationToken | None = None
        # Hilos todavía vivos (el activo y los que están terminando), con
        # su trabajo y su worker: se conserva la referencia de Python al
        # worker mientras corre, hasta finished.
        self._threads: dict[QThread, tuple[int, _SimulationWorker]] = {}

    @property
    def is_busy(self) -> bool:
        return self._active_job_id is not None

    @property
    def is_cancelling(self) -> bool:
        return self._token is not None and self._token.is_cancelled

    @property
    def active_job_id(self) -> int | None:
        return self._active_job_id

    @property
    def thread_count(self) -> int:
        """Hilos del runner todavía vivos (para pruebas y diagnóstico)."""
        return len(self._threads)

    def submit(self, job: Job) -> int | None:
        """Inicia ``job`` en un hilo nuevo.

        Returns:
            El identificador del trabajo, o None si ya hay uno activo.
        """
        if self.is_busy:
            return None

        job_id = self._next_job_id
        self._next_job_id += 1
        token = CancellationToken()

        thread = QThread()
        worker = _SimulationWorker(job_id, job, token)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        queued = Qt.ConnectionType.QueuedConnection
        worker.succeeded.connect(self._on_succeeded, queued)
        worker.failed.connect(self._on_failed, queued)
        worker.cancelled.connect(self._on_cancelled, queued)
        # El worker se destruye dentro de su propio hilo, al terminar:
        # finished se emite en ese hilo y Qt procesa ahí el deleteLater
        # antes de que el hilo termine. (Llamar a deleteLater después,
        # desde el hilo principal, no lo destruiría nunca: el hilo del
        # worker ya no tiene event loop.)
        thread.finished.connect(worker.deleteLater)
        # Un método del runner (no una lambda): así la conexión encolada
        # se ejecuta en el hilo principal, donde vive el runner.
        thread.finished.connect(self._on_thread_finished, queued)

        thread.start()
        # Si el sistema no pudo crear el hilo, Qt solo emite una
        # advertencia: started y finished nunca llegarían y el runner
        # quedaría ocupado para siempre. Se detecta aquí y se informa.
        if not (thread.isRunning() or thread.isFinished()):
            raise RuntimeError("Could not start the calculation thread.")

        # Se registra después de start(): las señales encoladas del
        # worker recién se procesan cuando el hilo principal vuelve a su
        # event loop, así que no pueden adelantarse a este registro.
        self._threads[thread] = (job_id, worker)
        self._active_job_id = job_id
        self._token = token
        self.busy_changed.emit(True)
        return job_id

    def request_cancel(self) -> bool:
        """Pide cancelar el trabajo activo (no lo interrumpe).

        Returns:
            True si había un trabajo activo.
        """
        if self._token is None:
            return False
        self._token.cancel()
        return True

    def shutdown(self) -> None:
        """Cancela el trabajo activo y espera a que terminen sus hilos.

        Bloquea mientras termina la llamada nativa en curso, si la hay
        (no puede interrumpirse). Al volver no queda ningún hilo del
        runner en ejecución; un trabajo pendiente se informa como
        cancelado.
        """
        job_id = self._active_job_id
        self.request_cancel()
        for thread in list(self._threads):
            thread.wait()
            self._forget_thread(thread)
        # Las señales del worker que quedaron encoladas llegarán con un
        # job_id que ya no está activo y se ignorarán.
        if job_id is not None and self._active_job_id == job_id:
            self._finish()
            self.cancelled.emit(job_id)

    # -- Resultados del worker (hilo principal) ---------------------------

    def _on_succeeded(self, job_id: int, result: object) -> None:
        if job_id != self._active_job_id:
            return
        if self.is_cancelling:
            self._finish()
            self.cancelled.emit(job_id)
            return
        self._finish()
        self.succeeded.emit(job_id, result)

    def _on_failed(self, job_id: int, message: str, details: str) -> None:
        if job_id != self._active_job_id:
            return
        cancelled = self.is_cancelling
        self._finish()
        if cancelled:
            self.cancelled.emit(job_id)
        else:
            self.failed.emit(job_id, message, details)

    def _on_cancelled(self, job_id: int) -> None:
        if job_id != self._active_job_id:
            return
        self._finish()
        self.cancelled.emit(job_id)

    def _finish(self) -> None:
        self._active_job_id = None
        self._token = None
        self.busy_changed.emit(False)

    @Slot()
    def _on_thread_finished(self) -> None:
        thread = self.sender()
        if not isinstance(thread, QThread):
            return
        job_id = self._forget_thread(thread)
        # finished llega siempre después del resultado del worker (misma
        # cola, mismo orden). Si el trabajo sigue activo, el worker
        # terminó sin informar nada (por ejemplo, por una BaseException
        # que no es Exception): se informa como fallo para no quedar
        # ocupado para siempre.
        if job_id is not None and job_id == self._active_job_id:
            cancelled = self.is_cancelling
            self._finish()
            if cancelled:
                self.cancelled.emit(job_id)
            else:
                self.failed.emit(
                    job_id,
                    "RuntimeError: the calculation thread ended without a result.",
                    "",
                )

    def _forget_thread(self, thread: QThread) -> int | None:
        """Suelta el hilo y devuelve el trabajo que ejecutaba, si lo conocía."""
        entry = self._threads.pop(thread, None)
        if entry is None:
            return None
        # finished se emite *justo antes* de que el hilo termine: después
        # todavía procesa el deleteLater del worker. Soltar antes las
        # referencias de Python dejaría que PySide destruyera el worker
        # (o el QThread) desde el hilo principal al mismo tiempo, una
        # carrera que se reprodujo como access violation / abort al
        # encadenar miles de trabajos cortos. wait() garantiza que el
        # hilo terminó del todo; como ya está terminando, vuelve en
        # seguida (no es una espera activa).
        thread.wait()
        # El worker ya se destruyó en su hilo (finished -> deleteLater);
        # el QThread vive en el hilo principal y se destruye aquí.
        thread.deleteLater()
        return entry[0]
