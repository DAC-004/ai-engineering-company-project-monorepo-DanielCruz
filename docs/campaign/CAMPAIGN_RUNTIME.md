# HealthCore integration campaign — operational runtime

**Campaign branch:** `integration/campaign`
**Documented HEAD at authoring:** `6a4e821` (I07-SSE merge) plus subsequent I09/I10 commits when present.
**Scope:** operational guidance for the integrated tree. Historical course assignment text and Milestone 1 deploy notes remain elsewhere in the root README; this file describes the **current** staff + API topology.

## Primary applications (do not swap)

| Role | Location | Typical host URL |
| --- | --- | --- |
| Internal Workspace (auth, inventory, incidents, analyzer, suppliers, RFP, knowledge, reporting, talent) | `uis/talent-pipeline-tracker` | http://127.0.0.1:3000 |
| HealthCore API | `services/api` | http://127.0.0.1:8000 |
| Public website (Compose) | `uis/website` | http://127.0.0.1:3010 |
| Legacy backoffice relocation (Compose) | `uis/backoffice` | http://127.0.0.1:3001 |
| Qdrant | Compose `qdrant` or local `data/process/qdrant_storage` | http://127.0.0.1:6333 |
| Redis / Celery worker / Flower | Compose `redis` `worker` `flower` | 6379 / worker process / http://127.0.0.1:5555 |

Staff development uses the **host** tracker on port **3000**. Compose maps the public site to **3010** so it does not collide with the tracker.

## Authenticated navigation

After login, `AppShell` links cover Home, talent pipeline, incidents (register/list/summary/analysis), inventory (products/inbound/outbound/movements), suppliers, RFP intake, knowledge, clinic supply report, profile, and change password. The talent pipeline keeps Milestone 3 candidate chrome inside the same authenticated shell and provides **Back to workspace home**.

## Local model and NLTK

- GGUF: `data/process/models/qwen2.5-3b-instruct-q4_k_m.gguf` (or `RAG_MODELS_DIR`). Gitignored.
- NLTK data: `data/process/nltk_data` (gitignored). Required for readability metrics in RFP evaluation.

## Evidence locations (gitignored)

Campaign acceptance artifacts live under `services/api/data/*-campaign/` and `services/api/data/campaign-validation/`. Do not stage those directories.

## Publication boundary

Main promotion, push, remote publication, external email, and instructor certification are **outside** campaign worktree authorization. This document does not claim those actions occurred.
