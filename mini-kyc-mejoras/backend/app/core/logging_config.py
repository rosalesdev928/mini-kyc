"""Logging with a request id, so every log line of one request can be found together."""

import logging
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

LOG_FORMAT = "%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"


def configure_logging() -> None:
    """Add `request_id` to every log record (works with the threadpool: contextvars are copied)."""
    previous_factory = logging.getLogRecordFactory()

    def factory(*args, **kwargs):
        record = previous_factory(*args, **kwargs)
        record.request_id = request_id_var.get()
        return record

    logging.setLogRecordFactory(factory)
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
