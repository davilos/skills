"""Which profile a document gets, which files its page shows, and where its review state lives.

Profiles (assets/profiles/*.json):
- `tlc-spec-lean`: a `plan.md` with the tlc-spec-lean sections (`Shape` and `Landing`, or the older
  `Flow` and `Impact`). Built by the lean_* engine.
- `tlc-spec-driven`: a feature folder with `spec.md`, `design.md`, `tasks.md`... (one tab per file).
  Built by the doc_* engine with the profile's extra review items and links.
- `generic`: anything else; one Markdown file, or several the user lists (one tab each).

Order: the profile the user named wins (the agent warns when detection disagrees); then the one
recorded in the review state; then detection. The file name alone never picks a profile: a
`plan.md` without the tlc-spec-lean headings is generic.

The review state is named after this skill: `<feature>/spec-review.json` for a feature folder,
`<stem>-spec-review.json` beside a single document. The older names (`review-page.json` from
plan-review, `<stem>-doc-review.json` from doc-review) are renamed on first use.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SKILL = "spec-review"
ASSETS = Path(__file__).resolve().parent.parent / "assets"
H2 = re.compile(r"^##\s+(.+?)\s*#*\s*$")
FENCE = re.compile(r"^\s*(```|~~~)")


class ProfileError(Exception):
    """The target cannot be built as asked (missing file, ambiguous profile...)."""


def load_profile(name: str) -> dict:
    p = ASSETS / "profiles" / f"{name}.json"
    if not p.is_file():
        raise ProfileError(f"unknown profile {name!r} (known: {', '.join(sorted(x.stem for x in (ASSETS / 'profiles').glob('*.json')))})")
    return json.loads(p.read_text(encoding="utf-8"))


def h2_names(path: Path) -> set[str]:
    """The `##` headings of a file, outside code blocks, lowercased."""
    names, in_code = set(), False
    for line in path.read_text(encoding="utf-8").splitlines():
        if FENCE.match(line):
            in_code = not in_code
            continue
        m = None if in_code else H2.match(line)
        if m:
            names.add(m[1].strip().lower())
    return names


def _matches(path: Path, rule: dict) -> bool:
    """A detect rule: `all` headings present, or `any` of them."""
    if not path.is_file():
        return False
    names = h2_names(path)
    if "all" in rule:
        return all(h.lower() in names for h in rule["all"])
    return any(h.lower() in names for h in rule.get("any", []))


def lean_match(plan: Path) -> bool:
    prof = load_profile("tlc-spec-lean")
    return plan.name == "plan.md" and any(_matches(plan, r) for r in prof["detect"]["headings"])


def driven_files(folder: Path) -> dict[str, bool]:
    """The tlc-spec-driven files in a folder and whether each one has that file's headings."""
    prof = load_profile("tlc-spec-driven")
    return {name: _matches(folder / name, rule) for name, rule in prof["detect"]["files"].items() if (folder / name).is_file()}


def driven_version(folder: Path) -> str:
    """4.x writes `**Approved**:` in spec.md and tasks.md and names the Verifier's report verification.md."""
    if (folder / "verification.md").is_file():
        return "4.x"
    if (folder / "validation.md").is_file():
        return "3.x"
    for name in ("spec.md", "tasks.md"):
        p = folder / name
        if p.is_file() and re.search(r"^\*\*Approved\*\*:", p.read_text(encoding="utf-8"), re.M):
            return "4.x"
    return "3.x"


def driven_tabs(folder: Path) -> list[dict]:
    """The tabs of a tlc-spec-driven page, in the profile's order: each file that exists, plus the
    expected ones of that version that are missing (shown switched off)."""
    prof = load_profile("tlc-spec-driven")
    version = driven_version(folder)
    tabs = []
    for t in prof["tabs"]:
        if version not in t.get("versions", ["3.x", "4.x"]):
            continue
        exists = (folder / t["file"]).is_file()
        if exists or t.get("expected"):
            tabs.append({"id": t["id"], "file": t["file"], "path": str(folder / t["file"]), "exists": exists})
    return tabs


def feature_of(path: Path) -> Path | None:
    """The feature folder (`<root>/.specs/features/<slug>`) a path is in, or None."""
    p = path.resolve()
    folder = p if p.is_dir() else p.parent
    if folder.parent.name == "features" and folder.parent.parent.name == ".specs":
        return folder
    return None


