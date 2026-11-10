# UI preview

Only for tlc-spec-lean plans. A second page, its own artifact, with before/after mockups of every screen the plan changes, a numbered highlight on each change and, next to it, the slice and criteria that require it. It helps people who review by looking. It is **opt-in** because it costs more: on a small React plan (two screens, 4 to 7 changes), building it after the review page added about 13k tokens (+21%) and doubled the time (1 to 2 minutes), measured over 2 runs each. It grows with the number and size of the screens drawn.

## When and how

1. **Detect.** `python3 {skill-dir}/scripts/build_preview.py {plan} --detect` prints `ui: yes` when the plan cites front-end files (components, pages, templates, styles) **and** has criteria about what the user sees (text, position, state, a new screen), listing both; `ui: code-only` when it cites the files but no criterion changes the screen (a hook, a renamed CSS variable); `ui: no` otherwise. The criteria match on words, so read the ones listed: if none really changes the screen, treat it as `code-only`.
2. **Offer once.** On `ui: yes`, if the review state has no `"ui_preview": false` and there is no `ui-preview.json` yet, ask in one line after telling the user about the review page, with the cost: "This plan changes {screens}. Want a before/after preview of them? It adds about 20% to the tokens of this review, more for many or large screens." Count the screens from the visible criteria (a dialog counts as one; its loading, error or empty versions are states of that screen, not more screens). **Above 3 screens, offer the main ones and name the rest**; the user may still ask for all. On no, write `"ui_preview": false` in the review state and do not ask again for this plan. Build it straight away when the user asked for it up front ("with a UI preview", "show how the screen will look"). On `ui: code-only` or `ui: no` say nothing, unless the user asks.
3. **Draw.** Before comes from the code (real labels, real style values); After is Before plus only what the plan states; each screen opens with a `summary` of what changes on it; every change is a mark with its kind, slice and criteria; a criterion with nothing to draw is a `same` or `effect` mark; what the plan does not fix is `tbd`. The fields and rules are below.
4. **Build.** `python3 {skill-dir}/scripts/build_preview.py {plan} --out {tmp}/{slug}-ui.html`. Exit 1 means a mark misstates the plan or the mockup (slice or criterion that does not exist, mark without an element in one of its states, highlight without a mark, state that does not exist, script or external URL in a fragment); fix ui-preview.json or the fragment.
5. **Publish** like the review page, but without capabilities (the preview has no buttons): new artifact with `icon: "layout"`; then `build_preview.py {plan} --mark-published --url {link}` (the `--url` only the first time); republish to the same `url` afterwards. Build and republish the review page too, so its "UI preview ↗" link appears. Without the `Artifact` tool, give the path of the HTML file.
6. **Tell the user** the link, how many screens and marks, which marks are "not defined", and that the mockups are a reading of the code and the plan, not screenshots.

When the plan changes later, rebuild the preview with the review page: `RECHECK mark:{screen}:{n}` means the slice or criteria behind that mark changed; redraw it before republishing.

**Example.** After the review page, `--detect` printed `ui: yes` with `PlanCard.tsx`, `BillingPage.tsx` and the criteria about the meter, the header and the new card; the user answered "yes, show me". Actions: read both components and `billing.css` → write `billing.before.html` from the code → write `billing.after.html` as the same markup with only the meter and the moved button changed → `ui-preview.json` with two marks (S1 / AC 1, 2 and S2 / AC 4) → `build_preview.py` → publish with `icon: "layout"` → `--mark-published --url` → rebuild and republish the review page. Result: "UI preview: {link}. 1 screen, 2 changes; the Danger zone text is not in the plan, marked not defined. The mockups are my reading of the code, not screenshots."

**Troubleshooting.**
- **`ERROR ... no element in the mockup has data-mark="N"`**: put `data-mark="N"` on the element that changes (on a wrapper for `input` or `img`).
- **`ERROR ... no element in the mockup of state 'x'`**: list only the states where the mark appears in `states`, or put the element in that state's fragment.
- **`ERROR ... has a <script>` / `an external or javascript: URL`**: fragments are static and offline; draw the state instead of scripting it, and replace external images with a `.ph` block.
- **`WARN ... has N KB`**: the fragment draws more than the change; turn unchanged parts into `.ph` placeholders.

Optional. A separate page with before/after mockups of the screens a front-end plan changes, so reviewers see the change instead of imagining it from `PlanCard.tsx:9-21`. It is a reading of the code and the plan, like Where / Why / Proof: never the plan, never a screenshot.

## Contents

