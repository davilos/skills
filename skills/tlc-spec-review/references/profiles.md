# Profiles

Read this when adding a profile, or when detection picks the wrong one. A profile is a JSON file in `assets/profiles/`; `scripts/profiles.py` reads it.

## How a profile is picked

1. The profile the user named (`--profile`). It wins; when detection disagrees, the build warns in one line and goes on with the user's.
2. The profile recorded in the review state (`"profile"`), so a rebuild never switches on its own.
3. Detection: `tlc-spec-lean` when a `plan.md` has the profile's headings; `tlc-spec-driven` when a feature folder has its files with their headings. Both: exit 3, ask the user. Neither: `generic`.

The file name alone never picks a profile: a `plan.md` without `Shape` and `Landing` (or `Flow` and `Impact`) is generic.

## Fields

| Field | Used by | What it is |
| --- | --- | --- |
| `name`, `engine`, `about` | all | `engine` is `doc` (the doc_* scripts and `assets/doc-template.html`) or `lean` (the lean_* scripts and `assets/tlc-spec-lean/template.html`) |
| `detect.file`, `detect.headings` | lean | the file and the `##` headings it must have: a list of `{all: [...]}` or `{any: [...]}`, any of which matches |
| `detect.files` | doc | per file name, the `##` headings that recognize it |
| `tabs` | doc | `{id, file, versions?, expected?}` in page order; `expected` shows a missing file as a switched-off tab |
| `items` | doc | extra review units: `{tab, kind, text, section?, under?, list?, cite, ac?}`; `"ac": true` (list items only) marks them as acceptance criteria, flagged on the page when they change |
| `ids` | doc | where IDs are defined: `{tab, kind, text, section?}` |
| `covers` | doc | `{ids, by}`: which IDs list the units that cite them, and which units count (`tab:kind`) |

**Item kinds.** `li`: an item of a list (`list`: `ol` or `ul`) whose text matches `text`; with `under`, only under a subheading matching it. `h`: a subheading matching `text` (its fingerprint covers everything under it). `p`: a paragraph matching `text`. `cell` (in `ids` only): the first cell of a table row. `section` restricts any rule to the `##` sections whose name matches.

**Citations.** `cite` takes `{1}` (the first group of `text`), `{under}` (the first group of `under`), `{n}` (the number the list item was written with), `{i}` (its position among the section's matches) and `{section}`. The build makes every citation unique on the page.

All regexes are Python syntax; anchor them (`^...$`) so they do not match inside other text.

## Adding a profile

1. Prefer the `doc` engine and data only: a new JSON file in `assets/profiles/`, plus its detection in `profiles.py` if it needs more than headings.
2. Add a fixture (synthetic, no project data) under `tests/fixtures/` and build it: `check_page.cjs` must print `"ok": true` with full coverage per file, and its review flow must exercise each new unit kind.
3. Document the profile in `references/{name}.md` and point to it from SKILL.md.
