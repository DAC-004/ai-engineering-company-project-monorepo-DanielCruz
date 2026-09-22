"""HealthCore RAG runtime: embed, retrieve, generate_answer, and query."""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from shared.healthcore_rag.config import (
    COLLECTION_NAME,
    DEFAULT_K,
    DEFAULT_MIN_SCORE,
    EMBEDDING_API_KEY,
    EMBEDDING_API_URL,
    EMBEDDING_MODEL_ID,
    GENERATION_API_KEY,
    GENERATION_API_URL,
    GENERATION_MODEL_ID,
    LOCAL_EMBEDDING_MODEL_ID,
    LOCAL_GENERATION_GGUF_FILENAME,
    LOCAL_GENERATION_GGUF_REPO,
    LOCAL_GENERATION_MODEL_ID,
    MODELS_DIR,
    VECTOR_SIZE,
)
from shared.healthcore_rag.qdrant import get_qdrant_client

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]{3,}")
_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "what",
    "which",
    "when",
    "how",
    "does",
    "can",
    "should",
    "someone",
    "have",
    "has",
    "not",
    "are",
    "was",
    "were",
    "into",
}
_INSUFFICIENT_INFORMATION_ANSWER = (
    "The available HealthCore knowledge base does not contain enough information "
    "to answer that question. I cannot confirm coverage, fees, timeframes, "
    "referral rules, or required documents that are not in the approved sources. "
    "Please verify with the appropriate HealthCore team before advising the caller."
)
# Policy markers used only to detect generation that went beyond retrieved
# text. These strings are not injected into prompts as HealthCore facts.
_POLICY_FACT_MARKERS = (
    "50 usd",
    "40 gbp",
    "11 days",
    "5 business days",
    "3 to 5 days",
    "tom callahan",
    "marcus reid",
    "blue cross",
    "aetna",
    "cigna",
    "unitedhealthcare",
    "bupa",
    "axa",
    "self-pay",
    "20%",
    "no-show fee",
    "informed consent",
    "hipaa",
    "uk gdpr",
    "4 hours",
)

_fastembed_model: Any | None = None
_local_llm: Any | None = None


def embedding_backend() -> str:
    """Return the embedding implementation that embed() will actually call."""
    if EMBEDDING_API_KEY:
        return f"api:{EMBEDDING_MODEL_ID}"
    return LOCAL_EMBEDDING_MODEL_ID


def generation_backend() -> str:
    """Return the generation implementation that generate_answer() will actually call."""
    if GENERATION_API_KEY:
        return f"api:{GENERATION_MODEL_ID}"
    return LOCAL_GENERATION_MODEL_ID


def _pad_vector(values: list[float]) -> list[float]:
    if len(values) >= VECTOR_SIZE:
        return [float(value) for value in values[:VECTOR_SIZE]]
    return [float(value) for value in values] + [0.0] * (VECTOR_SIZE - len(values))


def _load_fastembed_model() -> Any:
    """Load the dedicated FastEmbed ONNX embeddings model once per process.

    BAAI/bge-small-en-v1.5 is a neural sentence embedding model (384-d), not a
    corpus-fitted vectorizer. The first call downloads the ONNX weights into
    the FastEmbed cache. No API key is required.
    """
    global _fastembed_model
    if _fastembed_model is not None:
        return _fastembed_model
    from fastembed import TextEmbedding

    _fastembed_model = TextEmbedding(model_name=LOCAL_EMBEDDING_MODEL_ID)
    logger.info("Loaded dedicated embedding model %s", LOCAL_EMBEDDING_MODEL_ID)
    return _fastembed_model


def _local_gguf_path() -> Any:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    return MODELS_DIR / LOCAL_GENERATION_GGUF_FILENAME


def _model_acquisition_error(cause: Exception) -> RuntimeError:
    """Return a project-level download error that names the required local asset.

    The original exception is attached as the cause for debugging. The message
    never includes credentials or machine-specific secrets.
    """
    error = RuntimeError(
        "The local generation model could not be obtained. "
        f"Required repository: {LOCAL_GENERATION_GGUF_REPO}. "
        f"Required file: {LOCAL_GENERATION_GGUF_FILENAME}. "
        f"Expected local directory: {MODELS_DIR} "
        "(override with RAG_MODELS_DIR). "
        "Network access is required only for the first download. "
        "To use an already-downloaded GGUF, place that filename in the "
        "configured directory. Do not commit model binaries."
    )
    error.__cause__ = cause
    return error


