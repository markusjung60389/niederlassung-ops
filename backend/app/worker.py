"""Worker entry point.

Replaces the `sleep(31536000)` placeholder: rolls recurring compliance records
over and keeps action escalation levels in step with how long they are overdue.

Run with `python -m app.worker`.
"""

from __future__ import annotations

import logging
import signal
import sys
import time
from types import FrameType

from . import jobs
from .config import settings
from .database import SessionLocal

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger("app.worker")

_stopping = False


def _handle_signal(signum: int, _frame: FrameType | None) -> None:
    global _stopping
    logger.info("received signal %s, finishing the current cycle", signum)
    _stopping = True


def run_once() -> jobs.JobResult:
    with SessionLocal() as db:
        return jobs.run_all(db)


def main() -> int:
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    logger.info("worker started, interval %ss", settings.worker_interval_seconds)
    while not _stopping:
        try:
            run_once()
        except Exception:
            # A failing cycle must not kill the worker; the next one retries.
            logger.exception("worker cycle failed")

        # Sleep in short steps so a shutdown signal is picked up promptly.
        for _ in range(settings.worker_interval_seconds):
            if _stopping:
                break
            time.sleep(1)

    logger.info("worker stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
