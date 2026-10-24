---
name: plan-review
description: 'Builds an interactive HTML review page that mirrors a tlc-spec-lean plan.md section by section, with visual Problem / Flow / Impact / Landing views, per-section validation, and scripts that prove nothing from the plan is missing. Publishes it as an Artifact when available, otherwise writes a local HTML file. Use right after a tlc-spec-lean plan passes validate_plan.py and on every new plan version, or when the user says "plan review page", "make a page for the plan", "show the plan as a page", "interactive plan", "plan-review", "update the plan page", or "sync what I validated on the page". Do NOT use for writing or changing the plan, or for checks, build or verify (use tlc-spec-lean), for cutting a PRD into tasks (use tlc-plan), or for generic diagrams (use mermaid-studio).'
license: CC-BY-4.0
metadata:
  author: Dávilos Tavares - github.com/davilos
  version: '1.1.1'
---

# Tech Lead's Club - Plan Review

The page is a **mirror** of `plan.md` that makes it easier for people to review. It is never the source: `plan.md` is what counts, and the page is rebuilt whenever it changes. Never edit the generated HTML by hand; change `plan.md` or `review-page.json` and build again.

## Pieces

| Piece                                     | What it is                                                                                                                            | Who writes it            |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- | ------------------------ |
| `.specs/features/{slug}/plan.md`          | the source: section text, criteria, status                                                                                            | tlc-spec-lean / the user |
| `.specs/features/{slug}/review-page.json` | what requires reading the code: Where / Why / Proof, Flow paths, Impact cards, Landing in plain language, review state, artifact link | you, in this skill       |
| `assets/template.html`                    | the page template                                                                                                                     | fixed                    |
| `scripts/extract_plan.py`                 | reads plan.md (the mechanical part)                                                                                                   | fixed                    |
| `scripts/build_page.py`                   | validates review-page.json against the plan and builds the HTML                                                                       | fixed                    |
| `scripts/check_page.cjs`                  | runs the page in jsdom and checks it shows everything; fakes the db to test the validate buttons                                      | fixed                    |
| `scripts/coverage.py`                     | proves every piece of plan.md is on the page, in its section and in order                                                             | fixed                    |
| `scripts/sync_review.py`                  | brings what the user validated on the page into review-page.json                                                                      | fixed                    |
| artifact db, collection `review`          | validations made on the page                                                                                                          | the page's buttons       |

Read [references/review-page-json.md](references/review-page-json.md) before writing or changing `review-page.json`: it has every field, the `where` format and a minimal example.

## Procedure

Run everything from the project root (where `.specs/` lives). `{skill-dir}` is the directory holding this file; `{tmp}` is a scratch directory outside the repository.

0. **Bring in the page's validations first**, if `review-page.json` already has an `artifact_url`: follow "Bring validations into the plan" below **before** changing plan.md. The user validates on the page and nothing carries that into plan.md on its own; once the text changes, what they validated on the old text no longer counts. Changing only code-derived fields in review-page.json (Where, Why, cards, paths) touches no validation and skips this step.
1. **Read the plan.** `python3 {skill-dir}/scripts/extract_plan.py --root . {slug}` shows what the page will mirror. If a section comes out empty or odd, the problem is in the plan; tell the user.
2. **Write or update `review-page.json`.** If it exists, start from it and change only what the plan changed. The code-derived parts (`changes`, `flow_visual`, `impact_visual`, `problem_visual`) require reading the code: every `where` is a `file:line` you actually checked. To sweep many files, delegate to a search subagent and keep only the conclusions. **Never invent a line number**; when unsure, cite the file without the line. `landing_visual` is required whenever the Landing has doors.
3. **Review state** (`review`, `doors_confirmed`, tags) comes only from what the user said or from the plan's `**Status**:` line. Validating sections is not approving the plan: the tag says "plan in review" until the user says they approve it.
4. **Build.** `python3 {skill-dir}/scripts/build_page.py --root . {slug} --out {tmp}/{slug}.html`. Exit 1 means review-page.json misstates or hides something in the plan (criterion that does not exist, Impact row without a card, Flow hop without a path, Landing door without a `landing_visual` entry, new name the plan does not have and is not marked `tbd`, Where with prose, line range that diverges from the same range in the plan...) or a piece of plan.md did not reach the page data (`coverage: plan.md:N`). Fix review-page.json; a coverage failure is a defect in `extract_plan.py`, not in your data. `STALE` warns that the published page is from an earlier plan.md.
5. **Check.** `node {skill-dir}/scripts/check_page.cjs {tmp}/{slug}.html [path/to/node_modules/jsdom]` must print `"ok": true`. It counts sections, criteria, changes, cards and paths against the data, clicks every kind of row, checks every internal link has a target and that **every piece of plan.md appears in the page text** (`planCoverage: N/N`). It finds jsdom from the current directory; if the project has none, install it outside the repository (`npm install --prefix {tmp}/jsdom jsdom`) and pass `{tmp}/jsdom/node_modules/jsdom`.
6. **Publish.**
   - **The agent has the `Artifact` tool** (Claude Code with claude.ai artifacts):
     - New page (`artifact_url` empty): follow the tool's rules for a new artifact, publish the file with `icon: "code"` and `capabilities: {"db": {"rules": [{"path": "review", "read": "view", "write": "admin"}]}, "user": {}}` (the validate buttons depend on them; only people who can edit the page write), and store the URL in `artifact_url`. Then an `ArtifactData` `list` of the `review` collection confirms access.
     - Republish (`artifact_url` set): publish with `url` = `artifact_url` (reading the artifact first if this conversation has not, as the tool requires) and omit `capabilities` so the artifact keeps its own. The link does not change.
   - **No `Artifact` tool:** give the user the absolute path of `{tmp}/{slug}.html` to open in a browser. The page works offline, without the validate buttons; review state comes from what the user tells you, recorded in `review` / `doors_confirmed`.

   After publishing: `python3 {skill-dir}/scripts/build_page.py --root . {slug} --mark-published` records in review-page.json the hash of the plan.md that went live, so the next build knows when the page is stale.

