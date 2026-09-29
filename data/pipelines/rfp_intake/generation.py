"""Local llama.cpp generation for the RFP agents.

This follows the empty-key branch of the existing HealthCore generator:
load qwen2.5-3b-instruct-q4_k_m.gguf with llama-cpp, chatml, temperature 0.
Part 1 does not call a remote chat API and does not download the file.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parents[3]
GGUF_FILENAME = "qwen2.5-3b-instruct-q4_k_m.gguf"
DEFAULT_MODELS_DIR = REPO_ROOT / "data" / "process" / "models"

ChatComplete = Callable[[list[dict[str, str]]], str]

_local_llm = None
# The intake graph runs the three department workers together. llama.cpp is not
# safe for overlapping completions on one loaded model, and a second call aborts
# the process. This lock keeps those workers serialized without merging them.
_local_llm_lock = threading.Lock()


class ModelAssetMissing(RuntimeError):
    """The local GGUF file is not available. The message is a code, not document text."""

    code = "model_asset_missing"

    def __init__(self) -> None:
        super().__init__(self.code)


class PipelineFailure(RuntimeError):
    """A safe failure code. The message must not contain document or model text."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def local_gguf_path() -> Path:
    """Resolve the GGUF path. RAG_MODELS_DIR overrides the directory only."""
    override = os.environ.get("RAG_MODELS_DIR", "").strip()
    directory = Path(override) if override else DEFAULT_MODELS_DIR
    return directory / GGUF_FILENAME


def complete_local(messages: list[dict[str, str]]) -> str:
    """Run one local chat completion. Tests pass their own callable instead."""
    global _local_llm
    model_path = local_gguf_path()
    if not model_path.is_file() or model_path.stat().st_size <= 0:
        raise ModelAssetMissing()
    with _local_llm_lock:
        if _local_llm is None:
            try:
                from llama_cpp import Llama
            except ImportError as exc:
                raise PipelineFailure("llama_cpp_missing") from exc
            _local_llm = Llama(
                model_path=str(model_path),
                n_ctx=2048,
                n_threads=4,
                n_gpu_layers=0,
                verbose=False,
                chat_format="chatml",
            )
        completion = _local_llm.create_chat_completion(
            messages=messages,
            temperature=0.0,
            max_tokens=320,
        )
    content = completion["choices"][0]["message"]["content"]
    return str(content).strip()
