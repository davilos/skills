---
name: local-judge
description: Evidence-first code review of the current git branch before any PR exists, diffed against its base (origin/main by default) with uncommitted and untracked files included. Runs the repo's checks, researches official docs, and reviews correctness, security, structure, AI slop, commit-message claims and bypasses, and, given a spec (plan, PRD, issue), checks each requirement it states was implemented; every finding needs file:line or URL evidence and passes a deterministic gate, a per-branch ledger makes re-runs verify fixes, and it applies the fixes you pick. Use when there is no PR yet and the user says review my code, review my branch before I open the PR, review my local changes, run local-judge, "revise meu código", "revise minha branch antes do PR", "julgue minhas mudanças", "code review local", "check my branch against the plan", "revise contra a spec". Do NOT use for an already open GitHub PR (use the-judge), running a tlc-spec-lean Verifier (proofs, mutations), reviewing prose, or fixing CI.
license: CC-BY-4.0
metadata:
  author: Dávilos Tavares - github.com/davilos (adapted from the-judge by Felipe Rodrigues - github.com/felipfr)
  version: 1.1.0
---

# Local Judge

Review the current branch like a senior engineer with a high conviction bar, before it becomes a PR: few findings, every one backed by evidence, delivered as one gated report, then the fixes the user picks. Given a spec, the review also answers "did this branch build what the spec asked for", requirement by requirement. This is the-judge with local inputs and outputs: the diff comes from git, not GitHub, and the review lands in a report and a ledger instead of a posted review.

`<skill-dir>` below is the base directory this skill was loaded from. Every script is stdlib Python and writes only under `<git-dir>/local-judge/<branch>/` (the "workdir"), so nothing it produces can be committed by accident.

## Non-Negotiables

These rules override everything else in this skill.

1. **Evidence or silence.** An internal claim requires a `path:line` you confirmed by reading the file. An external claim (library, API, framework, version, deprecation, advisory, best practice) requires an https URL from an official source fetched during this review. A finding without evidence is not reported.
2. **Never assert external behavior from memory.** Search current official docs, changelogs or advisories first. Inconclusive research downgrades the finding to a question or kills it.
3. **Noise budget.** At most 5 nits; overflow becomes a count in the summary. Prefer three findings that matter over fifteen observations.
4. **Never report what the repo's own tooling catches.** Step 1 runs it first; anything it flags is out of scope.
5. **Every report passes the gate.** `review_gate.py` exits 0 before anything is recorded, and `ledger.py record` refuses otherwise.
6. **Language follows the user.** A language named at invocation wins; otherwise write in the language of the message that invoked the review, natively, with full diacritics. Verdict tokens (READY, NEEDS_WORK, BLOCKED), identifiers, quoted strings and tool output stay verbatim.
7. **Spend tokens where judgment lives.** Read the diff, the files it touches, and direct callers or callees only when tracing a finding needs them. Regex-detectable patterns go through `scan_bypasses.py`, not prose.
8. **The first review is the whole review.** Everything visible in round 1 is raised in round 1. Later rounds verify resolution and look only for new blockers (Convergence Contract).
9. **Read-only until the user picks fixes.** No edits before Step 8. Never stage, commit, push, fetch, checkout or stash anything; the user owns git.

## Severity and Verdict

| Severity | Emoji | Definition | Verdict effect |
|---|---|---|---|
| blocker | 🔴 | Must not reach a PR as is: data loss, exploitable security, incorrect money, broken auth, irreversible migration, PII in logs | BLOCKED |
| should-fix | 🟠 | Real defect, not a merge risk | NEEDS_WORK |
| nit | 🟡 | Minor. Capped at 5 | none |
| pre-existing | 🟣 | Bug this branch did not introduce. Reported, never counted | none |

Verdict: any 🔴 (new or still open from a previous round) is BLOCKED; otherwise any 🟠 is NEEDS_WORK; otherwise READY. The gate recomputes it.

## Workflow

### Step 0: Resolve what is under review

Work from the repo or worktree the user means. If the current directory is not inside a git repo (for example a workspace folder that holds several repos) and the user did not name one, ask which repo or worktree before going further.

```bash
python3 <skill-dir>/scripts/collect_diff.py --repo <repo-or-worktree> [--base <ref>] [--fresh] [--spec <file> [--spec-section <regex>]]
```

