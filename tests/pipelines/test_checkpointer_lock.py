"""Part 3 checkpoint access must serialize across threads."""

from __future__ import annotations

import threading
from pathlib import Path

from data.pipelines.rfp_intake.checkpointer import with_checkpointer


def test_with_checkpointer_releases_lock_after_use_raises(tmp_path: Path) -> None:
    db = tmp_path / "approvals.sqlite"

    def boom(_saver: object) -> None:
        raise RuntimeError("checkpoint use failed")

    try:
        with_checkpointer(db, boom)
    except RuntimeError:
        pass

    seen = {"ok": False}

    def use(_saver: object) -> None:
        seen["ok"] = True

    with_checkpointer(db, use)
    assert seen["ok"]


def test_with_checkpointer_serializes_concurrent_threads(tmp_path: Path) -> None:
    db = tmp_path / "approvals.sqlite"
    errors: list[BaseException] = []
    counter = {"value": 0}

    def worker() -> None:
        try:

            def use(saver: object) -> None:
                counter["value"] += 1

            with_checkpointer(db, use)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert not errors
    assert counter["value"] == 8
