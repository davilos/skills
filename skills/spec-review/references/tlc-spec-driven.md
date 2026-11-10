# tlc-spec-driven profile

Read this when the profile is tlc-spec-driven: a feature folder `.specs/features/{slug}/` written by tlc-spec-driven. The page is built only from the files; you write nothing into the review state (`.specs/features/{slug}/spec-review.json`, written by the scripts).

## Tabs

One tab per file, in this order, for the files that exist; an expected file that is missing shows as a switched-off tab with `-`, and fills in once it exists.

| Tab | File | Version | Expected |
| --- | --- | --- | --- |
| spec | `spec.md` | 3.x, 4.x | yes |
| context | `context.md` | 3.x, 4.x | no |
| design | `design.md` | 3.x, 4.x | yes |
| tasks | `tasks.md` | 3.x, 4.x | yes |
| verification | `verification.md` (the Verifier's report) | 4.x | yes |
| validation | `validation.md` | 3.x | yes |
| screens | `screens.md` | 4.x | no |

`proofs.md` stays out: it is the tail of the test runs, written by a script, not text to review. Other `.md` files in the folder (`tasks-p2.md`, an addendum) stay out too; build them as generic pages if the user wants them.

**Version.** 4.x when the folder has `verification.md`, or `spec.md` / `tasks.md` carry `**Approved**:`; 3.x otherwise. The build prints it (`PROFILE tlc-spec-driven 4.x`).

**Detection** needs `spec.md` (with `User Stories` or `Requirement Traceability`), `design.md` (`Architecture Overview` or `Components`) or `tasks.md` (`Task Breakdown`). A folder with only a Verifier report, or a spec written in another shape (a short bug-fix spec with `Problema` / `Causa raiz`), is not recognized: build its files as generic pages, or pass `--profile tlc-spec-driven` when the user says it is a tlc-spec-driven feature.

## What the user reviews

Besides each section and each table row:

| Unit | Where | Cited as |
| --- | --- | --- |
| each EARS criterion (`WHEN` / `IF` / `WHILE` / `WHERE` / `The system`) of a numbered list under a story `### P1: ...` | spec | `P1 AC 2` |
| each EARS bullet of `## Edge Cases` | spec | `Edge Cases #1` |
| each task heading `### T1: ...` (the fingerprint covers the task's whole body) | tasks | `T1` |
| each check paragraph `**C1** - ...` in `## Checks` (4.x) | tasks | `C1` |

When a citation would repeat on the page (two stories both `P1`), it falls back to `Section #N`; a citation repeated across tabs gets the tab in front (`spec · Risks #2`). The number button on the page copies exactly what the user should cite, and `sync_review.py` reports rejected units the same way.

## Links across tabs

IDs the files define become links wherever the text writes them: `T1` (task heading), `C1` (check), `LEMB-01` (first cell of a `Requirement Traceability` row), `P1` (story heading). An ID defined twice on the page gets no link (it would point to the wrong one). Under each requirement ID the page lists the tasks and checks whose text cites it ("cited by T2 T4 C1"). Nothing is inferred: an ID the files never write is never linked, and a requirement no task cites shows no list.

## Approval

tlc-spec-driven writes `**Approved**:` (4.x) or `**Status**:` in the files; the page shows the line as text. Validating on the page is not approving: never write either line from the badges.