- Files
- ui-preview.json
- Fragments
- Drawing faithfully
- Spending few tokens
- Minimal example

## Files

```
.specs/features/{slug}/
├── ui-preview.json          # screens, marks, artifact link
└── ui-preview/
    ├── billing.css          # styles shared by every fragment of a screen (optional)
    ├── billing.before.html  # the screen today
    └── billing.after.html   # the screen with the plan
```

`build_preview.py` reads them and writes one self-contained HTML; `build_page.py` reads `artifact_url` from `ui-preview.json` and puts a "UI preview ↗" link at the top of the review page.

## ui-preview.json

| Field                    | What it is                                                                                                                          |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------------------------- |
| `title`                  | artifact name, 2 to 4 words, stable across publishes (default: plan title + "UI preview")                                         |
| `artifact_url`           | the preview's artifact link; empty the first time                                                                                   |
| `review_url`             | where slice and criterion links go; leave it out to use `artifact_url` from spec-review.json                                       |
| `code_ref`               | repo, branch and commit read for the Before (e.g. `web feat/usage @ 1a2b3c4`)                                                       |
| `screens`                | list, one per screen (or dialog), in the order a user meets them; its loading, error or empty versions are `states`, not screens   |
| `published_*`            | written by `--mark-published`; do not edit by hand                                                                                  |

Screen: `{id, name, route?, summary?, where, before?, after?, css?, width?, states?, marks}`.

| Field    | What it is                                                                                                                       |
| -------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `id`     | kebab-case, unique; becomes the anchor `#screen-{id}`                                                                            |
| `name`   | what the user calls the screen ("Billing", "Cancel confirmation")                                                                |
| `route`  | URL or how to reach it ("/settings/billing (dialog)")                                                                            |
| `summary` | one or two sentences (md) on what changes on this screen as a whole, read before the mockups and the marks                      |
| `where`  | files the Before was drawn from, same format as spec-review.json: `file[:lines]` or `folder/`, separated by `·`, no prose         |
| `before` | fragment file of the screen today; leave it out for a screen the plan creates                                                    |
| `after`  | fragment file of the screen with the plan; leave it out for a screen the plan removes                                             |
| `css`    | a stylesheet both fragments load, so the styles are written once                                                                 |
| `width`  | the width the mockup is drawn at, in px (default 1280; 390 for a phone screen); the page scales it to fit                        |
| `states` | versions of the screen the reviewer switches between: `[{id, label, before?, after?}]`; see States below                        |
| `marks`  | what changes, numbered: `[{n, kind?, text (md), s, proof, where?, tbd?, states?}]`                                               |

Mark: `n` = 1, 2, 3... and the element that changes carries `data-mark="n"` in the fragment (in `after` for what arrives or changes, in `before` too for what leaves or moves). `kind` = `add` (green), `change` (amber) or `remove` (red, dashed): the highlight keeps that colour on both sides; without `kind` it is red in Before and green in After. `same` and `effect` are criteria with nothing to draw: the screen stays as today (`same`), or the criterion acts elsewhere, like the request a save sends (`effect`); they have no `n` and no element, and the page lists them under "No change to draw". `text` = what the reviewer should notice, in one sentence; `s` = slice; `proof` = criteria, as in spec-review.json (`AC 1, 2`); `where` = where it lands in code, when the plan says; `tbd: true` = the plan does not fix this detail (copy, exact position, colour), the mockup shows a neutral placeholder or a plausible guess, and the page says "not defined"; `states` = the ids of the states the mark holds in (leave it out when it holds in all).

### States

When a criterion is about a state of the screen (loading, error, empty, disabled, a toggle on or off), give the screen `states` instead of a new screen per state. The page shows them as tabs next to Before / After. A state takes only the fragments that differ: without `before` or `after` it uses the screen's, and `"before": null` means the state does not exist today.

```json
"before": "cancel.before.html", "after": "cancel.after.html",
"states": [
  { "id": "default", "label": "Default" },
  { "id": "error", "label": "Refund fails", "before": null, "after": "cancel-error.after.html" }
],
"marks": [
  { "n": 1, "text": "Refund amount above the button", "s": "S2", "proof": "AC 5" },
  { "n": 2, "text": "Error with the reason and \"Try again\"", "s": "S2", "proof": "AC 7", "states": ["error"] }
]
```

Marks of other states stay in the list, dimmed; a click on one switches to its state. An animation or a sequence (click, animating, open, closed) is a set of states too, one per moment that matters.

