---
name: tlc-spec-review
description: 'Builds an interactive review page that mirrors a local Markdown document section by section and recognizes its format: a tlc-spec-lean plan.md (Visual views, Where / Why / Proof cards, doors, an optional before/after UI preview), a tlc-spec-driven feature (spec, design, tasks and verification as tabs, with EARS criteria, tasks and checks reviewed one by one), or any other document such as a TDD, ADR, RFC or PRD. Every section gets Validate, every table row Confirm / Reject, and scripts prove nothing from the document is missing. Use when the user says "review page", "plan review page", "make a page for the plan", "review this spec as a page", "página de revisão", "quero revisar esse TDD numa página", "update the review page", "UI preview of the plan", or "sync what I validated on the page". Do NOT use for writing, changing or approving the plan, spec or document, or for checking a plan.md structure with validate_plan.py (use tlc-spec-lean or tlc-spec-driven), or for generic diagrams (use mermaid-studio).'
license: CC-BY-4.0
metadata:
  author: Dávilos Tavares - github.com/davilos
  version: '1.1.1'
---

# TLC Spec Review

The page is a **mirror** of local Markdown that makes it easier for people to review it. It is never the source: the `.md` files are what counts, and the page is rebuilt whenever they change. Never edit the generated HTML by hand.

## Profiles

The build picks one and prints it first (`PROFILE tlc-spec-driven 4.x (...)`):

| Profile | What it reads | What the page adds | Read before working on it |
| --- | --- | --- | --- |
| `tlc-spec-lean` | a `plan.md` with `Shape` and `Landing` (older: `Flow` and `Impact`) | Visual / Plan text tabs, Where / Why / Proof cards, doors, ACs as links. **You write the code-derived part** of its review state | [references/tlc-spec-lean.md](references/tlc-spec-lean.md) |
| `tlc-spec-driven` | a feature folder with `spec.md`, `design.md`, `tasks.md`... | one tab per file; EARS criteria, tasks and checks reviewed one by one; IDs linked across tabs | [references/tlc-spec-driven.md](references/tlc-spec-driven.md) |
| `generic` | any other Markdown (TDD, ADR, RFC, runbook, a `plan.md` without those headings); several files the user lists become tabs | nothing: the document's own text, drawn and numbered | - |

**The user's word wins.** When the user names a format ("revisa como genérico", "it's a tlc-spec-driven feature"), pass `--profile`; if detection disagrees, the build warns and goes on with the user's. Otherwise the profile recorded in the review state is kept, so a rebuild never switches. Exit 3 means two profiles fit: ask the user which one. The file name alone never picks a profile. To add a profile, or when detection picks the wrong one, read [references/profiles.md](references/profiles.md).

## Pieces

| Piece | What it is | Who writes it |
| --- | --- | --- |
| the `.md` files | the source | the user (or tlc-spec-lean / tlc-spec-driven) |
| review state | `.specs/features/{slug}/tlc-spec-review.json` for a plan or feature, `{stem}-tlc-spec-review.json` beside a document: artifact link, profile, validations, fingerprints, language | the scripts; for tlc-spec-lean also you (code-derived fields only) |
| `scripts/build_page.py` | picks the profile and builds the HTML; `--mark-published` records the link and hash | fixed |
| `scripts/check_page.cjs` | runs the page in jsdom: everything shown, in place and in order; fakes Mermaid and the db to test clicks | fixed |
| `scripts/sync_review.py` | brings what the user validated on the page into the review state | fixed |
| `scripts/extract.py` | shows the profile, tabs and sections the page will have | fixed |
| `scripts/build_preview.py` + `ui-preview.json` | tlc-spec-lean only, optional: before/after mockups of the screens a plan changes, its own artifact | the script; the mockups you, only when the user wants them |
| artifact db, collection `review` | validations made on the page | the page's buttons |

The older state files (`review-page.json` from plan-review, `{stem}-doc-review.json` from doc-review) are renamed on first use; the artifact link and validations carry over.

## Procedure

Run everything from the project root. `{skill-dir}` is the directory holding this file; `{target}` is what the user points at (a `.md` file, several, a `plan.md`, or a feature folder); `{tmp}` is a scratch directory outside the repository.

