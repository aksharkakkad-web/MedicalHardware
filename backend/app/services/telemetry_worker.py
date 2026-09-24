"""Single-lane durable telemetry consumer for the V1 application process."""

from __future__ import annotations

from collections.abc import Callable
from queue import Queue
from threading import Condition, Thread
from time import monotonic

from sqlalchemy.orm import Session

from backend.app.db.telemetry_repositories import TelemetryRepository
from backend.app.intelligence.orchestration import MonitoringIntelligenceEngine
from backend.app.services.telemetry_processing import TelemetryProcessingCoordinator


SessionFactory = Callable[[], Session]


class TelemetryProcessingWorker:
    """Queue committed batch IDs and restore unfinished work on startup."""

    def __init__(
        self,
        session_factory: SessionFactory,
        engine: MonitoringIntelligenceEngine,
        *,
        startup_limit: int = 10_000,
    ) -> None:
        if isinstance(startup_limit, bool) or not isinstance(startup_limit, int):
            raise ValueError("startup_limit must be a positive integer")
        if startup_limit < 1:
            raise ValueError("startup_limit must be a positive integer")
        self._session_factory = session_factory
        self._engine = engine
        self._startup_limit = startup_limit
        self._queue: Queue[str | None] = Queue()
        self._condition = Condition()
        self._scheduled: set[str] = set()
        self._running = False
        self._thread: Thread | None = None

    def start(self) -> None:
        with self._condition:
            if self._running:
                raise RuntimeError("telemetry worker is already running")
            self._running = True
            self._thread = Thread(
                target=self._run,
                name="telemetry-processing-worker",
                daemon=True,
            )
            self._thread.start()
        with self._session_factory() as session:
            unfinished = TelemetryRepository(session).pending_batches(
                limit=self._startup_limit
            )
        for batch in unfinished:
            self.enqueue(batch.batch_id)

    def enqueue(self, batch_id: str) -> None:
        if not isinstance(batch_id, str) or not batch_id.strip():
            raise ValueError("batch_id must be nonblank text")
        normalized = batch_id.strip()
        with self._condition:
            if not self._running:
                raise RuntimeError("telemetry worker is not running")
            if normalized in self._scheduled:
                return
            self._scheduled.add(normalized)
            self._queue.put(normalized)
            self._condition.notify_all()

    def wait_until_idle(self, *, timeout: float) -> bool:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        deadline = monotonic() + timeout
        with self._condition:
            while self._scheduled:
                remaining = deadline - monotonic()
                if remaining <= 0:
                    return False
                self._condition.wait(timeout=remaining)
            return True

    def stop(self) -> None:
        thread: Thread | None
        with self._condition:
            if not self._running:
                return
            thread = self._thread
        self.wait_until_idle(timeout=190.0)
        with self._condition:
            self._running = False
            self._queue.put(None)
        if thread is not None:
            thread.join(timeout=5.0)

    def _run(self) -> None:
        while True:
            batch_id = self._queue.get()
            if batch_id is None:
                return
            try:
                with self._session_factory() as session:
                    TelemetryProcessingCoordinator(
                        session,
                        self._engine,
                    ).process_batch(batch_id)
            finally:
                with self._condition:
                    self._scheduled.discard(batch_id)
                    self._condition.notify_all()


__all__ = ["TelemetryProcessingWorker"]