The build rejects: a slice or criterion the plan does not have, an unknown `kind`, a `same` or `effect` mark with a number, a mark with no element in a state it holds in, an element `data-mark` with no mark holding in that state, a mark naming a state the screen does not have, a Where with prose, a missing fragment, and a fragment with a script, an event handler, an iframe/link/meta, or any external URL.

## Fragments

- The `<body>` content of the screen, plus `<style>` if needed. No `<html>`, no scripts, no external images, fonts or stylesheets: the page is offline and the frame runs no code.
- Every frame gets a neutral base (system font, white background) and two placeholder classes for context that does not change: `.ph` (a grey block; give it a height and width inline) and `.ph-line` (a line of text; `.ph-line.short` is 40% wide).
- Put `data-mark` on an element that can hold a badge (a `div`, `section`, `button`), not on `input` or `img`: wrap those.
- **A change only in copy:** mark the element as usual and wrap the words that differ: `<del>` around what goes out in `before`, `<ins>` around what comes in in `after` (`… acompanha "Quantidade por via" <del>da configuração do e-mail</del>` / `<ins>das configurações gerais</ins>`). The page strikes and highlights them; with highlights off they read as plain text.
- Static states only. If the change is a state (disabled, error, empty, loading), draw that state; if more than one state matters, add them to the screen's `states`.

## Drawing faithfully

- **Before comes from the code**, not from memory: read the component, the page that mounts it and the styles it uses. Copy the real labels and copy text, the real colour and spacing values (from the CSS, tokens or theme file), the real order of elements. Data is representative: take the plan's examples when it has them (its Independent test, its criteria), otherwise plausible values.
- **After is Before plus what the plan states, and nothing else.** No restyling, no extra improvement, no element the plan does not ask for. Each change is a mark tied to the slice and criteria that require it; a change without a criterion behind it does not belong in the mockup.
- **What the plan does not fix is "not defined".** If the plan says "a Danger zone card" but not its text, draw the card with a neutral or plausible sentence and mark it `tbd: true`; never present an invented copy or name as decided. A name the plan leaves open (`tbd` in spec-review.json) is `tbd` here too.
- **Tell the user what is not plan**: the Before is your reading of the code, the After is your reading of the plan.

## Spending few tokens

The mockup is the expensive part of this skill: every line is output. Keep it to what the reviewer needs to see the change.

- **Draw the region that changes in detail; the rest as placeholders.** Header, navigation, cards that do not change: a `.ph` block or a title over two `.ph-line`. A changed card on a long page does not need the whole page.
- **After is the Before markup with only the changes.** Start from the Before you just wrote and change only what the plan changes, so the two differ exactly where the marks are. For a small fragment (a few KB), write After in one go: copying and editing costs an extra read of the file before the edit. Copy (`cp`) and edit only when the fragment is large and the change is small.
- **Styles once per screen** in `css`, shared by every fragment of the screen; inline `style` only for one-offs.
- **A state takes only what differs.** A state whose Before is the screen's Before leaves `before` out instead of copying the file.
- **Read only the files of the screens you draw**: the component, its parent and its styles. The Where of the review page usually already points there.
- `build_preview.py` warns above 30 KB per fragment: that size means it draws more than the change.

## Minimal example

```json
{
  "title": "Billing usage preview",
  "artifact_url": "",
  "code_ref": "acme-web main @ 1a2b3c4",
  "screens": [
    {
      "id": "billing",
      "name": "Billing",
      "route": "/settings/billing",
      "where": "src/pages/BillingPage.tsx:17-31 · src/components/PlanCard.tsx:9-21",
      "before": "billing.before.html",
      "after": "billing.after.html",
      "css": "billing.css",
      "width": 1100,
      "marks": [
        { "n": 1, "kind": "add", "text": "Usage meter under the plan name, amber at 80%", "s": "S1", "proof": "AC 1, 2" },
        { "n": 2, "kind": "change", "text": "Header keeps only \"Change plan\"", "s": "S2", "proof": "AC 4", "where": "src/pages/BillingPage.tsx:17-26" }
      ]
    }
  ]
}
```

`billing.after.html` (Before was the same with a "Cancel subscription" button carrying `data-mark="2"` and no meter):

```html
<div class="billing">
  <header class="billing-header"><h1>Billing</h1><button class="btn btn-primary" data-mark="2">Change plan</button></header>
  <section class="card">
    <h2>Current plan</h2>
    <div class="plan-name">Team</div>
    <div class="meter" data-mark="1"><div class="meter-bar"><span style="width:80%"></span></div>8 of 10 seats used</div>
  </section>
  <section class="card"><h2>Invoices</h2><div class="ph-line"></div><div class="ph-line short"></div></section>
</div>
```