It prints `meta.json` (also saved in the workdir): `branch`, `head`, `dirty`, `base`, `merge_base`, `commits`, `files` (with `mechanical_hint`), `branch_patch` (merge-base vs working tree, untracked files as new), `round`, `previous_open`, `next_finding_id`, and on round 2+ `since_patch` (last reviewed snapshot vs working tree). Default base is the first of `origin/main`, `main`, `origin/master`, `master` that exists; when the user says the branch came from another branch (`staging`, a feature branch), pass `--base`. It never fetches, so state the base commit in the report. `--fresh` moves the ledger and reports into `archive-<timestamp>/` and restarts at round 1; use it only when the user asks or the branch was rewritten so the old findings no longer map.

Pass `--spec` when the user names a spec, or when the repo's instructions say where the branch's spec lives (for example a plan found by branch name). It runs `scripts/extract_requirements.py`, writes `<workdir>/requirements.json` (one entry per requirement: `id`, spec `line`, `text`, `heading`) and adds `spec` to `meta.json`. Requirements are numbered or checkbox items under a criteria label (Acceptance Criteria, Requirements, Critérios, Critérios de aceite or de aceitação, Requisitos; as a heading or a bold label) and any list item with SHALL, MUST or DEVE; indented bullets are examples of the item above. `--spec-section` keeps only requirements whose heading chain matches the regex, for a spec that covers other repos or slices (`'\[api\]'`). Round 2+ reuses the last round's spec when `--spec` is omitted. When `count` is 0, read the spec and write `requirements.json` by hand in the same shape, one entry per testable requirement, `line` pointing at the spec; the next rounds keep it.

Then:
- Empty `files`: say there is nothing to review against that base and stop.
- Classify each file as **core** or **mechanical** (lockfiles, generated schema or types, snapshots, build output, auto-generated migrations). `mechanical_hint` is a hint: a hand-written data migration is core. Mechanical files are listed in the summary and skipped.
- Moved code (3+ identical lines deleted in one place and added elsewhere) is a move, not new code.
- `round` 2+: follow the Convergence Contract instead of a full re-run.
- Over roughly 400 changed core lines with subagents available: run the Step 3 passes as parallel subagents, each given the patch path, the file list and `references/review-standards.md`. Otherwise run them sequentially.

### Step 1: Deterministic ladder

Find and run the repo's own lint, typecheck and tests focused on the changed files (`package.json` scripts, `Makefile`, `pyproject.toml`, CI config, the repo's agent instructions). Record exact results. Do not install anything; missing tooling is noted in the summary.

Some repos forbid running certain commands without confirmation (for example tests that load a real `.env`). Follow those rules: ask with the exact command and directory, and if the user declines, record "not run, declined" in Checks run and continue. Read-only linters and typecheckers usually need no confirmation; check the repo's rules anyway.

Then scan for bypass markers:

```bash
python3 <skill-dir>/scripts/scan_bypasses.py < <branch_patch>
```

Hits are Pass F candidates, not findings.

### Step 2: Mandatory research

List every external surface the branch touches: dependencies added or bumped (manifest and lockfile diff), APIs called, framework features, version-sensitive language features. Search official docs, release notes and advisories for each and log every URL with the claim it supports or refutes. No external surfaces: say so in the research log. This step is never skipped because you feel sure.

### Step 3: Review passes

**Read `references/review-standards.md` now.** Run six passes over the core files: A correctness, B security, C structure, D AI slop and useless comments, E commit-message claims, F bypasses, duplication and gambiarras. With `meta.spec`, also run Pass G, spec conformance, over every entry of `requirements.json`. Round 1 covers every core file in depth. Withhold nits inside a block that a 🔴 or 🟠 asks to restructure, and say so in the summary.

### Step 4: Verification

Re-read the code at every candidate's location and confirm the claim holds; re-apply the exclusion lists; deduplicate; assign severity conservatively (an uncertain blocker is a should-fix phrased as a question). Reproduce a 🔴 from Pass A or B with a test or short script inside the repo's own harness when feasible and record it as `repro` evidence; a feasible repro that fails kills the finding. Kill for lack of evidence, downgrade for lack of impact, never conflate the two.

### Step 5: Write findings.json

**Read `references/comment-voice.md` now.** Write `<workdir>/findings.json`:

```json
{
  "language": "pt-BR",
  "round": 1,
  "verdict": "NEEDS_WORK",
  "summary": "## TL;DR\n...\n## Findings\n...\n## Promote to lint rule\n...\n## Research log\n...\n## Checks run\n...\n## Skipped files\n...",
  "findings": [
    {
      "id": "F1",
      "title": "applyDiscount divide por zero com carrinho vazio",
      "path": "src/billing/invoice.ts",
      "line": 142,
      "severity": "should-fix",
      "body": "🟠 `applyDiscount` divide por `items.length` sem guarda para lista vazia (src/billing/invoice.ts:142). ...",
      "evidence": [{"type": "internal", "ref": "src/billing/invoice.ts:142"}]
    }
  ],
  "resolution": [],
  "spec_coverage": [
    {"id": "AC1", "status": "implemented", "evidence": [{"type": "internal", "ref": "src/billing/invoice.ts:120"}]},
    {"id": "AC2", "status": "missing", "severity": "should-fix", "note": "nenhum caminho devolve 409 sem instância configurada"}
  ]
}
```