7. **Tell the user** what changed on the page, the check result (including coverage N/N) and the link or file path.

## Validating on the page

On a published artifact the user validates the plan on the page itself: every section and slice has "Validate" / "Undo", and every One-way door has "Confirm". A click writes to the artifact db at `review/{key}` (`problem`, `S1`, `door:1`...) as `{state: "validated" | "pending", fp, plan, by, at}`, where `fp` is the fingerprint of the validated text. If the plan changes later, the fingerprint stops matching and the page shows "validated · changed since" on its own. Only people who can edit the artifact see the buttons; outside claude.ai (or without the db) the page shows the state from review-page.json, with no buttons.

**Empty sections are not validated.** A section with no content, or whose whole content is a single `None - <why>` (also `nothing`, `N/A`, `-`), such as `Relations` with `None - no stored-data shape change`, comes out of `extract_plan.py` with `empty: true`. The page still shows its text, with a "nothing to validate" badge instead of the button, and leaves it out of the progress count and the "Not reviewed" list. Do not put it in `review`: the build ignores it with a warning, and `sync_review.py` lists it under "nothing to validate" rather than "pending". Once the plan gives it real content, it needs validating like any other section.

**Bring validations into the plan** (step 0, and whenever the user asks):

1. `ArtifactData` `list` with `url` = `artifact_url`, `collection: "review"`, `out_dir: {tmp}/review-db`.
2. `python3 {skill-dir}/scripts/sync_review.py --root . {slug} --dir {tmp}/review-db` updates `review` and `doors_confirmed` in review-page.json (only what was validated on the current text counts; the rest comes out as `RECHECK`) and prints the validation part of the `**Status**:` line.
3. Update the plan.md `**Status**:` line with that text. Approving the plan is still the user's word, not the sum of the badges.
4. Build and publish again, then `--mark-published`.

## Fidelity guarantees

The user reviews the plan through the page, so the page must be faithful to `plan.md`, and that is proven, not assumed:

- **Literal text.** The template's `md()` only turns backticks into code and `**` into bold; everything else (parentheses, `->`, punctuation) renders as in the plan. Markdown it does not render (link, strikethrough, italics, HTML, nested list, `####`, blockquote) raises a build warning: the page shows the raw text without losing content.
- **Everything, in place and in order.** The build refuses to run if any piece of plan.md (paragraph, item, cell, section or slice title) is missing from the data. The check fails if any piece does not appear **inside its section and in plan order**; sections with the Visual | Plan text tabs are checked on the "Plan text" view, which is the binding text.
- **Version.** The top of the page shows the plan.md hash and build time; `STALE` from the build means the published page is from another plan.md.
- **Change after validation.** `--mark-published` records the fingerprint of the part of the plan each derived item came from and, in `review_fingerprints`, that of the text the user validated for each section, slice and door (publishing never recomputes those; it only adds missing ones). On the next build, what changed becomes a badge on the page and `RECHECK` in the terminal: "validated · changed since" on a section, slice or door validated on other text, and "re-check: the plan changed here" on a card, path, symptom or change whose source changed since the last publish (ranges such as `AC 13–15` are expanded). On a `RECHECK` for a derived item, re-read the code and the plan and update review-page.json; the badge on a validated section only clears when the user validates again (on the page, brought in by `sync_review.py`, which records the new fingerprint).

