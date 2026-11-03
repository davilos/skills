---
name: doc-review
description: 'Builds an interactive HTML review page that mirrors any local Markdown document (TDD, ADR, RFC, PRD, design doc, runbook) section by section: the literal text, mermaid diagrams drawn with zoom and a step-by-step walk of their numbered steps, a Validate per section, numbered table rows the reviewer can confirm, reject and cite, and scripts that prove nothing from the document is missing. Publishes it as an Artifact when available, otherwise writes a local HTML file; the interface follows the document language (English or Portuguese). Use when the user says "review page for this doc", "make a page to review the TDD", "turn this md into a review page", "doc-review", "página de revisão do documento", "quero revisar esse TDD numa página", "update the review page", or "sync what I validated on the page". Do NOT use for a tlc-spec-lean plan.md (use plan-review), for writing or editing the document itself, for documents with no local .md file, or for generic diagrams (use mermaid-studio).'
license: CC-BY-4.0
metadata:
  author: Dávilos Tavares - github.com/davilos
  version: '1.0.1'
---

# Doc Review

The page is a **mirror** of a local Markdown document that makes it easier for people to review it. It is never the source: the `.md` is what counts, and the page is rebuilt whenever it changes. The page adds no content of its own (no summaries, no notes): everything on it is the document's text, drawn or numbered. Never edit the generated HTML by hand.

## Pieces

| Piece                           | What it is                                                                                     | Who writes it                              |
| ------------------------------- | ---------------------------------------------------------------------------------------------- | ------------------------------------------ |
| `docs/x.md`                     | the source                                                                                     | the user                                   |
| `docs/x-doc-review.json`        | the review state beside it: artifact link, validations, fingerprints, page language            | only the scripts (never edit it by hand)  |
| `assets/template.html`          | the page template                                                                              | fixed                                      |
| `scripts/extract_doc.py`        | reads the document into sections and blocks                                                    | fixed                                      |
| `scripts/build_page.py`         | builds the HTML, copies the images beside it; `--mark-published` records the link and hash    | fixed                                      |
| `scripts/check_page.cjs`        | runs the page in jsdom and checks it shows everything; fakes Mermaid and the db to test clicks | fixed                                      |
| `scripts/coverage.py`           | proves every piece of the document is on the page, in its section and in order                | fixed                                      |
| `scripts/sync_review.py`        | brings what the user validated on the page into the review state                              | fixed                                      |
| artifact db, collection `review` | validations made on the page                                                                  | the page's buttons                         |

**How the document is cut.** Sections are the headings one level below the title: with a single `#` title they are the `##` headings; without one (or with several `#`), the shallowest headings in the file. Deeper headings stay inside their section as subheadings, and the ones right below a section show in the tree. Text between the title and the first section becomes the "Introduction" section. Front matter (`---` at the top) shows as a key/value box under the title. HTML comments (`<!-- -->`) are notes to the editor and stay out of the page.

## Procedure

Run everything from the project root. `{skill-dir}` is the directory holding this file; `{doc}` is the document's path relative to the root (e.g. `docs/tdd-robo.md`); `{tmp}` is a scratch directory outside the repository.