Rules the gate enforces, so write to them from the start: `round` equals `meta.json`'s; new ids start at `next_finding_id` and never reuse an old one; `title` is one line up to 100 chars; `path` is relative to the repo root and `line` is the line in the working-tree file; blocker, should-fix and nit must sit on a file changed by this branch (otherwise it is pre-existing); blocker and should-fix need evidence; internal evidence must point at an existing line; body starts with the severity emoji; the summary has a TL;DR containing the verdict token and a lint-rule section. In round 2+, `resolution` maps every id in `previous_open` to `resolved`, `open` or `declined-accepted` (with the reason in `note`), and `findings` holds new blockers only.

With `meta.spec`, `spec_coverage` has exactly one row per id in `requirements.json`, every round: `status` is `implemented`, `partial`, `missing`, `contradicted` or `not-applicable`; `implemented`, `partial` and `contradicted` carry internal evidence on an existing line (any file of the repo, changed or not); every status other than `implemented` carries a `note`; `partial`, `missing` and `contradicted` carry `severity` `blocker` or `should-fix`, which weighs on the verdict like a finding; the summary has a Spec coverage section. A gap is a row, not a finding, so it needs no anchor on a changed file. Code that no requirement asked for is an ordinary finding (🟡 by default) on the changed line.

### Step 6: Gate

```bash
python3 <skill-dir>/scripts/review_gate.py <workdir>/findings.json --meta <workdir>/meta.json
```

Fix every violation and re-run until exit 0. When a banned pattern keeps failing, delete the sentence instead of rephrasing around it.

### Step 7: Record and report

```bash
python3 <skill-dir>/scripts/ledger.py record <workdir>/findings.json --meta <workdir>/meta.json
```

