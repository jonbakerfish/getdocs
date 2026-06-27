"""Clone completion summary (#22): the source-first Outcome report.

When a run clones the docs' source repo instead of crawling (ADR-0006), it
reports a `cloned` Outcome — distinct from a Crawl — so an agent can branch on
it. Verified at the in-process cli.main() seam with the source-first
orchestrator's network/git collaborators stubbed (prior art: test_source.py
monkeypatches fetch_html and clone_repo).
"""

import json

from getdocs import cli, source

EDIT_LINK_HTML = (
    '<a href="https://github.com/acme/docs/edit/main/p.md" '
    'title="Edit this page">edit</a>'
)


def fake_clone_with_docs(tmp_path):
    """A clone_repo stand-in that fabricates a repo dir holding markdown docs."""
    def _clone(repo_url, dest_parent, timeout=180.0):
        repo = dest_parent / "docs"
        (repo / "docs").mkdir(parents=True)
        (repo / "docs" / "index.md").write_text("# Home")
        return repo
    return _clone


def test_clone_prints_one_line_stderr_summary(tmp_path, monkeypatch, capsys):
    out = tmp_path / "out"
    monkeypatch.setattr(source, "fetch_html", lambda url, ua=None: EDIT_LINK_HTML)
    monkeypatch.setattr(source, "clone_repo", fake_clone_with_docs(tmp_path))

    rc = cli.main(["crawl", "https://docs.acme.io/", "-o", str(out)])

    assert rc == 0
    err = capsys.readouterr().err
    # Names the source repo and the cloned / serve-config locations.
    assert "getdocs: cloned acme/docs" in err
    assert str(out / "docs") in err
    assert "mkdocs.yml" in err


def test_clone_summary_json_emits_cloned_object(tmp_path, monkeypatch, capsys):
    out = tmp_path / "out"
    monkeypatch.setattr(source, "fetch_html", lambda url, ua=None: EDIT_LINK_HTML)
    monkeypatch.setattr(source, "clone_repo", fake_clone_with_docs(tmp_path))

    rc = cli.main(["crawl", "https://docs.acme.io/", "-o", str(out), "--summary-json"])

    assert rc == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["outcome"] == "cloned"
    assert summary["status"] == "ok"
    assert summary["repo"] == "acme/docs"
    assert summary["output_dir"] == str(out / "docs")
    assert summary["mkdocs_config"] == str(out / "mkdocs.yml")
    # A Clone has no Pages and no Manifest (CONTEXT.md): those keys are absent.
    assert "pages" not in summary
    assert "manifest" not in summary


def test_clone_stderr_line_and_json_carry_the_same_facts(tmp_path, monkeypatch, capsys):
    out = tmp_path / "out"
    monkeypatch.setattr(source, "fetch_html", lambda url, ua=None: EDIT_LINK_HTML)
    monkeypatch.setattr(source, "clone_repo", fake_clone_with_docs(tmp_path))

    rc = cli.main(["crawl", "https://docs.acme.io/", "-o", str(out), "--summary-json"])

    assert rc == 0
    captured = capsys.readouterr()
    summary = json.loads(captured.out)
    assert f"cloned {summary['repo']}" in captured.err
    assert summary["output_dir"] in captured.err


def test_agent_can_branch_on_outcome_clone_vs_crawl(tmp_path, monkeypatch, capsys):
    # A cloned run is discriminable from a crawled run purely by `outcome`.
    out = tmp_path / "out"
    monkeypatch.setattr(source, "fetch_html", lambda url, ua=None: EDIT_LINK_HTML)
    monkeypatch.setattr(source, "clone_repo", fake_clone_with_docs(tmp_path))

    cli.main(["crawl", "https://docs.acme.io/", "-o", str(out), "--summary-json"])
    cloned = json.loads(capsys.readouterr().out)

    assert cloned["outcome"] == "cloned"
    assert cloned["outcome"] != "crawled"
