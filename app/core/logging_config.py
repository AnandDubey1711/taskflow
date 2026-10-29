import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime

request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)

STANDARD_RECORD_FIELDS = set(vars(logging.makeLogRecord({}))) | {"message", "request_id"}


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_context.get()
        return True


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if getattr(record, "request_id", None):
            log_entry["request_id"] = record.request_id
        extra_fields = {
            field_name: value
            for field_name, value in vars(record).items()
            if field_name not in STANDARD_RECORD_FIELDS
        }
        log_entry.update(extra_fields)
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, default=str)


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    handler.addFilter(RequestIdFilter())
    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(logging.INFO)
