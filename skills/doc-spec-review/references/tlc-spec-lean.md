# tlc-spec-lean profile

Read this before writing or changing the review state of a tlc-spec-lean plan. The plan is tlc-spec-lean 2.x: `**Approved**:` under the title, then `Problem`, `Shape` (the numbered path, its mermaid drawings, the `Changes underneath` table, the `erDiagram` and `New:` line), `Surface`, `Landing`, `Criteria`, `Out of scope`, `Assumptions`, `Differences from the source` and `Sources`. Older plans (`**Status**:`, `Flow`, `Impact`, `Relations`, `Observable`) still build: the path visual goes on `Flow` and the cards on `Impact`.

## What you write

The review state (`.specs/features/{slug}/doc-spec-review.json`; the old `review-page.json` is renamed on the first build) holds what the page needs and `plan.md` does not have. Unlike the other profiles, you write part of it:

1. **Code-derived fields** (`changes`, `flow_visual`, `impact_visual`, `problem_visual`, `landing_visual`): they require reading the code. Every `where` is a `file:line` you actually checked; to sweep many files, delegate to a search subagent and keep only the conclusions. **Never invent a line number**; when unsure, cite the file without the line. `landing_visual` is required whenever the Landing has doors. If the file exists, start from it and change only what the plan changed.
2. **Review state** (`review`, `doors_confirmed`, `rejected`, `tags`) comes only from what the user said or marked on the page. Validating sections is not approving the plan: approval is the user's word, which tlc-spec-lean writes as `**Approved**:` under the title. The tag says "plan in review" until the plan carries that line; never write `**Approved**:` from the badges. An older plan with a `**Status**:` line takes the sync summary into that line.
3. Changing only code-derived fields touches no validation, so it skips bringing the validations in first.

Tell the user what is **not** plan: Where / Why / Proof, symptoms, cards and paths are a reading of the code and the plan by whoever built the page.

**Build errors that point at your data** (exit 1): a criterion that does not exist, a `Changes underneath` row without a card, a path hop without a `flow_visual` path, a Landing door without a `landing_visual` entry, a new name the plan does not have and is not marked `tbd`, a Where with prose, a line range that diverges from the same range in the plan. Fix the review state; a `coverage: plan.md:N` failure is a defect in `lean_extract.py`, not in your data. On a `RECHECK` for a derived item (`change:2`, `flow:1`...), re-read the code and the plan and update the field.

## Page rules (this profile)

- **Visual | Plan text tabs.** Each section carries the exact plan text; visual sections open on "Visual" and keep the text in "Plan text", which is the binding text the check proves. Shape's Visual shows "The drawing" (the `sequenceDiagram` or `flowchart`), "Changes underneath" (`impact_visual`), "The data" (`erDiagram`) and "States" (`stateDiagram-v2`). The cards of `flow_visual` open from the drawing; they show as a "The path" list only when the plan has no path drawing or it could not be drawn.
- **Diagrams show what changes.** A block is green when the plan changes it, grey otherwise: a node with `o` or `note` in `flow_visual`, a module the path marks `(new)` or `(door N)`, what the `New:` line adds, and the term of each `domain` row of `Changes underneath`.
- **Diagrams answer clicks with the plan.** A numbered step shows that hop's line of the path and its `flow_visual` cards, whose changed nodes open their Where / Why / Proof; a name the path, the cards or `Changes underneath` use shows the hops it is on, its cards and rows; `door N` links to the door. Steps come only from the `N.` labels the plan wrote.
- **Path: one card per node, each with its own Where.** The same node in several paths carries `change` only the first time (the build rejects repeats). Different nodes share a `change` only when Where / Why / Proof really are the same (`shared: true` when deliberate).
- **Struck-through → new is a rename.** When only part of a file moves, say what moves (`old`: "exceptions in `a.py`" → `neu`: "exceptions in `b.py`").
- **Landing for people.** The Landing's Visual tab explains each door in plain language (`landing_visual`): what is decided, what we chose, why it is hard to undo, what happens on deploy, what was rejected and why. Nothing new: everything comes from the plan.
- **A name the plan does not fix is "not defined".** The node, change or card takes `tbd: true`, and its name field describes what it will be. Never invent the name.
- **Plan nomenclature is not translated:** "One-way door N", section names, slice ids, hop, Literal shape, Alternative rejected.
- **Proof as links.** `AC N`, `AC N to M`, `AC N–M`, `AC N, M` link to each criterion; `door N` to the door; `S1` to the slice.
- **The page is checked against the plan, not the code.** The build does not read git. It rejects what the page claims against the plan and warns on a repeated Where.
- **Rows and doors.** Every table row of a section gets a number and Confirm / Reject; in Landing, the rows are the doors, and a door never inherits its section's state. Criteria slices, ACs and path hops are already numbered and stay as they are.

