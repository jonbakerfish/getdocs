"""Plugin & marketplace manifest validation (#24).

The /getdocs plugin is a markdown/JSON instruction artifact, not Python
behavior, so these tests assert the artifact is well-formed and self-consistent:
the marketplace lists the plugin, the plugin manifest is valid, the command file
exists, and the command invokes getdocs with the Outcome contract
(--summary-json) plus the version pin it depends on. Behavioral correctness of
crawling/cloning is covered by getdocs's own suite (and the #19 summary tests).
"""

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MARKETPLACE = REPO / ".claude-plugin" / "marketplace.json"


def _marketplace() -> dict:
    return json.loads(MARKETPLACE.read_text())


def _plugin_entry() -> dict:
    return next(p for p in _marketplace()["plugins"] if p["name"] == "getdocs")


def _plugin_dir() -> Path:
    return (REPO / _plugin_entry()["source"]).resolve()


def _plugin_manifest() -> dict:
    return json.loads((_plugin_dir() / ".claude-plugin" / "plugin.json").read_text())


def _command_text() -> str:
    return (_plugin_dir() / "commands" / "getdocs.md").read_text()


SKILL = REPO / "skills" / "getdocs" / "SKILL.md"


def _skill_text() -> str:
    return SKILL.read_text()


def _skill_frontmatter() -> dict:
    import yaml

    body = _skill_text()
    assert body.startswith("---\n")
    _, fm, _ = body.split("---\n", 2)
    return yaml.safe_load(fm)


def test_marketplace_lists_the_getdocs_plugin_and_its_dir_exists():
    market = _marketplace()
    assert market["name"]  # the install target: <plugin>@<marketplace name>
    assert market["owner"]["name"]

    entry = _plugin_entry()
    assert entry["source"].startswith("./")  # same-repo relative source
    assert entry["description"]

    assert (_plugin_dir() / ".claude-plugin" / "plugin.json").exists()


def test_plugin_manifest_is_valid_and_consistent_with_marketplace():
    manifest = _plugin_manifest()
    assert manifest["name"] == "getdocs"
    assert manifest["description"]
    # The validator rejects a version mismatch between the two manifests.
    assert manifest["version"] == _plugin_entry()["version"]


def test_command_file_exists_and_is_discoverable():
    # Commands are auto-discovered from the plugin's commands/ directory.
    assert (_plugin_dir() / "commands" / "getdocs.md").is_file()


def test_command_invokes_getdocs_with_the_summary_json_contract():
    text = _command_text()
    assert "getdocs crawl" in text
    assert "--summary-json" in text  # the Outcome contract this plugin depends on


def test_command_pins_a_getdocs_version_with_summary_json():
    # Must not run against a pre-0.2.0 build that lacks --summary-json (#24).
    text = _command_text()
    assert "uvx" in text
    assert 'getdocs>=0.2.0' in text


def test_command_preserves_polite_defaults():
    # No getdocs invocation overrides robots.txt on the user's behalf. (The
    # command may *mention* --ignore-robots to tell the agent not to use it;
    # what matters is that no actual invocation line passes it.)
    invocations = [
        line for line in _command_text().splitlines() if "getdocs crawl" in line
    ]
    assert invocations  # there is at least one real invocation to check
    assert all("--ignore-robots" not in line for line in invocations)


def test_command_branches_on_every_outcome():
    text = _command_text()
    for token in ('"crawled"', '"cloned"', "truncated", "empty"):
        assert token in text, f"command should guide the {token} Outcome"


def test_command_describes_both_execution_modes_and_the_heuristic():
    text = _command_text().lower()
    # Synchronous for a bounded section; background for a whole-site mirror.
    assert "synchronous" in text
    assert "background" in text
    # A heuristic distinguishing the two cases is documented.
    assert "section" in text and ("whole-site" in text or "whole site" in text)


def test_command_notes_background_resume_is_claude_code_specific():
    text = _command_text().lower()
    # Claude Code resumes the agent on background-task completion (ADR-0007).
    assert "resume" in text
    assert "claude code" in text


def test_command_states_which_mode_it_picked():
    text = _command_text().lower()
    # The command must tell the user which mode it chose and why.
    assert "which mode" in text or "tell the user" in text


def test_plugin_is_discoverable_by_crawl_and_scrape():
    # Marketplace search hits keywords + descriptions, so both must carry the
    # words users actually search for.
    manifest = _plugin_manifest()
    keywords = {k.lower() for k in manifest.get("keywords", [])}
    assert {"crawl", "scrape"} <= keywords
    for term in ("crawl", "scrape"):
        assert term in manifest["description"].lower()
        assert term in _plugin_entry()["description"].lower()


def test_skill_is_discoverable_with_required_frontmatter():
    # `npx skills add` discovers SKILL.md by its name/description frontmatter.
    fm = _skill_frontmatter()
    assert fm["name"] == "getdocs"
    desc = fm["description"].lower()
    assert desc
    assert "crawl" in desc and "scrape" in desc  # searchable terms


def test_skill_invokes_getdocs_with_summary_json_and_version_pin():
    text = _skill_text()
    assert "getdocs crawl" in text
    assert "--summary-json" in text
    assert "uvx" in text and "getdocs>=0.2.0" in text


def test_skill_preserves_polite_defaults():
    invocations = [line for line in _skill_text().splitlines() if "getdocs crawl" in line]
    assert invocations
    assert all("--ignore-robots" not in line for line in invocations)


def test_skill_branches_on_every_outcome():
    text = _skill_text()
    for token in ('"crawled"', '"cloned"', "truncated", "empty"):
        assert token in text, f"skill should guide the {token} Outcome"


def test_readme_documents_the_npx_skills_install():
    readme = (REPO / "README.md").read_text()
    assert "npx skills add jonbakerfish/getdocs" in readme


def test_readme_install_commands_match_the_manifest_names():
    # #27: the documented install commands must stay consistent with the actual
    # marketplace name + plugin name, so a rename can't silently break the docs.
    readme = (REPO / "README.md").read_text()
    market_name = _marketplace()["name"]
    plugin_name = _plugin_entry()["name"]
    assert f"claude plugin install {plugin_name}@{market_name}" in readme
    assert "claude plugin marketplace add jonbakerfish/getdocs" in readme
