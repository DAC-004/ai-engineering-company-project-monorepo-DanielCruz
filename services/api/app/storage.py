"""Atomic file helpers and incident upload/result paths under INCIDENT_DATA_DIR."""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any

from app.core.config import get_settings

# Queue messages carry only this identifier. Reject path separators and dots.
_SAFE_UPLOAD_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_JSON_READ_ATTEMPTS = 8
_JSON_READ_DELAY_SECONDS = 0.02


def incident_data_dir() -> Path:
    return Path(get_settings().incident_data_dir)


def uploads_dir() -> Path:
    return incident_data_dir() / "incident_uploads"


def results_dir() -> Path:
    return incident_data_dir() / "incident_results"


def ensure_runtime_dirs() -> None:
    """Create upload and result directories during API startup so the first enqueue is not a cold mkdir."""
    uploads_dir().mkdir(parents=True, exist_ok=True)
    results_dir().mkdir(parents=True, exist_ok=True)


def last_analysis_path() -> Path:
    return results_dir() / "last.json"


def task_result_path(task_id: str) -> Path:
    return results_dir() / f"{task_id}.json"


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Write bytes via a sibling temp file and os.replace so readers never see a partial file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    with open(tmp_path, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_path, path)


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    encoded = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    atomic_write_bytes(path, encoded)


def read_json_with_retry(path: Path) -> dict[str, Any] | None:
    """
    Read JSON that another process may be replacing.

    os.replace is atomic on the same volume; a reader can still hit an empty
    or truncated file if it raced a crash mid-write. Retry, then treat as missing.
    """
    if not path.exists():
        return None
    for _ in range(_JSON_READ_ATTEMPTS):
        try:
            text = path.read_text(encoding="utf-8")
            if not text.strip():
                time.sleep(_JSON_READ_DELAY_SECONDS)
                continue
            loaded = json.loads(text)
            if isinstance(loaded, dict):
                return loaded
        except (OSError, json.JSONDecodeError):
            time.sleep(_JSON_READ_DELAY_SECONDS)
    return None


def save_upload(*, data: bytes, owner_user_id: str, source_name: str) -> str:
    """Persist CSV + lightweight metadata. Returns the identifier placed on the queue."""
    upload_id = uuid.uuid4().hex
    target_dir = uploads_dir()
    atomic_write_bytes(target_dir / f"{upload_id}.csv", data)
    atomic_write_json(
        target_dir / f"{upload_id}.meta.json",
        {"owner_user_id": owner_user_id, "source_name": source_name},
    )
    return upload_id


def load_upload(upload_id: str) -> tuple[Path, dict[str, Any]]:
    """Resolve an upload by id. Missing or unsafe ids raise FileNotFoundError."""
    if not _SAFE_UPLOAD_ID.fullmatch(upload_id):
        raise FileNotFoundError(f"Upload not found: {upload_id}")
    csv_path = uploads_dir() / f"{upload_id}.csv"
    meta_path = uploads_dir() / f"{upload_id}.meta.json"
    if not csv_path.is_file():
        raise FileNotFoundError(f"Upload not found: {upload_id}")
    meta = read_json_with_retry(meta_path)
    if meta is None:
        raise FileNotFoundError(f"Upload metadata not found: {upload_id}")
    return csv_path, meta


def load_task_result(task_id: str) -> dict[str, Any] | None:
    return read_json_with_retry(task_result_path(task_id))


def save_task_result(task_id: str, payload: dict[str, Any]) -> None:
    atomic_write_json(task_result_path(task_id), payload)