0. **Bring in the page's validations first**, if `{doc}`'s review state already has an `artifact_url`: follow "Bring validations in" below **before** anyone changes the document. Once the text changes, what was validated on the old text no longer counts.
1. **Read the document.** `python3 {skill-dir}/scripts/extract_doc.py {doc}` shows the sections the page will have. If the cut looks wrong (one giant section, sections that should be subheadings), the document's headings are the problem: tell the user; do not work around it.
2. **Build.** `python3 {skill-dir}/scripts/build_page.py {doc} --out {tmp}/{name}.html`. The language comes from the review state, or is detected from the text; pass `--lang en` or `--lang pt` when the user asks for the other one. Exit 1 means a piece of the document did not reach the page data (`coverage: x.md:N`, a defect in `extract_doc.py`: report it with the line) or the review state contradicts itself. `STALE` warns that the published page is from an earlier version of the document; `RECHECK` names what was validated on text that changed since. Each image the document shows (`![name](img/x.png)`) is copied beside the HTML at the same path, and the build lists them.
3. **Check.** `node {skill-dir}/scripts/check_page.cjs {tmp}/{name}.html [path/to/node_modules/jsdom]` must print `"ok": true`, with `docCoverage: N/N`. It counts sections, table rows and diagrams against the data, checks every piece of the document appears in its section and in order, every internal link has a target and no id repeats, then exercises the validate buttons with a fake db and the drawings with a fake Mermaid (a parse error keeps the source open, numbered steps and `autonumber` messages are clickable, step by step walks them, full screen zooms and gives the drawing back, the dark theme draws again). It finds jsdom from the current directory; if there is none, install it outside the repository (`npm install --prefix {tmp}/jsdom jsdom`) and pass `{tmp}/jsdom/node_modules/jsdom`.
4. **Publish.**
   - **The agent has the `Artifact` tool:**
     - Images: pass every image the build listed in `files`, at the same path (`{"img/x.png": "{tmp}/img/x.png"}`), on the first publish and whenever one changes.
     - New page (no `artifact_url` yet): publish the file with `icon: "document"` and `capabilities: {"db": {"rules": [{"path": "review", "read": "view", "write": "admin"}]}, "user": {}}` (the validate buttons depend on them; only people who can edit the page write). Then `ArtifactData` `list` of the `review` collection confirms access.
     - Republish (`artifact_url` set): publish with `url` = `artifact_url` (reading the artifact first if this conversation has not) and omit `capabilities`, so the artifact keeps its own. The link does not change.
     - After publishing: `python3 {skill-dir}/scripts/build_page.py {doc} --mark-published --url {artifact link}` (the `--url` is only needed the first time). It records the link and the hash of the document that went live, so the next build knows when the page is stale.
   - **No `Artifact` tool:** give the user the absolute path of `{tmp}/{name}.html` to open in a browser (the images are already beside it). The page works offline without the validate buttons and without drawings (Mermaid comes from a CDN; the source shows instead). Review state then comes from what the user tells you.
5. **Tell the user** the link or path, the check result (sections, rows, diagrams, coverage N/N) and any `RECHECK`.

## Validating on the page

On a published artifact the user validates on the page itself: every section with content has "Validate" / "Undo", and every table row has "Confirm" / "Reject" (pressing the lit one again takes it back to pending). A click writes to the artifact db at `review/{key}` (`contexto`, `row:riscos:2`...) as `{state: "validated" | "rejected" | "pending", fp, doc, by, at}`, where `fp` is the fingerprint of the text the user saw. If the document changes later, the fingerprint stops matching and the page shows "validated · changed since" on its own. Only people who can edit the artifact see the buttons.

**Table rows are numbered and reviewed one by one.** Every table row of a section gets a number, `1`, `2`... per section, counted across its tables; a table whose first column already is `#` with the same numbers keeps it. A click on the number copies `Riscos #2`, so the user can cite the row in the conversation; when they do, it is the N-th table row of that section. The section's "Validate" also confirms all its rows, and "Undo" takes them all back to pending. A section counts as validated only when it and all its rows are; one rejected row shows it as "1 row rejected", and the panel lists every rejected row. A rejected row means the user disagrees with it: **ask them what is wrong before changing the document**, never assume.

**Empty sections are not validated.** A section with no content, or whose whole content is `None - <why>` (also `N/A`, `-`, `Nenhum`, `Nada`, `Não se aplica`), shows a "nothing to validate" badge instead of the button and stays out of the progress count.

**Bring validations in** (step 0, and whenever the user asks):

1. `ArtifactData` `list` with `url` = `artifact_url`, `collection: "review"`, `out_dir: {tmp}/review-db`.
2. `python3 {skill-dir}/scripts/sync_review.py {doc} --dir {tmp}/review-db` updates the review state (only what was marked on the current text counts; the rest comes out as `RECHECK`) and prints validated, partly confirmed and pending sections and the rejected rows (`Riscos #2`).
3. Tell the user that summary. If rows were rejected, ask what is wrong with each one before touching the document. Validating sections is not approving the document: if the document has a status or approval field, only the user changes it.
4. Build and publish again, then `--mark-published`.

## Fidelity guarantees