Tell the user what is **not** plan: Where / Why / Proof, symptoms, cards and paths are a reading of the code and the plan by whoever built the page.

## Page rules

- **All of the plan, in plan order.** Each section carries the exact plan text; in visual sections it sits in the "Plan text" tab (the section opens on "Visual"). The build rejects an Impact row without a card.
- **Flow: one card per node, each with its own Where.** The same node in several paths carries `change` only the first time (the build rejects repeats); copies open the same card. Different nodes share a `change` only when Where / Why / Proof really are the same; if each touches different lines or is proven by different criteria, each gets its own change.
- **The page is checked against the plan, not the code.** The build does not read git: confirming a line exists is the plan author's job. It rejects what the page claims against the plan (a name the plan does not have, a line range different from the one the plan cites) and warns on a repeated Where and on different nodes opening the same change (`shared: true` when deliberate). A reference the plan does not cite is your own reading and passes.
- **Struck-through → new is a rename.** When only part of a file moves and the file stays, say what moves (`old`/`before`: "exceptions in `a.py`" → `neu`/`after`: "exceptions in `b.py`"); striking out the whole file makes readers think it disappears or is renamed.
- **Landing for people.** The plan is written for the agent; the Landing's Visual tab explains each door in plain language (`landing_visual`: what is decided, what we chose, why it is hard to undo, what happens on deploy, what was rejected and why). Nothing new: everything comes from the plan.
- **A name the plan does not fix is "not defined".** A new module marked `placement per conventions` without a name, a name the build will decide: the node, change or card takes `tbd: true`, and its name field describes what it will be (e.g. "send errors, no channel in the name"). The page shows a "not defined" badge with the description. Never invent the name.
- **Plan nomenclature is not translated:** "One-way door N" / "door N", section names, slice ids, hop, Literal shape, Alternative rejected.
- **Proof as links.** In Proof (and in the Problem's "Fixed in"), `AC N`, `AC N to M`, `AC N–M`, `AC N, M` become links to each criterion; `door N` to the One-way door in the Landing; `S1` to the slice. Write Proof in that form so the link exists.
- **Where / Why / Proof** on everything clickable: Where = files and lines; Why = the reason in one or two sentences; Proof = the criterion (and door) that guarantees it.

## Examples

**First page for a plan.** The user says: "plan is ready, make the review page". Actions: `extract_plan.py` → read the code behind each Flow hop, Impact row and Landing door → write `review-page.json` with `artifact_url: ""` → `build_page.py` (fix every ERROR it reports) → `check_page.cjs` → publish as a new artifact with the db and user capabilities → `--mark-published`. Result: "Page published: {link}. 12 sections, 6 criteria, 3 changes; check ok, coverage 117/117. Where / Why / Proof are my reading of the code."

**The plan changed after review.** The user says: "I updated S2 in the plan, refresh the page". Actions: step 0 (pull the `review` collection, `sync_review.py`, update `**Status**:`) → build: it reports `RECHECK change:2` and an ERROR for the new criterion missing from a card → re-read the code, fix review-page.json → build, check, republish to the same `url`, `--mark-published`. Result: same link; S2 shows "validated · changed since" until the user validates it again.

**Agent without the Artifact tool.** Same steps 1 to 5, then: "Open /abs/path/to/dunning.html in a browser. The review buttons only exist on a claude.ai artifact; tell me which sections you validate and I will record them."

## Troubleshooting

- **`ERROR ... is not in the plan; a name the plan does not fix takes tbd: true`**: you used a name the plan does not have. Use the plan's name, or mark the item `tbd: true` and describe it.
- **`ERROR ... where has prose`**: Where takes only `file[:lines]` or `folder/`, separated by `·`; move the explanation to `why`.
- **`ERROR coverage: plan.md:N did not reach the page data`**: `extract_plan.py` did not parse that line (often an unusual table or list shape). Report it with the line; do not work around it in review-page.json.
- **check_page: `jsdom not found`**: install it outside the repository as in step 5 and pass the path.
- **check_page: `internal links without a target`**: a Proof cites a door, slice or criterion that does not exist on the page; fix the Proof text.
- **Validate buttons do not appear**: the artifact was published without the `db` and `user` capabilities, or the viewer cannot edit it. Republish with the capabilities from step 6.
