"""Installed-module check for error-path privacy. Synthetic marker only."""

from __future__ import annotations

import logging
from pathlib import Path

from app.core.safe_errors import log_failure, public_validation_errors, safe_route_template
from app.routers import inventory as inventory_router
from app.routers import telemetry as telemetry_router
from app.services import chat_channel

MARKER = "SYNTH_ERR_PATH_714"
FORMATTER = logging.Formatter("%(name)s %(levelname)s %(message)s")


class _Request:
    def __init__(self, scope: dict) -> None:
        self.scope = scope


def main() -> None:
    logger = logging.getLogger("healthcore.errorpath.check")
    capture: list[str] = []

    class _Handler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            capture.append(FORMATTER.format(record))

    handler = _Handler()
    logger.addHandler(handler)
    logger.setLevel(logging.ERROR)
    logger.propagate = False
    try:
        try:
            raise RuntimeError(MARKER)
        except RuntimeError:
            log_failure(logger, "probe failed")
    finally:
        logger.removeHandler(handler)

    blob = "\n".join(capture)
    if MARKER in blob or "Traceback" in blob:
        raise SystemExit("LOG_LEAK")
    if safe_route_template(_Request({"route": None})) != "<unmatched>":
        raise SystemExit("ROUTE_UNMATCHED")

    telemetry_source = Path(telemetry_router.__file__).read_text(encoding="utf-8")
    inventory_source = Path(inventory_router.__file__).read_text(encoding="utf-8")
    if "public_validation_errors" not in telemetry_source:
        raise SystemExit("TELEMETRY_SANITIZER")
    if "public_validation_errors" not in inventory_source:
        raise SystemExit("INVENTORY_SANITIZER")

    errors = public_validation_errors(
        [
            {
                "type": "value_error",
                "loc": ("body", "categories"),
                "msg": f"Value error, invalid categories: ['{MARKER}']",
                "input": [MARKER],
                "ctx": {"error": MARKER},
            },
            {
                "type": "int_parsing",
                "loc": ("body", "properties", MARKER),
                "msg": "Input should be a valid integer",
                "input": "not-int",
            },
            {
                "type": "extra_forbidden",
                "loc": ("events", 0, MARKER),
                "msg": "Extra inputs are not permitted",
                "input": "x",
            },
        ]
    )
    if any("input" in item or "ctx" in item for item in errors):
        raise SystemExit("VALIDATION_LEAK")
    if MARKER in str(errors):
        raise SystemExit("VALIDATION_MARKER")
    if errors[0]["msg"] != "Invalid value.":
        raise SystemExit("CUSTOM_MSG")
    if errors[1]["loc"] != ["body", "properties", "*"]:
        raise SystemExit("DICT_KEY_LOC")
    if errors[2]["loc"] != ["events", 0, "*"]:
        raise SystemExit("EXTRA_KEY_LOC")

    chat_source = Path(chat_channel.__file__).read_text(encoding="utf-8")
    if "HealthCore chat generation failed" not in chat_source:
        raise SystemExit("CHAT_LOG")
    if 'assistant.status = "failed"' not in chat_source:
        raise SystemExit("CHAT_STATUS")
    if "exc_info" in chat_source:
        raise SystemExit("CHAT_EXC_INFO")
    print("ERRORPATH_HOST_CHECK_OK")


if __name__ == "__main__":
    main()
