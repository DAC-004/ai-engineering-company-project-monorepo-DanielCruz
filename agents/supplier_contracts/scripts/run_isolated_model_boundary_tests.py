"""Isolated fake-model boundary runner. Does not collect live generation tests."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree

REPO = Path(__file__).resolve().parents[3]
RUNNER_PATH = Path(__file__).resolve()
PACKAGE_DIR = REPO / "agents" / "supplier_contracts"
TEST_FILES = (
    REPO / "tests" / "pipelines" / "test_supplier_contracts_model_boundary.py",
)
REVIEW_DEPS = Path(r"C:\Users\cruzd\AppData\Local\Temp\healthcore-task4-review-deps-20261106")
LIVE_VARS = (
    "DATABASE_URL",
    "REDIS_URL",
    "QDRANT_URL",
    "TINYDB_PATH",
    "SUPPLIERS_DB_PATH",
    "INCIDENT_DATA_DIR",
    "RESEND_API_KEY",
    "GENERATION_API_KEY",
    "GENERATION_API_URL",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "PLATFORM_SEED_PASSWORD",
    "RFP_DEMONSTRATION_PASSWORD",
    "SECRET_KEY",
    "SUPPLIER_CONTRACTS_LIVE_GENERATION",
)
SECRET_SUFFIXES = ("_API_KEY", "_TOKEN", "_PASSWORD", "_SECRET", "_CREDENTIAL")


def _is_secret_name(name: str) -> bool:
    upper = name.upper()
    return name in LIVE_VARS or upper.endswith(SECRET_SUFFIXES)


def _clear_live_credentials(env: dict[str, str]) -> list[str]:
    cleared: list[str] = []
    for name in list(env):
        if _is_secret_name(name):
            env.pop(name, None)
            cleared.append(name)
    return sorted(cleared)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_paths() -> list[Path]:
    package = sorted(path for path in PACKAGE_DIR.rglob("*") if path.is_file() and path.suffix in {".py", ".md"})
    return [*package, *TEST_FILES, RUNNER_PATH]


def _manifest() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for path in _source_paths():
        mapping[str(path.relative_to(REPO)).replace("\\", "/")] = _sha(path)
    return mapping


def _owned_evidence_dir(raw: str) -> Path:
    if not raw or not raw.strip():
        raise SystemExit("evidence directory is required and must be an absolute owned path")
    given = Path(raw.strip())
    if not given.is_absolute():
        raise SystemExit("evidence directory must be an absolute path")
    resolved = given.resolve()
    if not resolved.is_absolute():
        raise SystemExit("evidence directory did not resolve to an absolute path")
    cwd = Path.cwd().resolve()
    if resolved == cwd or resolved == REPO:
        raise SystemExit("evidence directory must not be the current working directory or repository root")
    if resolved == REPO or REPO in resolved.parents:
        raise SystemExit("evidence directory must be an owned path outside the repository")
    return resolved


def _parse_junit(path: Path) -> dict[str, int]:
    if not path.is_file():
        raise SystemExit("JUnit file was not written")
    root = ElementTree.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    if root.tag == "testsuites" and not suites:
        suites = list(root)
    tests = failures = errors = skipped = 0
    for suite in suites:
        tests += int(suite.attrib.get("tests", "0"))
        failures += int(suite.attrib.get("failures", "0"))
        errors += int(suite.attrib.get("errors", "0"))
        skipped += int(suite.attrib.get("skipped", "0"))
    if tests == 0 and root.attrib.get("tests"):
        tests = int(root.attrib.get("tests", "0"))
        failures = int(root.attrib.get("failures", "0"))
        errors = int(root.attrib.get("errors", "0"))
        skipped = int(root.attrib.get("skipped", "0"))
    return {"tests": tests, "failures": failures, "errors": errors, "skipped": skipped}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", required=True, help="Absolute owned directory outside the repository")
    args = parser.parse_args()
    parent = _owned_evidence_dir(args.evidence_dir)
    parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = parent / f"run-{stamp}-{uuid.uuid4().hex[:8]}"
    if run_dir.exists():
        raise SystemExit("run directory already exists")
    run_dir.mkdir(parents=False, exist_ok=False)
    basetemp = run_dir / "basetemp"
    isolated = run_dir / "stores"
    basetemp.mkdir()
    isolated.mkdir()
    before = _manifest()
    (run_dir / "source-manifest-before.json").write_text(json.dumps(before, indent=2, sort_keys=True), encoding="utf-8")
    env = os.environ.copy()
    cleared = _clear_live_credentials(env)
    pythonpath = [str(REPO)]
    if REVIEW_DEPS.is_dir():
        pythonpath.append(str(REVIEW_DEPS))
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join([*pythonpath, existing] if existing else pythonpath)
    env["SECRET_KEY"] = "task4-isolated-secret-key-32chars"
    env["DATABASE_URL"] = f"sqlite:///{(isolated / 'inventory.db').as_posix()}"
    env["TINYDB_PATH"] = str(isolated / "auth.json")
    env["SUPPLIERS_DB_PATH"] = str(isolated / "suppliers.json")
    env["INCIDENT_DATA_DIR"] = str(isolated / "incident-data")
    env["QDRANT_PATH"] = str(isolated / "qdrant")
    env["CELERY_TASK_ALWAYS_EAGER"] = "1"
    env["SUPPLIER_CONTRACTS_RAW_DIR"] = str(isolated / "raw")
    env["SUPPLIER_CONTRACTS_PROCESS_DIR"] = str(isolated / "process")
    env.pop("QDRANT_URL", None)
    env.pop("REDIS_URL", None)
    env.pop("SUPPLIER_CONTRACTS_LIVE_GENERATION", None)
    junit = run_dir / "junit.xml"
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-p",
        "no:cacheprovider",
        "--noconftest",
        "--tb=short",
        f"--basetemp={basetemp}",
        f"--junitxml={junit}",
        *[str(path) for path in TEST_FILES],
    ]
    completed = subprocess.run(command, cwd=str(REPO), env=env, check=False)
    after = _manifest()
    (run_dir / "source-manifest-after.json").write_text(json.dumps(after, indent=2, sort_keys=True), encoding="utf-8")
    changed = sorted(key for key in sorted(set(before) | set(after)) if before.get(key) != after.get(key))
    junit_totals = _parse_junit(junit)
    passed = (
        completed.returncode == 0
        and not changed
        and junit_totals["failures"] == 0
        and junit_totals["errors"] == 0
        and junit_totals["tests"] > 0
    )
    summary = {
        "exit_code": completed.returncode,
        "junit": junit_totals,
        "cleared_variable_names": cleared,
        "source_changed": changed,
        "passed": passed,
        "live_generation": False,
        "run_dir": str(run_dir),
    }
    (run_dir / "result.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (run_dir / "exit-code.txt").write_text(str(completed.returncode), encoding="utf-8")
    if changed:
        return 1
    if not passed:
        return completed.returncode or 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
