#!/usr/bin/env python3
"""Bring into the review state what the user validated on the published page.

Read the artifact's `review` collection with ArtifactData (`action: "list"`, `collection: "review"`,
`out_dir: <dir>`) and pass that directory. A mark only counts if its fingerprint still matches the
current text; the rest comes out as RECHECK.

Usage:
    python3 sync_review.py <target>... --dir <out_dir directory> [--profile P] [--dry-run]

Prints validated, partly confirmed and pending sections and the rejected rows (what the user wants
to discuss before anyone changes the document).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # no __pycache__ in the skill folder: the registry would ship it
sys.path.insert(0, str(Path(__file__).resolve().parent))
import profiles  # noqa: E402
from build_page import resolve  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("target", nargs="+")
    ap.add_argument("--dir", required=True, help="directory where ArtifactData saved the review collection")
    ap.add_argument("--profile", choices=["generic", "tlc-spec-lean", "tlc-spec-driven"])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    info = resolve(args.target, args.profile)
    if not info:
        return 1
    sp = profiles.state_path(info)
    if info["profile"] == "tlc-spec-lean":
        import lean_sync
        feat = Path(info["feature"])
        sys.argv = ["sync_review.py", "--root", str(feat.parent.parent.parent), "--data", str(sp), "--dir", args.dir, feat.name] + (["--dry-run"] if args.dry_run else [])
        return lean_sync.main()
    import doc_sync
    return doc_sync.sync(info, sp, Path(args.dir), args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
