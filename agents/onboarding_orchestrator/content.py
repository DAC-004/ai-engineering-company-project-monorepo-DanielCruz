"""Index official onboarding markdown. This is the only Q&A source."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from agents.onboarding_orchestrator.state import (
    FRAMEWORK_HIPAA,
    FRAMEWORK_UK_GDPR,
    ROLE_DIGITAL_ENGINEER,
    ROLE_REVENUE_ANALYST,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
MATERIAL_DIR = REPO_ROOT / "data" / "raw" / "healthcore-onboarding"

DOCUMENT_FILES: dict[str, str] = {
    "stage-02-the-company": "stage-02-the-company.md",
    "stage-03-how-we-operate": "stage-03-how-we-operate.md",
    "stage-04-compliance-hipaa": "stage-04-compliance-hipaa.md",
    "stage-04-compliance-uk-gdpr": "stage-04-compliance-uk-gdpr.md",
    "stage-05-role-digital-engineer": "stage-05-role-digital-engineer.md",
    "stage-05-role-revenue-cycle-analyst": "stage-05-role-revenue-cycle-analyst.md",
    "stage-06-how-we-work": "stage-06-how-we-work.md",
}

_STOPWORDS = frozenset(
    "a an the and or of to for in on with is are was be this that it not".split()
)


@dataclass(frozen=True)
class DocumentSection:
    document_id: str
    heading: str
    text: str


def _tokenize(text: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if token not in _STOPWORDS and len(token) > 1
    ]


@lru_cache(maxsize=1)
def load_documents(material_dir: str | None = None) -> dict[str, str]:
    directory = Path(material_dir) if material_dir else MATERIAL_DIR
    loaded: dict[str, str] = {}
    for document_id, filename in DOCUMENT_FILES.items():
        loaded[document_id] = (directory / filename).read_text(encoding="utf-8")
    return loaded


def sections_for(document_id: str, material_dir: str | None = None) -> list[DocumentSection]:
    body = load_documents(material_dir)[document_id]
    chunks: list[DocumentSection] = []
    heading = document_id
    buffer: list[str] = []
    for line in body.splitlines():
        if line.startswith("## "):
            if buffer:
                chunks.append(DocumentSection(document_id, heading, "\n".join(buffer).strip()))
            heading = line[3:].strip()
            buffer = []
        else:
            buffer.append(line)
    if buffer:
        chunks.append(DocumentSection(document_id, heading, "\n".join(buffer).strip()))
    return [chunk for chunk in chunks if chunk.text]


def document_for_stage(stage: int, *, framework: str, role_key: str) -> str:
    if stage == 2:
        return "stage-02-the-company"
    if stage == 3:
        return "stage-03-how-we-operate"
    if stage == 4:
        if framework == FRAMEWORK_UK_GDPR:
            return "stage-04-compliance-uk-gdpr"
        if framework == FRAMEWORK_HIPAA:
            return "stage-04-compliance-hipaa"
        raise ValueError("unknown_framework")
    if stage == 5:
        if role_key == ROLE_REVENUE_ANALYST:
            return "stage-05-role-revenue-cycle-analyst"
        if role_key == ROLE_DIGITAL_ENGINEER:
            return "stage-05-role-digital-engineer"
        raise ValueError("unknown_role_key")
    if stage == 6:
        return "stage-06-how-we-work"
    raise ValueError("not_a_content_stage")


def presented_content(stage: int, *, framework: str, role_key: str) -> dict[str, str]:
    document_id = document_for_stage(stage, framework=framework, role_key=role_key)
    return {
        "document_id": document_id,
        "title": document_id,
        "body": load_documents()[document_id],
    }


def check_catalog_id(stage: int, *, framework: str, role_key: str) -> str:
    if stage == 2:
        return "company"
    if stage == 3:
        return "operations"
    if stage == 4:
        return "compliance_uk_gdpr" if framework == FRAMEWORK_UK_GDPR else "compliance_hipaa"
    if stage == 5:
        return (
            "role_revenue_cycle_analyst"
            if role_key == ROLE_REVENUE_ANALYST
            else "role_digital_engineer"
        )
    if stage == 6:
        return "how_we_work"
    raise ValueError("not_a_content_stage")


@lru_cache(maxsize=1)
def load_checks(material_dir: str | None = None) -> dict:
    directory = Path(material_dir) if material_dir else MATERIAL_DIR
    return json.loads((directory / "checks.json").read_text(encoding="utf-8"))


def token_overlap(question: str, section: DocumentSection) -> int:
    question_tokens = set(_tokenize(question))
    section_tokens = set(_tokenize(f"{section.heading} {section.text}"))
    return len(question_tokens & section_tokens)