0. **Bring in the page's validations first**, if the review state already has an `artifact_url`: follow "Bring validations in" below **before** anyone changes the documents. Once the text changes, what was validated on the old text no longer counts.
1. **Read.** `python3 {skill-dir}/scripts/extract.py {target} [--profile P]` prints the profile, the tabs and the sections. If the cut looks wrong (one giant section, sections that should be subheadings), the document's headings are the problem: tell the user; do not work around it.
2. **tlc-spec-lean only: write or update the code-derived fields** of the review state, as [references/tlc-spec-lean.md](references/tlc-spec-lean.md) says. Every `where` is a `file:line` you checked; never invent a line number.
3. **Build.** `python3 {skill-dir}/scripts/build_page.py {target} --out {tmp}/{name}.html [--profile P] [--lang en|pt]`. One language for the whole page: from the review state, else detected from the first file; pass `--lang` when the user asks for the other one. Exit 1: a piece of a document did not reach the page data (`coverage: x.md:N`, a defect in the extractor: report it with the line), the review state contradicts the documents, or (tlc-spec-lean) your data misstates the plan. `STALE` warns that the published page is from earlier documents; `RECHECK` names what was validated on text that changed since; `AC-CHANGED`, `AC-NEW` and `AC-REMOVED` name the acceptance criteria the reviewer has not seen in their current form (see "Changed criteria" below). Each image a document shows is copied beside the HTML at the same path, and the build lists them.
4. **Check.** `node {skill-dir}/scripts/check_page.cjs {tmp}/{name}.html [path/to/node_modules/jsdom]` must print `"ok": true`, with full coverage (`docCoverage N/N`, and `coverageByFile` per tab; `planCoverage` for a plan). It finds jsdom from the current directory; if there is none, install it outside the repository (`npm install --prefix {tmp}/jsdom jsdom`) and pass `{tmp}/jsdom/node_modules/jsdom`.
5. **Publish.**
   - **The agent has the `Artifact` tool:**
     - Images: pass every image the build listed in `files`, at the same path (`{"img/x.png": "{tmp}/img/x.png"}`), on the first publish and whenever one changes.
     - New page (no `artifact_url` yet): publish with `icon: "document"` and `capabilities: {"db": {"rules": [{"path": "review", "read": "view", "write": "admin"}]}, "user": {}}` (the validate buttons depend on them; only people who can edit the page write). Then `ArtifactData` `list` of the `review` collection confirms access.
     - Republish (`artifact_url` set): publish with `url` = `artifact_url` (reading the artifact first if this conversation has not) and omit `capabilities`, so the artifact keeps its own. The link does not change.
     - After publishing: `python3 {skill-dir}/scripts/build_page.py {target} --mark-published --url {artifact link}` (the `--url` is only needed the first time). It records the link, the profile and the hash that went live, so the next build knows when the page is stale.
   - **No `Artifact` tool:** give the user the absolute path of `{tmp}/{name}.html` to open in a browser (the images are already beside it). The page works offline without the validate buttons and without drawings (Mermaid comes from a CDN; the source shows instead). Review state then comes from what the user tells you.
6. **Tell the user** the profile, the link or path, the check result (sections, rows, diagrams, coverage per file), any `RECHECK` and the changed criteria by citation (`P1 AC 1 changed, P2 AC 1 new, 1 removed from Edge Cases`), so they know where to look. For tlc-spec-lean, say that Where / Why / Proof are your reading of the code.
7. **tlc-spec-lean only: offer the UI preview** when the plan changes the screen. `python3 {skill-dir}/scripts/build_preview.py {plan} --detect` says `ui: yes`, `code-only` or `no`; on `yes`, offer it once with its cost (about 20% more tokens), unless the review state has `"ui_preview": false`. Read [references/ui-preview.md](references/ui-preview.md) before drawing it.

## Validating on the page

On a published artifact the user validates on the page itself: every section with content has "Validate" / "Undo", and every reviewable row has "Confirm" / "Reject" (pressing the lit one again takes it back to pending). A click writes to the artifact db at `review/{key}` (`contexto`, `row:riscos:2`, `spec-user-stories`...) as `{state, fp, doc, by, at}`, where `fp` is the fingerprint of the text the user saw. If the document changes later, the fingerprint stops matching and the page shows "validated · changed since" on its own. Only people who can edit the artifact see the buttons.