- **Literal text.** The template's `md()` renders inline code, bold, italics, strikethrough, links, autolinks, images and `<br>`; lists keep their nesting and task boxes; quotes, code blocks and horizontal rules render as such. A link to a heading of the document (`[x](#riscos)`) jumps to it; a link to a local file stays as text (the page cannot open it). Markdown it does not render (HTML, footnotes, reference links, setext headings) raises a build warning and shows as raw text, without losing content.
- **Everything, in place and in order.** The build refuses to run if any piece of the document is missing from the data, and the check fails if any piece does not appear inside its section and in document order. `coverage.py`'s `rendered_form` mirrors `md()`: change both together.
- **Version.** The top of the page shows the document's hash and build time; `STALE` from the build means the published page is from another version.
- **Change after validation.** `--mark-published` keeps, in `review_fingerprints`, the fingerprint of the text the user validated for each section and row (publishing never recomputes them). On the next build, what changed becomes "changed since" on the page and `RECHECK` in the terminal, until the user validates again.

## Page rules

- **All of the document, in its order.** One `section` per section, with its subheadings, lists, tables, code, quotes and images. Nothing is summarized, reordered or added.
- **Diagrams are drawn.** Every mermaid block is drawn by Mermaid 11.17.2 from `cdn.jsdelivr.net` (allowed in Artifacts), with its source folded under it and a "Copy source" button; the colours follow the light or dark theme. A sequence or flowchart keeps its natural size and scrolls sideways; the expand icon in its top right corner opens it full screen (wheel, buttons or pinch to zoom, drag to move). Offline, or when a block does not parse, the source stays open with the reason.
- **Numbered steps are walked step by step.** A label that starts with a number (`1. dispara`, `2) responde`) and a message numbered by `autonumber` are steps: a click lights the label, its arrow and its number, fades the other steps, and repeats the step under the drawing. With two steps or more the drawing gets "Step by step" (Previous, one button per step, Next; ← → on them and anywhere in full screen, where the view also moves and zooms to the step). A drawing with no numbers has no stepper.
- **Interface language.** Buttons and labels follow the document (`pt` or `en`); section names, row text and the document's own words are never translated.

## Examples

**First page for a TDD.** The user says: "quero revisar o docs/tdd-robo.md numa página". Actions: `extract_doc.py docs/tdd-robo.md` → `build_page.py docs/tdd-robo.md --out {tmp}/tdd-robo.html` → `check_page.cjs` → publish as a new artifact with the db and user capabilities, passing the listed images in `files` → `--mark-published --url {link}`. Result: "Página publicada: {link}. 20 seções, 113 linhas de tabela, 3 diagramas; check ok, cobertura 675/675."

**The document changed after review.** The user says: "updated the Risks section, refresh the page". Actions: step 0 (pull the `review` collection, `sync_review.py`, tell the summary) → build: it prints `RECHECK riscos` → check → republish to the same `url` → `--mark-published`. Result: same link; Risks shows "validated · changed since" until the user validates it again.

**Agent without the Artifact tool.** Steps 1 to 3, then: "Open /abs/path/to/tdd-robo.html in a browser. The review buttons only exist on a claude.ai artifact; tell me which sections you validate."

## Troubleshooting

- **`ERROR coverage: x.md:N did not reach the page data`**: `extract_doc.py` did not parse that line (often an unusual list or table shape). Report it with the line; do not rewrite the document to get around it unless the user wants to.
- **`WARN x.md:N uses HTML / footnote / reference link / setext heading`**: the page shows that text raw. Suggest the plain Markdown form to the user if it matters.
- **`WARN x.md:N shows img/x.png, which does not exist beside the document`** (or outside its folder, or a remote URL): the page shows only the image's name. Fix the path in the document, or tell the user.
- **One section holds the whole document**: the document has only a `#` title and `###` headings, or skips levels. The shallowest heading below the title is the section level; tell the user to fix the heading levels.
- **Page note `This diagram did not render, so its source is shown: Parse error...`**: the document's mermaid block has a syntax error. The page is right; tell the user with the error.
- **Page note `The drawings need Mermaid, which did not load`**: the page opened without network or something blocked `cdn.jsdelivr.net`.
- **A drawing has no stepper**: its labels are not numbered (`1. x`) and the sequence has no `autonumber`. Numbers are never invented.
- **A row the user cites does not match** (`Riscos #2` is about something else): the document changed since the page was published and rows renumbered. Rebuild and republish.
- **Validate buttons do not appear**: the artifact was published without the `db` and `user` capabilities, or the viewer cannot edit it. Republish with the capabilities from step 4.
- **check_page: `jsdom not found`**: install it outside the repository as in step 3 and pass the path.