def detect(targets: list[str], forced: str | None = None, recorded: str | None = None) -> dict:
    """The profile for a build: {profile, reason, files | plan, feature, warn}.

    `targets`: what the user pointed at (a .md file, several, or a feature folder).
    """
    paths = [Path(t) for t in targets]
    for p in paths:
        if not p.exists():
            raise ProfileError(f"{p} not found")
    first = paths[0]
    feat = feature_of(first) if len(paths) == 1 else None
    folder = first if first.is_dir() else first.parent

    found = []  # what detection finds, strongest first
    plan = folder / "plan.md"
    if (first.is_dir() or first.name == "plan.md") and lean_match(plan):
        found.append(("tlc-spec-lean", f"{plan} has the tlc-spec-lean sections"))
    df = driven_files(folder) if (first.is_dir() or first.name != "plan.md") else {}
    recognized = [n for n, ok in df.items() if ok]
    # A Verifier report alone is not a tlc-spec-driven feature: tlc-spec-lean writes verification.md too.
    core = [n for n in recognized if n in ("spec.md", "design.md", "tasks.md")]
    if len(paths) == 1 and core and (first.is_dir() or first.name in df):
        found.append(("tlc-spec-driven", f"{', '.join(recognized)} with the tlc-spec-driven sections"))

    warn = None
    if forced:
        name = forced
        reason = "named by the user"
        if found and found[0][0] != forced:
            warn = f"detection points to {found[0][0]} ({found[0][1]}); using {forced} as the user said"
    elif recorded:
        name, reason = recorded, "recorded in the review state"
    elif len(found) > 1:
        raise ProfileError("ambiguous: " + "; ".join(f"{n} ({r})" for n, r in found) +
                           ". Ask the user which one and pass --profile")
    elif found:
        name, reason = found[0]
    else:
        name, reason = "generic", "no profile recognizes it"

    out = {"profile": name, "reason": reason, "warn": warn}
    if name == "tlc-spec-lean":
        if not plan.is_file():
            raise ProfileError(f"tlc-spec-lean needs {plan}")
        if not feature_of(plan):
            raise ProfileError(f"tlc-spec-lean needs the plan inside .specs/features/<slug>/ ({plan})")
        out.update(plan=str(plan), feature=str(feature_of(plan)))
    elif name == "tlc-spec-driven":
        if not feature_of(folder):
            raise ProfileError(f"tlc-spec-driven needs a folder inside .specs/features/ ({folder})")
        out.update(feature=str(feature_of(folder)), version=driven_version(folder), tabs=driven_tabs(folder))
        if not any(t["exists"] for t in out["tabs"]):
            raise ProfileError(f"{folder} has none of the tlc-spec-driven files")
    else:
        files = [p for p in paths if p.is_file()]
        if not files or len(files) != len(paths):
            raise ProfileError(f"no profile recognizes the folder {first} (no tlc-spec-lean plan.md, no tlc-spec-driven "
                               "spec.md / design.md / tasks.md with their sections). Point at its .md files, or pass "
                               "--profile tlc-spec-driven if the user says it is one")
        if feat and feat == folder and len(paths) == 1:
            out["feature"] = None  # a single file in a feature folder keeps its own state beside it
        out["tabs"] = [{"id": "doc" if len(files) == 1 else f"f{i + 1}", "file": f.name, "path": str(f), "exists": True}
                       for i, f in enumerate(files)]
    return out


def _adopt(new: Path, old: Path) -> Path:
    """Rename a state file from the old skill's name to this skill's, once."""
    if old.is_file() and not new.exists():
        old.rename(new)
        print(f"  NOTE  {old.name} renamed to {new.name} (the review state now carries this skill's name)", file=sys.stderr)
    return new


def state_path(info: dict) -> Path:
    """Where the review state of this page lives (renaming the older file if there is one)."""
    if info["profile"] in ("tlc-spec-lean", "tlc-spec-driven"):
        feat = Path(info["feature"])
        new = feat / f"{SKILL}.json"
        return _adopt(new, feat / "review-page.json") if info["profile"] == "tlc-spec-lean" else new
    doc = Path(info["tabs"][0]["path"])
    return _adopt(doc.with_name(f"{doc.stem}-{SKILL}.json"), doc.with_name(f"{doc.stem}-doc-review.json"))


def recorded_profile(targets: list[str]) -> str | None:
    """The profile written in an existing review state, if any (read without renaming anything)."""
    first = Path(targets[0])
    folder = first if first.is_dir() else first.parent
    candidates = []
    # The feature's state is the page of the whole feature: it speaks for the folder and its profiles'
    # own files, never for another document in the folder (a `notes.md` beside the spec stays generic).
    own = {"plan.md"} | {t["file"] for t in load_profile("tlc-spec-driven")["tabs"]}
    if feature_of(folder) and len(targets) == 1 and (first.is_dir() or first.name in own):
        candidates += [folder / f"{SKILL}.json"]
    if first.is_file():
        candidates += [first.with_name(f"{first.stem}-{SKILL}.json")]
    for c in candidates:
        if c.is_file():
            try:
                prof = json.loads(c.read_text(encoding="utf-8")).get("profile")
            except json.JSONDecodeError:
                continue
            if prof:
                return prof
    return None
