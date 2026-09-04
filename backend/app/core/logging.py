"""结构化日志：统一记录 paper_id / job_id / task / status / error / duration。"""

import json
import logging
import sys
import time
from contextlib import contextmanager

_LOGGER_NAME = "paperhub"


def setup_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    root = logging.getLogger(_LOGGER_NAME)
    root.setLevel(level)
    root.handlers = [handler]
    root.propagate = False


def get_logger(name: str | None = None) -> logging.Logger:
    return logging.getLogger(_LOGGER_NAME if name is None else f"{_LOGGER_NAME}.{name}")


def log_event(
    level: int,
    event: str,
    *,
    paper_id: str | None = None,
    job_id: str | None = None,
    task: str | None = None,
    status: str | None = None,
    error: str | None = None,
    duration: float | None = None,
    **extra,
) -> None:
    payload = {
        "event": event,
        "paper_id": paper_id,
        "job_id": job_id,
        "task": task,
        "status": status,
        "error": error,
        "duration": duration,
    }
    payload.update({k: v for k, v in extra.items() if v is not None})
    # 不打印任何 secret / token / api key
    for key in list(payload):
        if any(
            s in key.lower() for s in ("secret", "token", "api_key", "apikey", "key")
        ):
            payload.pop(key, None)
    logging.getLogger(_LOGGER_NAME).log(
        level, json.dumps(payload, ensure_ascii=False, default=str)
    )


@contextmanager
def timed(event: str, **ctx):
    start = time.perf_counter()
    try:
        yield
    finally:
        log_event(
            logging.INFO, event, duration=round(time.perf_counter() - start, 3), **ctx
        )
