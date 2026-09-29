"""Convert an uploaded PDF to Markdown before any agent reads it."""

from __future__ import annotations

import tempfile
from pathlib import Path

from data.pipelines.rfp_intake.generation import PipelineFailure


def pdf_bytes_to_markdown(pdf_bytes: bytes) -> str:
    """Convert PDF bytes with MarkItDown. The temp file is always removed.

    The original bytes are not written under data/raw here. Storage happens
    only after the PHI screen accepts the text.
    """
    if not pdf_bytes:
        raise PipelineFailure("conversion_failed")
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as handle:
            handle.write(pdf_bytes)
            temp_path = Path(handle.name)
        from markitdown import MarkItDown

        converted = MarkItDown().convert(str(temp_path))
        markdown = (converted.text_content or "").strip()
    except PipelineFailure:
        raise
    except Exception as exc:
        raise PipelineFailure("conversion_failed") from exc
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
    if not markdown:
        raise PipelineFailure("conversion_failed")
    return markdown
