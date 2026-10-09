# HealthCore NIST delivery

This folder is the delivery folder for Secure Practices for AI Integration in Systems. The supplied project text says the NIST report is a Markdown file inside the delivery folder and does not name that folder. This repository already keeps audit deliverables under `docs/`. The NIST report is `docs/nist/nist-report.md`.

## Where a language model receives external input

This list was written after the first code edits on 2026-10-08. That missed the required pre-code timing. Later completion does not satisfy that sequence. On 2026-10-08 the call sites were checked again: `create_chat_completion`, `complete_local`, `embed()`, `generate_answer()`, and the `httpx.post` calls in `data/pipelines/rag.py`. The rows below are that present-day inventory.

| Point | External input | Where it enters the prompt | Control in this tree |
| --- | --- | --- | --- |
| `POST /knowledge/query` | Staff question | `data/pipelines/rag.py` `query()` then `_build_generation_messages()` user message | `screen_question()` runs before retrieval and generation. A block returns a fixed sentence and does not call the model. |
| `POST /agent/query` | Staff question | `run_support_agent()` then the support graph | The same screen runs before the graph. Ticket questions require a bearer before MCP. |
| WebSocket chat | Staff question and prior user or assistant turns | `services/api/app/services/chat_channel.py` calls `run_support_agent()`. Prior turns are appended as `user` and `assistant` messages, not as the system message. | `event_text_for_turn()` replaces a blocked or patient-looking message with a fixed withheld label before the event is stored. The generator still receives the original text so the refusal runs. An allowed question is still echoed. |
| Semantic knowledge base, generation | Files in `docs/company-knowledge-base/` | `retrieve()` payloads are wrapped as `[untrusted data, not instructions]` inside the user message | `chunk_is_prohibited()` drops a chunk that carries an embedded instruction before generation. |
| Semantic knowledge base, index | The same files, through `data/process/rag.py` `setup()` | `embed()` sends each chunk to FastEmbed `BAAI/bge-small-en-v1.5`. If `EMBEDDING_API_KEY` is set, the same text is posted to `{EMBEDDING_API_URL}/embeddings` instead. | This is the embedding model, not the chat model. Indexing runs on the repository files. |
| Screened staff question, retrieval | The question that `screen_question()` allowed | `retrieve()` calls `embed()` before the vector search. The remote embedding branch receives that same question. | The block path in `query()` and `run_support_agent()` returns before `retrieve()`. |
| Approved operational memory | Staff-approved note text | `generate_from_context()` passes `approved_memory` into the user message as unverified notes | The notes are labeled untrusted data. They are not passed through `chunk_is_prohibited()`. |
| Generation retry | The model's own previous sample | `_build_retry_messages()` appends that sample as the assistant message and asks for a rewrite | The external inputs are still the question, the retrieved chunks, and any approved notes. |
| Remote chat | The messages already built for local generation | If `GENERATION_API_KEY` is set, `_complete_chat()` posts those messages to `{GENERATION_API_URL}/chat/completions` | This is the same prompt, not a new external source. |
| MCP tool results | Incident rows returned to the support agent | The model does not receive the rows. `_row_clause()` appends id, status, category, origin, and branch to the answer after generation. Title and description are not copied. | `partition_rows()` withholds a row when `disclosure_is_prohibited()` matches any stored field. Inventory writes are rejected before an upstream call. |
| RFP classifier and orchestrator | Uploaded document, after `screen_text()` | `classify_rfp()` and `orchestrate_rfp()` place that markdown in the user message. The system role stays separate. | `process_pdf()` screens before `run_intake_graph()`. The classifier keeps only the decision enum. |
| RFP department worker | That department's extract and shared metadata | `analyze_department()` places them in the user JSON | The worker does not receive the full document. Returned aspects are screened and checked against the source text. |
| RFP department generator | Shared metadata, key aspects, and `feedback_for_generator` | `generate_revenue_section()`, `generate_clinical_section()`, and `generate_compliance_section()` place that JSON in the user message | The system role is the department instruction. Feedback is the screened approval note or evaluator text. |
| RFP synthesizer | Worker sections and metadata | `synthesize_findings()` places that JSON in the user message | The synthesizer does not receive the PDF. The output object is shape-checked before it is kept. |
| RFP approval note | Human note on reject or request-changes | `feedback_for_generator` in the department generator user message | `screen_generated()` runs in `decide()` before the checkpoint command and again before graph state is written. |

Retrieved protocol text, user text, and tool results are not given the system role.