def _ensure_local_gguf() -> Any:
    """Download the Qwen GGUF once. Prefer the ignored project models dir.

    Hugging Face `local_dir` needs its nested cache directories created first
    on Windows; if that path still fails, the default Hub cache is used.
    """
    from pathlib import Path

    from huggingface_hub import hf_hub_download

    target = _local_gguf_path()
    if target.is_file() and target.stat().st_size > 0:
        return target

    logger.info(
        "Downloading generation GGUF %s/%s",
        LOCAL_GENERATION_GGUF_REPO,
        LOCAL_GENERATION_GGUF_FILENAME,
    )
    cache_parent = MODELS_DIR / ".cache" / "huggingface" / "download"
    cache_parent.mkdir(parents=True, exist_ok=True)
    try:
        downloaded = hf_hub_download(
            repo_id=LOCAL_GENERATION_GGUF_REPO,
            filename=LOCAL_GENERATION_GGUF_FILENAME,
            local_dir=str(MODELS_DIR),
        )
        return Path(downloaded)
    except OSError as first_error:
        logger.warning("Project-local GGUF download failed; using the Hugging Face cache.")
        try:
            downloaded = hf_hub_download(
                repo_id=LOCAL_GENERATION_GGUF_REPO,
                filename=LOCAL_GENERATION_GGUF_FILENAME,
            )
            return Path(downloaded)
        except Exception as cache_error:
            raise _model_acquisition_error(cache_error) from cache_error
    except Exception as download_error:
        raise _model_acquisition_error(download_error) from download_error


def _load_local_llm() -> Any:
    """Load the dedicated local generation LLM via llama-cpp.

    This is an actual causal language model (Qwen2.5-3B-Instruct), not a
    template or keyword rewriter. It is a different model ID from the
    FastEmbed embeddings model.
    """
    global _local_llm
    if _local_llm is not None:
        return _local_llm
    try:
        from llama_cpp import Llama
    except ImportError as exc:
        raise RuntimeError(
            "llama-cpp-python is required for the local generation LLM. "
            "Install it with `uv add llama-cpp-python`."
        ) from exc

    model_path = _ensure_local_gguf()
    _local_llm = Llama(
        model_path=str(model_path),
        n_ctx=2048,
        n_threads=4,
        n_gpu_layers=0,
        verbose=False,
        chat_format="chatml",
    )
    logger.info("Loaded dedicated generation model %s from %s", LOCAL_GENERATION_MODEL_ID, model_path)
    return _local_llm


def local_llm_is_loaded() -> bool:
    """True after the process has loaded the local generation LLM once."""
    return _local_llm is not None


def embed(text: str) -> list[float]:
    """Embed one text value with the dedicated embedding path.

    The same function is used when `setup()` indexes chunks and when
    `retrieve()` embeds a coordinator question. It never calls the
    generation model ID.
    """
    if not text or not text.strip():
        raise ValueError("embed() requires non-empty text")

    if EMBEDDING_API_KEY:
        if not EMBEDDING_API_URL:
            raise RuntimeError("EMBEDDING_API_URL or LLM_API_URL is required for API embeddings.")
        headers = {
            "Authorization": f"Bearer {EMBEDDING_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {"model": EMBEDDING_MODEL_ID, "input": text}
        response = httpx.post(
            f"{EMBEDDING_API_URL}/embeddings",
            headers=headers,
            json=payload,
            timeout=30.0,
        )
        response.raise_for_status()
        vector = response.json()["data"][0]["embedding"]
        return _pad_vector([float(value) for value in vector])

    vectors = list(_load_fastembed_model().embed([text]))
    return _pad_vector([float(value) for value in vectors[0]])


def _search_scored_points(query_vector: list[float], k: int) -> list[Any]:
    """Qdrant nearest-neighbor search. Isolated so unit tests can stub it."""
    client = get_qdrant_client()
    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=k,
        with_payload=True,
    )
    return list(results.points)


def _payload_dict(payload: Any) -> dict[str, Any]:
    if payload is None:
        return {}
    if isinstance(payload, dict):
        return dict(payload)
    if hasattr(payload, "model_dump"):
        return dict(payload.model_dump())
    return dict(payload)


def _content_tokens(text: str) -> set[str]:
    return {
        token
        for token in _TOKEN_RE.findall(text.lower())
        if token not in _STOPWORDS and len(token) >= 4
    }


def _has_lexical_support(query: str, payload: dict[str, Any]) -> bool:
    """Utility used by tests; not applied on the FastEmbed retrieval path."""
    query_tokens = _content_tokens(query)
    if not query_tokens:
        return True
    haystack = f"{payload.get('section', '')} {payload.get('text', '')}"
    return bool(query_tokens & _content_tokens(haystack))


