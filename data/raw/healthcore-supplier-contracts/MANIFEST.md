# Supplier-contract raw fixtures — provenance

These files were copied byte-identically from the passing fixture review
`task4-fixture-review-ta8kz_a5/raw` into this worktree. They were not
regenerated here. Do not overwrite them.

Load date used by the verified extraction: **2026-11-06**.

| File | SHA-256 |
| --- | --- |
| `prices.csv` | `ECFCD15CF901E93536323FA75E20230892715DC14DAF413D870170ED67CE41AE` |
| `pdfs/CT-HC-01.pdf` | `8AF5D6AAB4B4BE227C3E632D10772EA23AD96A9848A281FD42B5D0B1B23E1228` |
| `pdfs/CT-HC-02.pdf` | `AD0F6F60E9D499532C8D96A76E0D9C982894B39C65B41C352462496D1D2B5174` |
| `pdfs/CT-HC-03.pdf` | `151932C9094DF84843695679A464B319601650C6D06C25FD313A8605D18D879C` |
| `pdfs/CT-HC-04.pdf` | `3318C83AC73ED39F3E81DCF158EEE7BA11A1AF254717A8F03F49E36CA30D94DA` |

`prices.csv` has 85 lines (header plus 84 month rows: seven suppliers × twelve months).

Executed evidence (not rerun by this note):

- Fixture/PDF extraction: `task4-fixture-review-ta8kz_a5`, 25/25 assertions.
- Visual inspection of the four English PDFs: 10 pages.

Runtime may still generate isolated copies under a test `SUPPLIER_CONTRACTS_RAW_DIR`. The files in this directory are the delivery originals for the worktree. Seed code was not changed.
