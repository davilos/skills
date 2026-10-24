# review-page.json

Lives at `.specs/features/{slug}/review-page.json`. It holds what the page needs and `plan.md` does not have. Every field is optional unless stated; without `problem_visual`, `flow_visual` or `impact_visual`, the matching section shows only the plan text.

Text with backticks (`` `x` ``) and `**bold**` renders as code and bold in fields marked _(md)_; other fields render as written. Write prose fields (`why`, `today`, `decide`, `hard`...) in the language the plan's reviewers read.

Proof fields (`changes[].proof`, `impact_visual.cards[].proof`, `problem_visual.symptoms[].fix.proof`, `landing_visual.doors[].proof`) become links: in `AC 10 to 12`, `AC 1–3`, `AC 10, 12` or `AC 5 and 6`, every number written links to its criterion (`#ac-N`), so list a criterion explicitly when it needs its own link; `door N` to the One-way door (`#door-N`); `S5` to the slice (`#slice-S5`). Every criterion cited after `AC` must exist in the plan; the build rejects otherwise and the check rejects a link with no target.

## Contents

- Header and review
- Changes (Criteria)
- problem_visual
- flow_visual
- landing_visual
- impact_visual
- Minimal example

## Header and review

| Field                    | Type              | What it is                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| ------------------------ | ----------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `title`                  | string            | tab and artifact name (2 to 4 words, stable across publishes)                                                                                                                                                                                                                                                                                                                                                                                             |
| `artifact_url`           | string            | the artifact link; empty the first time                                                                                                                                                                                                                                                                                                                                                                                                                   |
| `plan_path`              | string            | plan path, shown at the top and in the footer                                                                                                                                                                                                                                                                                                                                                                                                             |
| `published_plan_hash`    | string            | written by `build_page.py --mark-published`: hash of the plan.md last published; do not edit by hand                                                                                                                                                                                                                                                                                                                                                      |
| `published_at`           | string            | written with it: when it was published                                                                                                                                                                                                                                                                                                                                                                                                                    |
| `published_fingerprints` | `{key: hash}`     | written with it: fingerprint of each section, slice (`S1`), door (`door:1`) and derived item (`impact:N`, `flow:N`, `change:N`, `symptom:N`, `problem-visual`) at publish time; the build compares against it to flag what changed since. Do not edit by hand                                                                                                                                                                                             |
| `review_fingerprints`    | `{key: hash}`     | fingerprint of the text the user validated for each validated section, slice and door; the build compares against it to show "validated · changed since". `--mark-published` writes it for keys that have none yet (the current text counts) and never recomputes the others; `sync_review.py` writes the one from a validation made on the page. When you mark a validation by hand in `review`, do not create the key: the next `--mark-published` does |
| `code_ref`               | string            | repo, branch and commit read for the Where (e.g. `billing-api feat/dunning @ f75a388c9`)                                                                                                                                                                                                                                                                                                                                                                  |
| `tags`                   | `[{text, warn?}]` | top-of-page tags; `warn: true` paints it amber (use it for "plan in review")                                                                                                                                                                                                                                                                                                                                                                              |
| `review`                 | `{id: bool}`      | review state when the page has no db (outside claude.ai) or the item was not marked on it yet; what the user marks on the page (db `review/{key}`) wins, and `sync_review.py` brings it back here. Section ids: `problem`, `flow`, `impact`, `relations`, `surface`, `landing`, `criteria`, `out`, `assumptions`, `questions`, `observable`, `sources`; slice ids: `S1`, `S2`... Missing = "not reviewed"                                                 |
| `doors_confirmed`        | `[int]`           | numbers of the one-way doors the user confirmed                                                                                                                                                                                                                                                                                                                                                                                                           |

Doors are numbered by their row in the `## Landing` table (first row = door 1), the same numbering the plan uses in "(door N)". A first cell written as `1. name` also works.

## Changes (Criteria)

`changes`: a list; each item becomes a clickable row under its slice.

| Field   | Required | What it is                                                                                                                           |
| ------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `s`     | yes      | slice id (`S1`...)                                                                                                                   |
| `neu`   | yes      | the new name or state                                                                                                                |
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

