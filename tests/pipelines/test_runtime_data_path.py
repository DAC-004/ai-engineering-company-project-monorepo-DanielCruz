"""Host data paths are selected only when each store directory exists.

The helper is loaded from its file so this test does not import the package
initializer, which requires qdrant. A dotenv stub is inserted only for that
load and is removed afterward, including when the load fails.
"""

import importlib.util
import sys
import types
from pathlib import Path

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "shared" / "healthcore_rag" / "config.py"
_DOTENV_STUB_MARK = "_healthcore_runtime_path_test_stub"


def _load_runtime_data_path(config_path: Path):
    """Load runtime_data_path without leaving a stub in sys.modules."""
    inserted_stub = False
    try:
        if "dotenv" not in sys.modules:
            dotenv_stub = types.ModuleType("dotenv")
            dotenv_stub.load_dotenv = lambda *args, **kwargs: False  # type: ignore[attr-defined]
            setattr(dotenv_stub, _DOTENV_STUB_MARK, True)
            sys.modules["dotenv"] = dotenv_stub
            inserted_stub = True
        spec = importlib.util.spec_from_file_location(
            "healthcore_rag_config_under_test",
            config_path,
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("Could not load shared/healthcore_rag/config.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.runtime_data_path
    finally:
        if inserted_stub:
            current = sys.modules.get("dotenv")
            if current is not None and getattr(current, _DOTENV_STUB_MARK, False):
                del sys.modules["dotenv"]


runtime_data_path = _load_runtime_data_path(_CONFIG_PATH)


def test_sqlite_store_requires_its_own_directory(tmp_path: Path) -> None:
    host_file = tmp_path / "agent-checkpoints" / "support_agent.sqlite"
    repository_file = tmp_path / "repo" / "support_agent.sqlite"

    assert runtime_data_path(host_file, repository_file) == repository_file

    host_file.parent.mkdir()
    assert runtime_data_path(host_file, repository_file) == host_file


def test_directory_store_ignores_a_parent_that_is_only_the_data_root(tmp_path: Path) -> None:
    data_root = tmp_path / "healthcore"
    data_root.mkdir()
    host_directory = data_root / "agent-traces"
    repository_directory = tmp_path / "repo-traces"

    assert runtime_data_path(host_directory, repository_directory) == repository_directory

    host_directory.mkdir()
    assert runtime_data_path(host_directory, repository_directory) == host_directory


def test_dotenv_stub_does_not_escape() -> None:
    current = sys.modules.get("dotenv")
    assert current is None or not getattr(current, _DOTENV_STUB_MARK, False)


def test_failed_load_restores_the_preexisting_dotenv_module(tmp_path: Path) -> None:
    preexisting = sys.modules.get("dotenv")
    missing = tmp_path / "missing-config.py"
    try:
        _load_runtime_data_path(missing)
    except Exception:
        restored = sys.modules.get("dotenv")
        assert restored is preexisting
        assert restored is None or not getattr(restored, _DOTENV_STUB_MARK, False)
    else:
        raise AssertionError("A missing config file must not load.")
