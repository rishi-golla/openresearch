# Lab Paper Upload Design

## Goal

Let a user upload a PDF directly from `/lab` and run either the offline or SDK pipeline from that uploaded paper, without replacing the existing quick-start demo buttons.

## Constraints

- Reuse the repo's existing PDF ingestion path instead of adding a parallel paper parser just for the lab.
- Keep the current fixture-driven buttons working when no upload is provided.
- Support both `offline` and `sdk` runs from the uploaded paper.
- Preserve the current background-run model, stop behavior, and status polling.

## User Experience

The lab page gets a dedicated upload panel above the run buttons. A user can drag in or browse for a single PDF, see the selected filename, choose whether to launch the offline or SDK pipeline, and then start a run from that uploaded paper.

If no file is selected, the current `Run offline demo` and `Run SDK demo` behavior stays unchanged. If a file is selected, the upload action starts a new run and the dashboard source card changes from the fixture label to the uploaded filename.

## Backend Design

### API

`POST /api/demo` will support two request shapes:

- no body or JSON-free request: existing fixture demo run
- `multipart/form-data`: uploaded-paper run

Multipart requests will carry:

- `paper`: the PDF file
- `mode`: `offline` or `sdk`

The route validates that the upload exists, is a PDF, and is non-empty before starting a run.

### Runner

The demo runner will grow an optional uploaded-paper input:

- when absent, it uses the existing in-repo PPO workspace fixture
- when present, it copies the uploaded PDF into the run directory and launches the pipeline from that PDF path

The PDF-backed path should reuse the same ingestion + reproduce logic the CLI uses today:

1. register project from `PdfPath`
2. fetch paper into the project run directory
3. parse, discover, index, and build workspace
4. run the agent pipeline in offline or SDK mode

The lab runner still owns the `ui_demo_*` or `ui_sdk_demo_*` run id and demo status file, but it will also pass the uploaded source metadata through to the dashboard payload.

### Metadata

The demo payload metadata will distinguish:

- `workspace_fixture`
- `uploaded_pdf`

For uploads, the summary will show:

- original filename
- note that the run came from a lab upload

## Frontend Design

Add a compact upload section to the top lab hero:

- file input with drag/drop styling
- selected filename / clear state
- validation message when the file is missing or not a PDF
- `Run uploaded paper (offline)` and `Run uploaded paper (SDK)` actions, or a single action that uses the selected mode

The rest of the page stays the same:

- runner log
- dashboard replay
- stop button
- source/status cards

## Error Handling

- Reject non-PDF uploads in the API with a clear message.
- Reject empty uploads.
- If upload staging fails, return a `500` and keep the current page state unchanged.
- If ingestion or parsing fails later, the normal run failure path writes the error into `demo_status.json` and the UI surfaces it through the existing error banner and log panel.

## Testing

### Backend / API

- `POST /api/demo` with multipart PDF starts an uploaded-paper run.
- multipart request without a file returns `400`.
- multipart request with a non-PDF MIME/extension returns `400`.

### Runner

- uploaded-paper mode records uploaded source metadata instead of the fixture metadata.
- uploaded-paper mode writes the staged file path into the Python launch script path.

### UI

- selecting a file stores the filename in state
- uploaded-paper submit uses `FormData`
- mode-specific upload actions disable while a run is starting

## Out of Scope

- DOI / arXiv entry inside the lab page
- multiple file uploads
- client-side PDF preview
- replacing the current fixture demo buttons