## problem_visual

| Field             | What it is                                                                                                                                         |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `symptoms`        | `[{what, today (md), where, fix, pays}]`: what is wrong today; the open card shows Where (`where`), Today (`today`), Fixed in (`fix`) and Who pays |
| `symptoms[].fix`  | `{slice, proof, door?, text? (md)}`: the slice (link) and the criteria that fix the symptom; slice and criteria must exist in the plan             |
| `symptoms[].pays` | `[int]`: indexes into `pays` this symptom hits                                                                                                     |
| `pays`            | `[string (md)]`: who pays; becomes a filter that highlights the linked symptoms (the build warns if one highlights none)                           |
| `why_now`         | string (md)                                                                                                                                        |
| `outcome`         | string (md): what changes once it ships                                                                                                            |

## flow_visual

`paths`: `[{title, when, hop, nodes}]`. `hop` = the number of the `## Flow` item the path represents (every hop in the plan needs at least one path; two paths may share a hop).

Each node: `{k, n, o?, d?, note?, change?, tbd?, shared?}`: `k` = kind (job, task, module, client, config, metric, webhook, output), `n` = new name, `o` = today's name, `d` = door, `note` = what changes when the name does not, `change` = index into `changes` whose Where / Why / Proof the click opens. `tbd: true` = the plan does not fix the name yet: `n` carries a description, and the node shows "not defined". `shared: true` = this node deliberately opens the same change as another, different node (same Where / Why / Proof); without it, the build warns. A node with `o` or `note` is green; without `change` it is not clickable (the build warns).

**One card per node:** when the same node (same `n`) appears in more than one path, only the first occurrence, in `paths` order, carries `change`; the others keep `o`/`d`/`note` (still green) and have no `change`. Every copy opens the same card (the page takes the `change` from the occurrence that has it); while it is open, the page highlights the other copies and dims every other node. The build rejects the same `n` with `change` twice. Different nodes point to the same `change` only when Where / Why / Proof really are the same (e.g. modules of the same renamed package that change in the same place). If each node touches different lines or is proven by different criteria (e.g. the email counter and the SMS counter), each gets its own entry in `changes`.

## landing_visual

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
| `risk`         | what happens on deploy (from the Impact)                          |
| `alternatives` | `[[option, why not]]`, taken from Alternative rejected            |
| `proof`        | criteria that guarantee it, e.g. `AC 10 to 12, 15` (become links) |

Nothing here is a new decision: everything comes from the plan's Landing, Impact and criteria.

## impact_visual

| Field       | What it is                                                                                                                                                    |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `audiences` | `[string]`: who feels it (filter)                                                                                                                             |
| `groups`    | `[[id, label]]`, e.g. `[["code","Changes in code"],["ops","Changes in operations"],["same","Does not change"]]`; `code`/`ops`/`same` have their own colour    |
| `cards`     | see below; **every row of the `## Impact` table needs at least one card**                                                                                     |
| `keep`      | `[[names, reason]]`: a list opened on the card with `keep: true`; several names in `names` are separated by `·` (each one becomes code, always the full name) |
| `tree`      | `{before: [[text, class, note]], after: [...]}`: a file tree opened on the card with `tree: true`; class `del`, `add` or `""`                                 |

Card: `{g, row, title, before?, after?, tbd?, who, risk?, where, why, proof, keep?, tree?}`. `tbd: true` = the name in `after` is not fixed in the plan yet: `after` carries the description, and the card shows "not defined". `row` = 0-based index of the Impact table row; its text appears in the open card. `where` (Where), `why` (Why) and `proof` (Proof) are required; on a card with `keep: true` Where is optional (the list is the content; do not write "the list below").

## Minimal example

For a plan with one slice, one Flow hop, one Impact row and one door:

```json
{
  "title": "Dunning plan review",
  "artifact_url": "",
  "plan_path": ".specs/features/dunning/plan.md",
  "tags": [{ "text": "plan in review", "warn": true }],
  "changes": [
    {
      "s": "S1",
      "old": "`Active` = has a row",
      "neu": "`Suspended` in `subscriptions.status`",
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
