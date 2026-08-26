# `uis` folder

This folder contains **all projects with a user interface** for the cross-functional AI Engineering company project — for example: a public website, admin dashboard frontend, ecommerce UI, customer portals, Streamlit/Gradio app or other frontend-only tools.

The two main projects stored here are:

- **`website`** — HealthCore public-facing Next.js site (port `3000` in Docker). Mapped from the Milestone 1 landing and care-request pages.
- **`backoffice`** — HealthCore internal Next.js workspace (port `3001` in Docker): authentication, profile, and medical-supply inventory. Mapped from `uis/talent-pipeline-tracker`.

`docker compose up` from the repository root starts both apps in a single UI container. See each subfolder README for local non-Docker commands.

Organize `uis/` by **different concerns** — each subfolder covers a distinct area of the company (for example, public web vs internal operations) and includes its own technical and functional documentation.

- **Main purpose**: to centralize in a single place all frontend applications that support the company's use cases.
- **Recommendation**: document in this file (or in sub-READMEs) the applications you add, their objective, the technology used, and how to run them.

> _Estas instrucciones también están disponibles en [español](./README.es.md)._
