"""Auth storage stays readable while another request writes it.

The first live ticket load returned 500 because get_current_user decoded
TinyDB while another thread was writing the same file handle.
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path

from tinydb import Query, TinyDB

API_DIR = Path(__file__).resolve().parents[1]
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from app.db.tinydb import LockedJSONStorage  # noqa: E402


def test_concurrent_reads_during_writes_do_not_decode_an_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "auth.json"
    database = TinyDB(path, storage=LockedJSONStorage)
    users = database.table("users")
    users.insert({"id": "user-1", "email": "reader@example.com", "blob": "x" * 400})
    failures: list[BaseException] = []
    stop = threading.Event()

    def write_user() -> None:
        index = 0
        while not stop.is_set():
            index += 1
            users.update(
                {"n": index, "blob": "y" * (200 + (index % 300))},
                Query().id == "user-1",
            )

    def read_user() -> None:
        try:
            for _ in range(400):
                row = users.get(Query().id == "user-1")
                if row is None or row.get("id") != "user-1":
                    raise AssertionError("The user row was missing during a concurrent write.")
        except BaseException as exc:
            failures.append(exc)

    writer = threading.Thread(target=write_user)
    readers = [threading.Thread(target=read_user) for _ in range(6)]
    writer.start()
    for reader in readers:
        reader.start()
    for reader in readers:
        reader.join()
    stop.set()
    writer.join()
    stored = users.get(Query().id == "user-1")
    database.close()

    assert failures == []
    assert stored is not None
    assert stored["email"] == "reader@example.com"
