# Trackback — Project Ideation & Engineering Notebook

[Open the finished five-page PDF](project-ideation-notebook.pdf).

Prepared retrospectively from repository revision `e452169`, for an authentic review in Notability. The notebook covers the problem and users, an exploration mind map, the complete correction journey, implemented architecture, and a Git-backed development timeline. It does not claim that the team used Notability earlier.

## Before submission

1. Import `project-ideation-notebook.pdf` into Notability as a new note.
2. Add genuine team review: highlight a design tradeoff on page 2, trace or question a branch on page 3, and write an owner and next experiment on page 5. Use the blank dotted areas on every page.
3. Keep the editable Notability note. Export an annotated PDF and capture your actual review in the app for submission evidence. Describe only the Notability features you actually used.

The original PDF has selectable text, embedded fonts, vector diagrams, five outline bookmarks, clickable page-number navigation, and links to repository evidence. It is portrait 3:4 for comfortable tablet reading. No annotations, research sessions or app screenshots have been fabricated.

## Evidence and limits

- **Pages 1–2:** `README.md`, `DECISIONS.md`, `backend/trackback/core/propagate.py`, and the evaluation baselines. Exploration is explicitly retrospective; the six-gym company is fictional.
- **Page 3:** `frontend/src/stage/Stage.tsx`, `backend/trackback/api.py`, `live.py`, `corrections.py`, `core/waves.py`, `core/pings.py`, `review.py`, and `lessons.py`. The guided demo scripts a rejection/re-draft and submits lesson approval as the Controller; this is disclosed separately from manual Deep review. Effects are simulated locally.
- **Page 4:** `frontend/package.json`, `backend/trackback/main.py`, `core/domain.py`, `core/tools.py`, `core/memento.py`, `core/llm/gateway.py`, `schema.sql`, `mcp_server.py`, `Dockerfile`, and `api/index.py`. MCP read tools exist; MCP/A2A notification adapters are still future work. Hosting configuration is not proof of a live deployment.
- **Page 5:** actual commit timestamps and messages for `06bbbc9`, `4b6031c`, `fcc8cb3`, `48964da`, and `e452169`; `DECISIONS.md`; `STATUS.md`; `backend/tests/`; and `data/eval/latest.json`. Evaluation figures are committed replay results, not a fresh test run or production benchmarks. Snapshot responses mix recorded and scripted origins; Jade's current checks are code-based.

Current code takes precedence over older prose: the UI says **Scorecard** and **Time travel**; the removed Research tab is not presented as functionality. Memento remains the internal document-service name. The 48-gym proposal in `NEW_SPEC.md` is not the implemented world.

## Editable sources

`diagrams/01-vision.svg` through `05-development.svg` are editable vector pages. `diagrams/build_notebook.py` is the single source for their text, shapes, connections and PDF layout. No application files are imported or modified by the generator.

To regenerate, install `reportlab` in a separate environment and run:

```sh
python notability/diagrams/build_notebook.py
```

The generator embeds macOS Arial/Georgia or Linux DejaVu fonts. PyMuPDF was used to open and render all five pages for visual inspection; layout bounds and links were checked. [devpost-section.md](devpost-section.md) contains truthful, ready-to-paste process copy; add a factual sentence about your completed Notability review after you perform it.