**Rows are numbered and reviewed one by one.** Table rows get `1`, `2`... per section; a profile adds its own units (an EARS criterion, a task, a check, a one-way door). A click on the number copies what to cite (`Riscos #2`, `P1 AC 2`, `T1`); when the user cites it in the conversation, `extract.py` shows where it is. The section's "Validate" also confirms all its rows, and "Undo" takes them back to pending. A section counts as validated only when it and all its rows are. A rejected row means the user disagrees with it: **ask what is wrong before changing the document**, never assume.

**Empty sections are not validated.** A section with no content, or whose whole content is `None - <why>` (also `N/A`, `-`, `Nenhum`, `Nada`, `Não se aplica`), shows a "nothing to validate" badge instead of the button and stays out of the progress count.

**Changed criteria** (tlc-spec-lean and tlc-spec-driven). So the reviewer reads only what changed, the review state keeps `ac_baseline`: each acceptance criterion as the reviewer last saw it (a tlc-spec-lean slice's numbered criteria; a tlc-spec-driven spec's EARS items, the profile's `items` with `"ac": true`). The build pairs the current criteria with it by content, so renumbering alone flags nothing, and the page shows "criterion changed" with "See before" (a word diff), "new criterion", the removed ones struck through at the end of their slice or section, and a notice at the top listing them. A flag stays across any number of republishes until the reviewer acknowledges it: confirming or rejecting the criterion on its current text (tlc-spec-driven), or validating its slice or section on its current text; removed criteria also clear with "Seen" (`review/gone:<slice or section>`), the only way when their slice or section is gone. `--mark-published` and `sync_review.py` move the baseline forward only for what was acknowledged. The first publish (no baseline yet) flags nothing. Other units (table rows, tasks, checks, doors) keep only "changed since".

**Bring validations in** (step 0, and whenever the user asks):

1. `ArtifactData` `list` with `url` = `artifact_url`, `collection: "review"`, `out_dir: {tmp}/review-db`.
2. `python3 {skill-dir}/scripts/sync_review.py {target} --dir {tmp}/review-db` updates the review state (only what was marked on the current text counts; the rest comes out as `RECHECK`) and prints validated, partly confirmed and pending sections and the rejected rows.
3. Tell the user that summary. If rows were rejected, ask what is wrong with each one before touching the documents. Validating sections is not approving: if a document has `**Approved**:` or `**Status**:`, only the user (or the skill that wrote the document) changes it.
4. Build and publish again, then `--mark-published`.

## Fidelity guarantees

- **Literal text.** The template renders inline code, bold, italics, strikethrough, links, autolinks, images and `<br>`; lists keep their nesting, task boxes and the code blocks inside items; quotes, code blocks and horizontal rules render as such. A link to a heading jumps to it; a link to a local file stays as text. Markdown the page does not render (HTML, footnotes, reference links, setext headings) raises a build warning and shows as raw text, without losing content.
- **Everything, in place and in order.** The build refuses to run if any piece of any file is missing from the data, and the check fails if any piece does not appear inside its section, in its tab and in document order. The coverage scripts mirror the template's Markdown: change both together.
- **Nothing invented.** Links between IDs exist only for IDs the files define; "cited by" lists only units whose text writes the ID. In tlc-spec-lean, what comes from reading the code is labeled as such on the page.
- **Version.** The page shows the hash of each file and the build time; `STALE` means the published page is from other files.
- **Change after validation.** `--mark-published` keeps the fingerprint of the text the user validated for each section and row (publishing never recomputes them). On the next build, what changed becomes "changed since" on the page and `RECHECK` in the terminal, until the user validates again.

## Page rules

- **All of the documents, in their order.** One `section` per section, with its subheadings, lists, tables, code, quotes and images. Nothing is summarized, reordered or added.
- **Tabs.** A page with several files has one tab per file, each with its own title, path and hash; the tree shows the sections of the open tab, and a link to another tab opens it. A missing expected file is a switched-off tab.
- **Diagrams are drawn.** Every mermaid block is drawn by Mermaid 11.17.2 from `cdn.jsdelivr.net` (allowed in Artifacts), with its source folded under it and a "Copy source" button; colours follow the light or dark theme. The expand icon opens it full screen (wheel, buttons or pinch to zoom, drag to move). Offline, or when a block does not parse, the source stays open with the reason.
- **Numbered steps are walked step by step.** A label that starts with a number (`1. dispara`) and a message numbered by `autonumber` are steps: a click lights the label, its arrow and its number, and repeats the step under the drawing. With two steps or more the drawing gets "Step by step" (Previous, one button per step, Next; ← → in full screen too). A drawing with no numbers has no stepper; numbers are never invented.
- **Interface language.** Buttons and labels follow the page language (`pt` or `en`); section names, row text and the documents' own words are never translated.

## Examples

**First page for a TDD.** The user says: "quero revisar o docs/tdd-robo.md numa página". Actions: `extract.py docs/tdd-robo.md` (generic) → `build_page.py docs/tdd-robo.md --out {tmp}/tdd-robo.html` → `check_page.cjs` → publish as a new artifact with the db and user capabilities, passing the listed images in `files` → `--mark-published --url {link}`. Result: "Página publicada: {link}. Perfil generic; 20 seções, 113 linhas, 3 diagramas; check ok, cobertura 675/675."

**A tlc-spec-driven feature.** The user says: "faz a página de revisão da feature lembrete-vencimento". Actions: `extract.py .specs/features/lembrete-vencimento` (tlc-spec-driven 4.x: spec, design, tasks, verification) → build → check → publish → `--mark-published --url {link}`. Result: "Página publicada: {link}. 4 abas, 40 itens revisáveis (P1 AC 1…, T1–T4, C1–C3), 33 links entre IDs; cobertura spec 73/73 · design 81/81 · tasks 66/66 · verification 23/23."

**A plan after review.** The user says: "updated S2 in the plan, refresh the page". Actions: step 0 (pull the `review` collection, `sync_review.py .specs/features/dunning/plan.md --dir ...`, tell the summary) → build: `RECHECK change:2` → re-read the code, fix the code-derived fields → build, check, republish to the same `url`, `--mark-published`. Result: same link; S2 shows "validated · changed since" until the user validates it again.

**The user names the format.** The user says: "revisa esse plan.md como documento genérico". Actions: `build_page.py .specs/features/x/plan.md --profile generic --out ...`; the build warns that detection points to tlc-spec-lean and goes on with generic. Result: the plan as a plain mirror, with its own state beside it (`plan-tlc-spec-review.json`).

**Agent without the Artifact tool.** Steps 1 to 4, then: "Open /abs/path/to/page.html in a browser. The review buttons only exist on a claude.ai artifact; tell me which sections you validate."

## Troubleshooting

- **Exit 3, `ambiguous: tlc-spec-lean (...); tlc-spec-driven (...)`**: the folder has both a tlc-spec-lean plan and tlc-spec-driven files. Ask the user which one and pass `--profile`.
- **`no profile recognizes the folder ...`**: point at the files themselves (generic, one tab each), or pass `--profile tlc-spec-driven` if the user says it is one.
- **`ERROR coverage: x.md:N did not reach the page data`**: the extractor did not parse that line (often an unusual list or table shape). Report it with the line; do not rewrite the document to get around it unless the user wants to.
- **`WARN x.md:N uses HTML / footnote / reference link / setext heading`**: the page shows that text raw. Suggest the plain Markdown form if it matters.
- **`WARN x.md:N shows img/x.png, which does not exist beside the document`** (or outside its folder, or a remote URL): the page shows only the image's name. Fix the path, or tell the user.
- **One section holds the whole document**: the document has only a `#` title and `###` headings, or skips levels. Tell the user to fix the heading levels.
- **Page note `This diagram did not render, so its source is shown: Parse error...`**: the mermaid block has a syntax error. The page is right; tell the user with the error.
- **Page note `The drawings need Mermaid, which did not load`**: the page opened without network or something blocked `cdn.jsdelivr.net`.
- **A row the user cites does not match** (`Riscos #2` is about something else): the documents changed since the page was published and rows renumbered. Rebuild and republish.
- **Validate buttons do not appear**: the artifact was published without the `db` and `user` capabilities, or the viewer cannot edit it. Republish with the capabilities from step 5.
- **check: `jsdom not found`**: install it outside the repository as in step 4 and pass the path.
- **tlc-spec-lean build errors** (`... is not in the plan`, `where has prose`, `door N is cited, but the Landing has 0 door(s)`...): see [references/tlc-spec-lean.md](references/tlc-spec-lean.md#troubleshooting-this-profile).