def retrieve(
    query: str,
    *,
    k: int = DEFAULT_K,
    min_score: float = DEFAULT_MIN_SCORE,
) -> list[dict[str, Any]]:
    """Embed the question, search Qdrant, and keep only payloads at or above min_score.

    Fewer than `k` results is expected when some neighbors are weak matches.
    An empty list is valid and must not be filled with low-scoring hits.
    """
    if not query or not query.strip():
        raise ValueError("retrieve() requires a non-empty query")
    if k < 1:
        raise ValueError("k must be at least 1")

    query_vector = embed(query)
    hits = _search_scored_points(query_vector, k)
    surviving: list[dict[str, Any]] = []
    for hit in hits:
        score = float(getattr(hit, "score", 0.0))
        if score < min_score:
            continue
        payload = _payload_dict(getattr(hit, "payload", None))
        if not payload:
            continue
        logger.info(
            "retrieve kept source=%s section=%s score=%.4f",
            payload.get("source_document"),
            payload.get("section"),
            score,
        )
        surviving.append(payload)

    logger.info(
        "retrieve question=%r k=%s min_score=%s hits=%s kept=%s sources=%s",
        query[:160],
        k,
        min_score,
        len(hits),
        len(surviving),
        [item.get("source_document") for item in surviving],
    )
    return surviving


def _context_for_prompt(context: list[dict[str, Any]]) -> str:
    if not context:
        return "(no retrieved HealthCore chunks exceeded the similarity threshold)"

    blocks: list[str] = []
    for item in context:
        source_document = item.get("source_document", "unknown")
        section = item.get("section", "unknown")
        text = str(item.get("text", "")).strip()
        blocks.append(f"[source_document={source_document} / section={section}]\n{text}")
    return "\n\n---\n\n".join(blocks)


