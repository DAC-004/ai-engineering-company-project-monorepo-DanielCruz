# `uis` folder

This folder contains **all projects with a user interface** for the cross-functional AI Engineering company project — for example: a public website, admin dashboard frontend, ecommerce UI, customer portals, Streamlit/Gradio app or other frontend-only tools.

Current HealthCore UIs:

- **`website`** — public Next.js site (port **3000** in Docker Compose `ui` service).
- **`backoffice`** — lightweight supplier directory and legacy static artifacts (port **3001** in Docker). Not the authenticated staff workspace.
- **`talent-pipeline-tracker`** — authenticated Internal Workspace (login, inventory, incidents, RFP, knowledge, analyzer). Run on host port **3000** for normal development; do not map it to the same host port as Docker `ui` without changing one service's port.
- **`incidents`** — shared incident UI modules consumed by the tracker (`npm ci` in `uis/incidents` before tracker lint/build).
- **`web`** — relocated static incident analyzer assets (see narrow I09).

`docker compose up` from the repository root starts **qdrant**, the **backend** API, and the **ui** container (website + backoffice).

### Supported dev topology (I04)

| Role | How to run | Host URL |
| --- | --- | --- |
| Public website | Compose `ui` (container port 3000) | http://localhost:**3010** |
| Legacy backoffice (supplier relocation) | Compose `ui` (container port 3001) | http://localhost:**3001** |
| **Internal Workspace** (auth, inventory, incidents, RFP, knowledge) | **Host** `npm run dev` in `uis/talent-pipeline-tracker` (after `uis/incidents` `npm ci`) | http://localhost:**3000** |
| HealthCore API | Compose `backend` | http://localhost:**8000** |
| Qdrant | Compose `qdrant` | http://localhost:**6333** |

Compose maps **3010→3000** so the staff workspace can keep the default **3000** origin (`FRONTEND_BASE_URL`, password-reset links, `NEXT_PUBLIC_STAFF_WORKSPACE_URL`). Browser calls from the public site use `/backend/*` rewrites to the API service.

See subfolder READMEs for local non-Docker commands.

Organize `uis/` by **different concerns** — each subfolder covers a distinct area of the company (for example, public web vs internal operations) and includes its own technical and functional documentation.

- **Main purpose**: to centralize in a single place all frontend applications that support the company's use cases.
- **Recommendation**: document in this file (or in sub-READMEs) the applications you add, their objective, the technology used, and how to run them.

> _Estas instrucciones también están disponibles en [español](./README.es.md)._
