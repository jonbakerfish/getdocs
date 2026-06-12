#!/usr/bin/env python
"""Rename percent-encoded files in an existing crawl output directory.

Crawls made before getdocs decoded URL escapes wrote file names containing
literal %20 etc. The content is fine — only the names need fixing, so this
renames every affected file and directory using the same rule the writer now
applies (percent-decode each name; a decoded "/" becomes "_"). No re-crawl
is needed.

Usage:
    python scripts/fix_encoded_names.py ./out            # rename in place
    python scripts/fix_encoded_names.py ./out --dry-run  # preview only
"""

import argparse
import sys
from pathlib import Path
from urllib.parse import unquote


def decoded(name: str) -> str:
    return unquote(name).replace("/", "_")


def collect_renames(crawl_dir: Path) -> list[tuple[Path, Path]]:
    """Deepest paths first, so children are renamed before their parents."""
    renames = []
    for path in sorted(crawl_dir.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if ".getdocs" in path.parts:
            continue
        new_name = decoded(path.name)
        if new_name != path.name:
            renames.append((path, path.with_name(new_name)))
    return renames


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("crawl_dir", type=Path, nargs="?", default=Path("./out"),
                        help="getdocs output directory (default: ./out)")
    parser.add_argument("--dry-run", action="store_true", help="Print renames without applying")
    args = parser.parse_args()

    if not args.crawl_dir.is_dir():
        print(f"error: {args.crawl_dir} is not a directory", file=sys.stderr)
        return 2

    renames = collect_renames(args.crawl_dir)
    if not renames:
        print("nothing to fix — no percent-encoded names found")
        return 0

    skipped = 0
    for source, target in renames:
        if target.exists():
            print(f"skip (target exists): {source} -> {target.name}", file=sys.stderr)
            skipped += 1
            continue
        print(f"{source.relative_to(args.crawl_dir)} -> {target.name}")
        if not args.dry_run:
            source.rename(target)

    action = "would rename" if args.dry_run else "renamed"
    print(f"{action} {len(renames) - skipped} path(s)" + (f", {skipped} skipped" if skipped else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