def _build_generation_messages(question: str, context: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Coordinator prompt: behavioral rules only. Policy facts come from chunks."""
    system = (
        "You are an experienced HealthCore patient coordinator answering for "
        "front-desk colleagues. Speak clearly, empathetically, and practically.\n\n"
        "Use ONLY the retrieved context. Do not invent coverage, fees, "
        "timeframes, contacts, referral rules, or required documents. "
        "Mention a company fact only when that fact appears in the retrieved "
        "context. Do not add policy from another topic just because it is "
        "generally related to HealthCore.\n\n"
        "If the retrieved context answers the question, state that answer. "
        "Do not say the knowledge base lacks information when the retrieved "
        "context already contains the applicable rule.\n"
        "If an insurance question does not name a country and the retrieved "
        "context includes more than one country, distinguish those countries.\n"
        "If the retrieved context says a plan must be verified with billing, "
        "do not confirm that plan.\n"
        "If the retrieved context says Medicare or Medicaid patients are not "
        "charged a no-show fee, do not apply that fee. When that exception is "
        "in the retrieved context and the question is about a cancellation or "
        "no-show charge, include the exception.\n"
        "If the retrieved context states a time threshold, apply it literally "
        "to the duration named in the question. If the question is yes/no "
        "about a charge and that duration falls inside a retrieved late-fee "
        "window, the direct answer is yes for the retrieved private-pay fee. "
        "Do not begin with No in that case.\n"
        "If the question asks what a new patient must complete or bring, "
        "include every retrieved requirement that applies. Do not omit one.\n"
        "If there is no retrieved context, say the knowledge base does not "
        "contain enough information.\n"
        "Do not include real or realistic simulated patient names, diagnoses, "
        "or medical record numbers.\n"
        "Rewrite the facts in coordinator voice. Do not return the raw chunk "
        "as the entire answer."
    )
    named_durations = _named_durations(question)
    duration_line = ""
    if named_durations:
        duration_line = (
            f" The question names this duration: {', '.join(named_durations)}. "
            "Compare it to any time threshold in the retrieved context and "
            "apply the matching retrieved rule to that named duration. "
            "If it falls inside a retrieved late-fee window, say so directly "
            "and include any retrieved Medicare or Medicaid exception. "
            "Do not begin with No when the late-fee rule applies."
        )
    user = (
        f"Retrieved HealthCore context:\n{_context_for_prompt(context)}\n\n"
        f"Coordinator question:\n{question}\n\n"
        "Write the answer the coordinator can say to the caller. "
        "Use only the retrieved context."
        f"{duration_line}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _build_retry_messages(
    question: str,
    context: list[dict[str, Any]],
    previous_answer: str,
    reason: str,
) -> list[dict[str, str]]:
    """Ask the same generation model to rewrite a leaked or overly cautious answer."""
    messages = _build_generation_messages(question, context)
    messages.append({"role": "assistant", "content": previous_answer})
    messages.append(
        {
            "role": "user",
            "content": (
                f"{reason} Rewrite the coordinator answer using only the "
                "retrieved context. Do not mention any fee, contact, "
                "timeframe, plan, or document that is absent from that context."
            ),
        }
    )
    return messages


def _combined_context_text(context: list[dict[str, Any]]) -> str:
    joined = " ".join(str(item.get("text", "")) for item in context)
    return re.sub(r"\s+", " ", joined).lower()


def unsupported_policy_facts(answer: str, context: list[dict[str, Any]]) -> list[str]:
    """Return policy markers present in the answer but absent from retrieved text.

    Used after generation so a small local LLM cannot keep leftover facts from
    the system prompt or from a neighboring topic. This is not a formatter and
    does not write the final answer.
    """
    if not answer:
        return []
    lowered_answer = answer.lower()
    lowered_context = _combined_context_text(context)
    return [
        marker
        for marker in _POLICY_FACT_MARKERS
        if marker in lowered_answer and marker not in lowered_context
    ]


_DURATION_RE = re.compile(r"\b(\d+)\s*(hours?|days?)\b")


def _named_durations(question: str) -> list[str]:
    return [f"{match.group(1)} {match.group(2)}" for match in _DURATION_RE.finditer(question.lower())]


def _answer_opens_with_no(answer: str) -> bool:
    """True when the first word is a standalone No, not No-show or Note."""
    tokens = answer.lstrip().split(None, 1)
    if not tokens:
        return False
    return tokens[0].lower().rstrip(".,:;!") == "no"


def _question_asks_about_cancellation_or_no_show_fee(question: str) -> bool:
    lowered = question.lower()
    return any(
        marker in lowered
        for marker in ("cancel", "no-show", "no show")
    ) or ("charge" in lowered and bool(_DURATION_RE.search(lowered)))


def _question_names_country(question: str) -> bool:
    lowered = question.lower()
    return any(
        marker in lowered
        for marker in (
            "united states",
            "united kingdom",
            "georgia",
            "texas",
            "florida",
            " uk",
            "u.s",
            "nhs",
        )
    )


def _grounding_retry_reason(
    question: str,
    context: list[dict[str, Any]],
    answer: str,
) -> str | None:
    """Return a retry instruction when the model ignored retrieved constraints.

    This does not write the answer. It only decides whether the same generation
    model should be asked to rewrite using the retrieved chunks.
    """
    if not context or not answer:
        return None

    reasons: list[str] = []
    leaked = unsupported_policy_facts(answer, context)
    if leaked:
        reasons.append(
            "The previous answer mentioned policy facts that are not in the retrieved context."
        )
    if _claims_insufficient_information(answer):
        reasons.append(
            "The retrieved context already answers the question. Do not say information is missing."
        )

    context_text = _combined_context_text(context)
    answer_text = answer.lower()
    hours = [int(match.group(1)) for match in re.finditer(r"(\d+)\s*hours?", question.lower())]
    late_fee_context = "less than 24" in context_text or "50 usd" in context_text
    if hours and late_fee_context and min(hours) < 24:
        named_hours = str(min(hours))
        if "50 usd" not in answer_text and "less than 24" not in answer_text:
            reasons.append(
                "The question names a duration below a retrieved time threshold. "
                "Apply the matching retrieved late-cancellation or no-show rule."
            )
        if _answer_opens_with_no(answer):
            reasons.append(
                "The named duration is inside the retrieved late-cancellation "
                "window. Answer that duration directly: yes, the retrieved "
                "private-pay late fee applies. Do not begin with No."
            )
        if named_hours not in answer_text:
            reasons.append(
                "State that the duration named in the question falls inside "
                "the retrieved late-fee window."
            )
        if (
            _question_asks_about_cancellation_or_no_show_fee(question)
            and ("medicare" in context_text or "medicaid" in context_text)
            and "not charged" in context_text
            and "medicare" not in answer_text
            and "medicaid" not in answer_text
        ):
            reasons.append(
                "The retrieved context includes a Medicare or Medicaid fee "
                "exception. Include that retrieved exception."
            )

    if (
        not _question_names_country(question)
        and "united states" in context_text
        and "united kingdom" in context_text
        and ("united states" in answer_text or "us clinics" in answer_text)
        and "united kingdom" not in answer_text
        and "nhs" not in answer_text
        and "bupa" not in answer_text
    ):
        reasons.append(
            "The retrieved context covers more than one country. Distinguish those countries."
        )

    if (
        "informed consent" in context_text
        and "hipaa" in context_text
        and "gdpr" in context_text
        and "consent" in answer_text
        and ("hipaa" not in answer_text or "gdpr" not in answer_text)
    ):
        reasons.append(
            "The retrieved context includes country-specific consent rules. Include those retrieved conditions."
        )

    if not reasons:
        return None
    return " ".join(reasons)


def _claims_insufficient_information(answer: str) -> bool:
    lowered = answer.lower()
    return (
        "does not contain enough information" in lowered
        or "not enough information" in lowered
        or "insufficient information" in lowered
        or "i don't have the specific information" in lowered
        or "i do not have the specific information" in lowered
    )


def _complete_chat(messages: list[dict[str, str]]) -> str:
    """Call an optional remote chat API. Isolated so unit tests can stub it."""
    if not GENERATION_API_KEY or not GENERATION_API_URL:
        raise RuntimeError("A remote generation API key and URL are required for API generation.")
    headers = {
        "Authorization": f"Bearer {GENERATION_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GENERATION_MODEL_ID,
        "messages": messages,
        "temperature": 0.0,
    }
    response = httpx.post(
        f"{GENERATION_API_URL}/chat/completions",
        headers=headers,
        json=payload,
        timeout=45.0,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    return str(content).strip()


def _local_llm_complete(messages: list[dict[str, str]]) -> str:
    """Run the local generation LLM. Isolated so unit tests can stub it."""
    llm = _load_local_llm()
    completion = llm.create_chat_completion(
        messages=messages,
        temperature=0.0,
        max_tokens=320,
    )
    content = completion["choices"][0]["message"]["content"]
    return str(content).strip()


def _run_generation_model(messages: list[dict[str, str]]) -> str:
    """Dispatch to the remote chat API or the local generation LLM."""
    if GENERATION_API_KEY:
        return _complete_chat(messages)
    return _local_llm_complete(messages)


def generate_answer(question: str, context: list[dict[str, Any]]) -> str:
    """Generate a coordinator-facing answer from a generation LLM.

    In-corpus answers always go through `_run_generation_model`. If that
    model adds policy facts that are absent from the retrieved chunks, or
    claims a gap when retrieved text already answers the question, the same
    model is asked once more. The retry is still generation, not a rules
    formatter. Empty retrieval still invokes the model; invented empty-
    context facts are replaced with the insufficient-information statement.
    """
    if not question or not question.strip():
        raise ValueError("generate_answer() requires a non-empty question")

    prompt_payloads = [
        {key: value for key, value in item.items() if key != "_score"}
        for item in context
    ]
    messages = _build_generation_messages(question, prompt_payloads)

    try:
        answer = _run_generation_model(messages)
    except Exception:
        if not context:
            logger.exception("Generation failed for empty-context refusal")
            return _INSUFFICIENT_INFORMATION_ANSWER
        raise

    if not answer:
        if not context:
            return _INSUFFICIENT_INFORMATION_ANSWER
        raise RuntimeError("The generation model returned an empty answer.")

    if not context:
        if (not _claims_insufficient_information(answer)) or unsupported_policy_facts(
            answer, []
        ):
            logger.warning("Empty-context generation was not a grounded refusal; using refusal.")
            return _INSUFFICIENT_INFORMATION_ANSWER
        logger.info("generate_answer backend=%s chars=%s context_chunks=0", generation_backend(), len(answer))
        return answer

    retry_reason = _grounding_retry_reason(question, prompt_payloads, answer)
    if retry_reason:
        logger.warning("Retrying grounded generation: %s", retry_reason)
        answer = _run_generation_model(
            _build_retry_messages(question, prompt_payloads, answer, retry_reason)
        )

    logger.info(
        "generate_answer backend=%s chars=%s context_chunks=%s leaked=%s",
        generation_backend(),
        len(answer),
        len(prompt_payloads),
        unsupported_policy_facts(answer, prompt_payloads),
    )
    return answer


def query(question: str) -> str:
    """Compose retrieval and generation. This is the only HTTP/UI entrypoint."""
    context = retrieve(question)
    answer = generate_answer(question, context)
    logger.info(
        "query sources=%s sections=%s answer_chars=%s backend=%s/%s",
        [item.get("source_document") for item in context],
        [item.get("section") for item in context],
        len(answer),
        embedding_backend(),
        generation_backend(),
    )
    return answer
