"""Docs stay consistent with the code.

These guard against the most common doc rot: a CLI flag shipped but never
documented. The check is deliberately shallow (presence, not prose) so it
flags real drift without being noisy.
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_every_cli_flag_is_documented_in_usage():
    cli = (REPO / "src" / "getdocs" / "cli.py").read_text()
    usage = (REPO / "docs" / "USAGE.md").read_text()
    flags = sorted(set(re.findall(r'"(--[a-z][a-z-]+)"', cli)))
    assert flags  # sanity: we actually found the flag definitions
    missing = [f for f in flags if f not in usage]
    assert not missing, f"CLI flags missing from docs/USAGE.md: {missing}"