## Troubleshooting (this profile)

- **`ERROR ... is not in the plan; a name the plan does not fix takes tbd: true`**: use the plan's name, or mark the item `tbd: true` and describe it.
- **`WARN ... has backticks, which the page shows literally`**: a name field (`neu`, `old`, `n`, `o`, `before`, `after`) already renders as code; write the name without backticks.
- **`ERROR ... where has prose`**: Where takes only `file[:lines]` or `folder/`, separated by `·`; move the explanation to `why`.
- **`ERROR door N is cited, but the Landing has 0 door(s)`**: the Landing table's first header is not `One-way door`. Fix the header in the plan (tlc-spec-lean's form), or drop the door citations.
- **`WARN plan.md:N shows captures/x.png, which does not exist beside plan.md`**: the plan is wrong (tlc-spec-lean's `validate_plan.py` also flags it); tell the user.
- **`ERROR coverage: plan.md:N did not reach the page data` on several `**Approved**:` lines**: `lean_extract.py` reads only the first approval line under the title. Report it; do not rewrite the plan to get around it unless the user wants to.
- **check: `internal links without a target`**: a Proof cites a door, slice or criterion that does not exist on the page; fix the Proof text.

## The review state

Every field is optional unless stated; without `problem_visual`, `flow_visual` or `impact_visual`, the matching section shows only the plan text. `flow_visual` and `impact_visual` both go on `## Shape` (on `## Flow` and `## Impact` in older plans).

Text with backticks (`` `x` ``) and `**bold**` renders as code and bold in fields marked _(md)_; other fields render as written. Write prose fields (`why`, `today`, `decide`, `hard`...) in the language the plan's reviewers read.

Proof fields (`changes[].proof`, `impact_visual.cards[].proof`, `problem_visual.symptoms[].fix.proof`, `landing_visual.doors[].proof`) become links: in `AC 10 to 12`, `AC 1–3`, `AC 10, 12` or `AC 5 and 6`, every number written links to its criterion (`#ac-N`), so list a criterion explicitly when it needs its own link; `door N` to the One-way door (`#door-N`); `S5` to the slice (`#slice-S5`). Every criterion cited after `AC` must exist in the plan; the build rejects otherwise and the check rejects a link with no target.

### Contents

- Header and review
- Changes (Criteria)
- problem_visual
- flow_visual
- landing_visual
- impact_visual
- Minimal example

### Header and review

| Field                    | Type              | What it is                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| ------------------------ | ----------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `title`                  | string            | tab and artifact name (2 to 4 words, stable across publishes)                                                                                                                                                                                                                                                                                                                                                                                             |
| `artifact_url`           | string            | the artifact link; empty the first time                                                                                                                                                                                                                                                                                                                                                                                                                   |
| `plan_path`              | string            | plan path, shown at the top and in the footer                                                                                                                                                                                                                                                                                                                                                                                                             |
| `published_plan_hash`    | string            | written by `build_page.py --mark-published`: hash of the plan.md last published; do not edit by hand                                                                                                                                                                                                                                                                                                                                                      |
| `published_at`           | string            | written with it: when it was published                                                                                                                                                                                                                                                                                                                                                                                                                    |
| `published_fingerprints` | `{key: hash}`     | written with it: fingerprint of each section, slice (`S1`), door (`door:1`), table row (`row:assumptions:2`) and derived item (`impact:N`, `flow:N`, `change:N`, `symptom:N`, `problem-visual`) at publish time; the build compares against it to flag what changed since. Do not edit by hand                                                                                                                                                                                             |
| `review_fingerprints`    | `{key: hash}`     | fingerprint of the text the user validated or rejected for each section, slice, door and table row marked; the build compares against it to show "validated · changed since". `--mark-published` writes it for keys that have none yet (the current text counts) and never recomputes the others; `sync_review.py` writes the one from a validation made on the page. When you mark a validation by hand in `review`, do not create the key: the next `--mark-published` does |
| `code_ref`               | string            | repo, branch and commit read for the Where (e.g. `billing-api feat/dunning @ f75a388c9`)                                                                                                                                                                                                                                                                                                                                                                  |
| `tags`                   | `[{text, warn?}]` | top-of-page tags; `warn: true` paints it amber (use it for "plan in review")                                                                                                                                                                                                                                                                                                                                                                              |
| `review`                 | `{id: bool}`      | review state when the page has no db (outside claude.ai) or the item was not marked on it yet; what the user marks on the page (db `review/{key}`) wins, and `sync_review.py` brings it back here. Section ids: `problem`, `shape`, `surface`, `landing`, `criteria`, `out`, `assumptions`, `questions`, `differences` (Differences from the source), `sources` (older plans: `flow`, `impact`, `relations`, `observable`); slice ids: `S1`, `S2`...; table row ids: `row:{section}:{n}` (`row:assumptions:2`, the N-th table row of the section, 1-based, counted across its tables; Landing door rows are doors, not rows). Missing = "not reviewed"; a row missing takes its section's value. Leave out empty sections (no content or only `None - <why>`): they have nothing to validate and the build ignores them                                                 |
| `doors_confirmed`        | `[int]`           | numbers of the one-way doors the user confirmed                                                                                                                                                                                                                                                                                                                                                                                                           |
| `rejected`               | `[key]`           | table rows (`row:shape:3`) and doors (`door:2`) the user rejected: what they want to discuss. A key cannot be both here and validated (`review` true or in `doors_confirmed`); the build rejects that. `sync_review.py` writes it from the page                                                                                                                                                                                                                  |

Doors are the rows of the first `## Landing` table whose first header is `One-way door` (the tlc-spec-lean form), numbered by row (first row = door 1), the same numbering the plan uses in "(door N)". A first cell written as `1. name` also works. A Landing table with any other header is plain text, with no doors.

### Changes (Criteria)

`changes`: a list; each item becomes a clickable row under its slice.

| Field   | Required | What it is                                                                                                                           |
| ------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `s`     | yes      | slice id (`S1`...)                                                                                                                   |
| `neu`   | yes      | the new name or state, without backticks: the page already shows it as code                                                          |
| `old`   | no       | today's name (shown struck through); without it the row shows only `neu`                                                             |
| `k`     | no       | kind, free text (e.g. `internal`, `contract`); becomes a filter                                                                      |
| `where` | yes      | Where: files and lines you checked                                                                                                   |
| `why`   | yes      | Why                                                                                                                                  |
| `proof` | yes      | Proof: criteria, e.g. `AC 10, 12` or `AC 1–3` (every number cited must exist in the plan)                                            |
| `door`  | no       | number of the linked one-way door                                                                                                    |
| `tbd`   | no       | `true` when the plan does not fix the new name yet: `neu` carries a description of what it will be, and the page shows "not defined" |

**`where` format** (change, card, symptom): code references only, no prose. Items separated by `·`, each `file[:lines]` (`billing.py:172,187,439`) or a folder path ending in `/` (`tests/billing/`). Whatever explains the reference (it is the route, how many occurrences, which decision) goes in `why`, also as `file:line`, never `(:N)`. When the plan already cites the reference, use the plan's form. The build rejects an item with prose.

`warn_kinds`: kinds of `k` painted amber (e.g. `["contract"]`).
`slice_notes`: `{"S5": "text"}` for a slice with no changes (e.g. guarantees only).

### problem_visual

| Field             | What it is                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `symptoms`        | `[{what, today (md), where, fix, pays}]`: what is wrong today; the open card shows Where (`where`), Today (`today`), Fixed in (`fix`) and Who pays                                                                                                                                                                                                                                                                                                                                                                              |
| `symptoms[].fix`  | `{slice, proof, door?, text? (md)}`: the slice (link) and the criteria that fix the symptom; slice and criteria must exist in the plan                                                                                                                                                                                                                                                                                                                                                                                          |
| `symptoms[].pays` | `[int]`: indexes into `pays` this symptom hits                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| `pays`            | `[string (md)]`: who pays, copied from the plan's Problem section and nothing beyond: no payer the Problem does not name, no role or detail the Problem does not give (Problem says "the MASTER" → `"the MASTER"`, not `"the MASTER who configures the robot"`); becomes a filter that highlights the linked symptoms. The build warns if one highlights none, or if its text does not appear in the Problem (the comparison is literal, so the same payer written differently also warns: rewrite it as the Problem writes it) |
| `why_now`         | string (md)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `outcome`         | string (md): what changes once it ships                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |

### flow_visual

`paths`: `[{title, when, hop, nodes}]`. When Shape draws the path (a `sequenceDiagram` or `flowchart`), these cards open from the drawing: a click on step N shows the paths of hop N, a click on a module the paths it is on; they only show as a list without a drawing. A node with `o` or `note` also paints its block green in the drawings. `hop` = the number of the Shape path line the path represents (the `## Flow` item in older plans) (every hop in the plan needs at least one path; two paths may share a hop).

Each node: `{k, n, o?, d?, note?, change?, tbd?, shared?}`: `k` = kind (job, task, module, client, config, metric, webhook, output), `n` = new name, `o` = today's name, `d` = door, `note` = what changes when the name does not, `change` = index into `changes` whose Where / Why / Proof the click opens. `tbd: true` = the plan does not fix the name yet: `n` carries a description, and the node shows "not defined". `shared: true` = this node deliberately opens the same change as another, different node (same Where / Why / Proof); without it, the build warns. A node with `o` or `note` is green; without `change` it is not clickable (the build warns).

**One card per node:** when the same node (same `n`) appears in more than one path, only the first occurrence, in `paths` order, carries `change`; the others keep `o`/`d`/`note` (still green) and have no `change`. Every copy opens the same card (the page takes the `change` from the occurrence that has it); while it is open, the page highlights the other copies and dims every other node. The build rejects the same `n` with `change` twice. Different nodes point to the same `change` only when Where / Why / Proof really are the same (e.g. modules of the same renamed package that change in the same place). If each node touches different lines or is proven by different criteria (e.g. the email counter and the SMS counter), each gets its own entry in `changes`.

### landing_visual

The plan's Landing is written for the agent (Literal shape, Alternative rejected); people do the validating. `landing_visual` is required when the Landing has doors (the build refuses to run without it): the Visual tab explains each door in plain language, and the plan's table stays in the "Plan text" tab. Each door's "Confirm" button lives in the Visual tab.

`intro` (md, optional): what a One-way door is, in one sentence anyone on the team understands.
`doors`: one per door in the plan (the build rejects a door without an explanation), each `{n, title, decide, choice, hard, risk?, alternatives?, proof?}`:

| Field          | What it is                                                        |
| -------------- | ----------------------------------------------------------------- |
| `n`            | the door number in the plan                                       |
| `title`        | a short, clear name for what is decided                           |
| `decide`       | the question the door answers, without jargon                     |
| `choice`       | what was chosen, with the exact names (rendered as code)          |
| `hard`         | why it is hard to undo: who comes to depend on the name           |
| `risk`         | what happens on deploy (from Shape's `Changes underneath`)        |
| `alternatives` | `[[option, why not]]`, taken from Alternative rejected            |
| `proof`        | criteria that guarantee it, e.g. `AC 10 to 12, 15` (become links) |

Nothing here is a new decision: everything comes from the plan's Landing, Shape and criteria.

### impact_visual

| Field       | What it is                                                                                                                                                    |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `audiences` | `[string]`: who feels it (filter)                                                                                                                             |
| `groups`    | `[[id, label]]`, e.g. `[["code","Changes in code"],["ops","Changes in operations"],["same","Does not change"]]`; `code`/`ops`/`same` have their own colour    |
| `cards`     | see below; **every row of Shape's `Changes underneath` table needs at least one card** (the `## Impact` table in older plans)                                  |
| `keep`      | `[[names, reason]]`: a list opened on the card with `keep: true`; several names in `names` are separated by `·` (each one becomes code, always the full name) |
| `tree`      | `{before: [[text, class, note]], after: [...]}`: a file tree opened on the card with `tree: true`; class `del`, `add` or `""`                                 |

Card: `{g, row, title, before?, after?, tbd?, who, risk?, where, why, proof, keep?, tree?}`. `tbd: true` = the name in `after` is not fixed in the plan yet: `after` carries the description, and the card shows "not defined". `row` = 0-based index of the `Changes underneath` row (the table whose first header is `Front`); its text appears in the open card. `where` (Where), `why` (Why) and `proof` (Proof) are required; on a card with `keep: true` Where is optional (the list is the content; do not write "the list below").

### Minimal example

For a plan with one slice, one Shape path line, one `Changes underneath` row and one door:

```json
{
  "title": "Dunning plan review",
  "artifact_url": "",
  "plan_path": ".specs/features/dunning/plan.md",
  "tags": [{ "text": "plan in review", "warn": true }],
  "changes": [
    {
      "s": "S1",
      "old": "Active = has a row",
      "neu": "Suspended in subscriptions.status",
      "k": "contract",
      "where": "app/models/subscription.rb",
      "why": "New enum value read by `AccessPolicy#grant?`.",
      "proof": "AC 1 to 3",
      "door": 1
    }
  ],
  "flow_visual": {
    "paths": [
      {
        "title": "Apply",
        "when": "failed charge",
        "hop": 1,
        "nodes": [{ "k": "module", "n": "Billing::Subscription", "note": "persists status", "change": 0, "d": 1 }]
      }
    ]
  },
  "impact_visual": {
    "audiences": ["Members"],
    "groups": [["code", "Changes in code"]],
    "cards": [
      {
        "g": "code",
        "row": 0,
        "title": "New term Suspended",
        "after": "Suspended",
        "who": ["Members"],
        "where": "app/models/subscription.rb",
        "why": "Access is revoked on a failed charge.",
        "proof": "AC 1, 3"
      }
    ]
  },
  "landing_visual": {
    "doors": [
      {
        "n": 1,
        "title": "Suspended status",
        "decide": "How is a suspended subscription stored?",
        "choice": "`suspended` enum value",
        "hard": "Every reader of `status` depends on the value.",
        "alternatives": [["`is_suspended` boolean", "cannot express the next state"]],
        "proof": "AC 1"
      }
    ]
  }
}
```