It re-runs the gate, stores the round (with a snapshot of the working tree for the next round's `since_patch`) and writes `<workdir>/round-N.md`. Tool output is not shown to the user, so put the report in your reply: the header (branch, head, base and merge-base, round, verdict), the TL;DR, the findings table with clickable `path:line`, the full body of every 🔴 and 🟠, and the path of `round-N.md`.

### Step 8: Offer the fixes

Ask which findings to apply (all, a list of ids, or none). For each one chosen:
1. Apply the laziest fix that works, as the finding describes; behavior stays the same except for the defect fixed.
2. Re-run the Step 1 checks covering the touched files (same confirmation rules).
3. After all of them: `python3 <skill-dir>/scripts/ledger.py mark --meta <workdir>/meta.json --status fixed-locally F1 F3`.

Do not stage or commit. A fix that turns out wrong or larger than the finding said is reported, not forced. Close by suggesting a re-run of local-judge, which becomes round 2 and verifies the fixes.

## Summary Body Template

```markdown
## TL;DR
One to three sentences: what the branch does and the verdict with its reason. Contains READY, NEEDS_WORK or BLOCKED verbatim.

## Findings
| ID | Severity | Location | Summary |
|---|---|---|---|

## Resolution (round 2+)
| ID | Status | Note |
|---|---|---|

## Spec coverage (only with --spec)
Spec path, then counts per status and one line per row that is not implemented: id, status, what is missing or wrong. ledger.py appends the full per-requirement table to round-N.md.

## Promote to lint rule
Deterministic findings (banned pattern, naming rule) with a one-line sketch of the lint rule each one needs. "none" if empty.

## Research log
URLs consulted in Step 2 with the claim each supports or refutes. "no external surfaces touched" if none.

## Checks run
Step 1 results, verbatim numbers: tests passed/failed/skipped, lint and typecheck outcome, bypass scan candidates, commands not run and why.

## Skipped files
Mechanical files excluded.

## Nit overflow
"N additional nits not reported individually". Omit when under the cap.
```

## Convergence Contract

Round 1 is exhaustive; every later round shrinks.

Round N (N >= 2) does exactly two things:
1. **Resolution check.** For every id in `previous_open`, look at the current code: `resolved` (say what changed), `open`, or `declined-accepted` when the user gave a reason that holds on code-health grounds. `fixed-locally` in the ledger only means a fix was applied; it still has to be verified here.
2. **New blockers only.** Read `since_patch` solely for 🔴 introduced since the last round. No new 🟠, 🟡 or 🟣. Code visible in round 1 and not flagged then is forfeited; the single exception is a genuine 🔴 discovered late, labeled as missed in round 1.

With a spec, `spec_coverage` is re-emitted in full. Re-examine the rows that were not `implemented` in the last round (the ledger keeps them in `spec_gaps`) and the rows whose evidence lines `since_patch` touches; carry the other rows over with their evidence. A row that turns from `implemented` into a gap is a regression introduced since the last round and follows the new-blockers rule: report it only as `blocker`, otherwise keep it `implemented`. The gate enforces this from `meta.spec.previous_gaps` (the last round's gaps, `null` when the spec path or section changed, which makes every row new).

A declined finding is re-argued at most once with new evidence; after that it stays `open` and is not raised again. By round 3 every open finding is fixed, accepted as a follow-up by the user, or left open by explicit decision. Approve (READY) as soon as the branch improves code health; open nits never block READY.

## Examples

### Example 1: first review before the PR

User says: "revise minha branch antes de eu abrir o PR" inside `api-celer/.claude/worktrees/prospeccao-robo`.
Actions: collect_diff with the default `origin/main` base, round 1, 9 core files and 1 auto migration skipped. Ruff and the typecheck run; pytest needs a real `.env` under the repo rules, so the command is asked first. Scan finds one naked `# noqa`. Research checks one bumped dependency's changelog. One 🟠 and two 🟡 survive verification; the gate fails once on "vale ressaltar" and passes on the next run. Report in Portuguese with verdict NEEDS_WORK, then the fix question.
Result: the user picks F1 and F2; both are applied, ruff re-runs clean, the ledger marks them fixed-locally, and the reply suggests a re-run.

### Example 2: re-run after fixes

User says: "judge it again".
Actions: collect_diff reports round 2 with F1 and F2 fixed-locally and F3 open. The resolution check finds F1 resolved, F2 still dividing by zero on one path (stays open), and the user declined F3 with a reason that holds. `since_patch` holds no new blockers. `findings` is empty and the verdict is NEEDS_WORK because F2 is a should-fix still open.
Result: a short report with the Resolution table only.

### Example 3: branch cut from another branch

User says: "review my local changes, this branch came off staging".
Actions: collect_diff with `--base origin/staging`; the header states the base and merge-base so the user can see what was compared.
Result: a review of only this branch's work, without staging's commits mixed in.

### Example 4: review against the plan

User says: "revise minha branch e veja se o plan foi implementado" in an api worktree whose feature plan has `[api]` and `[front]` slices.
Actions: collect_diff with `--spec <path>/plan.md --spec-section '\[api\]'`; 12 requirements extracted as AC1..AC12. Pass G finds AC1 to AC10 implemented with `path:line`, AC11 missing (the 409 path does not exist, should-fix) and AC12 not-applicable (needs the front, note says so). One 🟡 flags a retry loop no requirement asked for. The gate passes with NEEDS_WORK because of AC11.
Result: the report lists the gap with the spec line, round-1.md carries the full coverage table, and the fix question includes AC11.

## Troubleshooting

### `spec: no requirements recognized`
Cause: the spec has no criteria label and no list item with SHALL, MUST or DEVE (a prose PRD, an issue body).
Solution: read the spec and write `<workdir>/requirements.json` by hand (`id`, `line`, `text`, `heading` per requirement), then continue; the gate refuses an empty list.

### Gate says a requirement has no spec_coverage row
Cause: a requirement was skipped, or `--spec-section` was too broad.
Solution: add the row; if the requirement belongs to another repo or slice, mark it `not-applicable` with the reason, or re-run collect_diff with a narrower `--spec-section`.

### `base ref not found`
Cause: no `origin/main`, `main`, `origin/master` or `master`, or a wrong `--base`.
Solution: ask the user which branch this one came from and pass `--base <ref>`. Do not fetch.

### `not a git repository`
Cause: running from a folder that holds several repos.
Solution: ask which repo or worktree and pass `--repo`.

### `round N already recorded`
Cause: `ledger.py record` ran twice without a new collect_diff.
Solution: run collect_diff again; it computes the next round.

### Gate says a path is not changed on this branch
Cause: the finding sits on a file the branch did not touch.
Solution: anchor it on the changed caller that exposes it, or make it 🟣 pre-existing.

### Findings no longer match the code after a rebase
Cause: the branch history was rewritten since the last round.
Solution: tell the user, and with their agreement re-run collect_diff with `--fresh`.
