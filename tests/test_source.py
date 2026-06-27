"""Source-first detection, cloning, and the clone_source_for orchestrator."""

import subprocess
from pathlib import Path

import pytest

from getdocs import source
from getdocs.config import CrawlConfig

# --- repo_root_from_url -------------------------------------------------------


def test_repo_root_strips_edit_deeplink():
    url = "https://github.com/acme/docs/edit/main/docs/intro.md"
    assert source.repo_root_from_url(url) == "https://github.com/acme/docs"


def test_repo_root_keeps_bare_repo_and_drops_dot_git():
    assert source.repo_root_from_url("https://github.com/acme/docs") == "https://github.com/acme/docs"
    assert source.repo_root_from_url("https://github.com/acme/docs.git") == "https://github.com/acme/docs"


def test_repo_root_normalizes_www_and_other_hosts():
    assert source.repo_root_from_url("https://www.github.com/a/b") == "https://github.com/a/b"
    assert source.repo_root_from_url("https://gitlab.com/a/b/-/tree/main") == "https://gitlab.com/a/b"


def test_repo_root_rejects_non_repo_paths():
    assert source.repo_root_from_url("https://github.com/acme") is None  # owner only
    assert source.repo_root_from_url("https://github.com/sponsors/acme") is None  # product page
    assert source.repo_root_from_url("https://example.com/acme/docs") is None  # unknown host
    assert source.repo_root_from_url("mailto:x@y.com") is None


# --- detect_repo --------------------------------------------------------------


def test_detect_repo_finds_material_edit_link():
    html = """
    <html><body>
      <a href="https://github.com/acme/docs/edit/main/docs/page.md"
         title="Edit this page" class="md-content__button">edit</a>
      <a href="https://twitter.com/acme">Follow us</a>
    </body></html>
    """
    assert source.detect_repo(html) == "https://github.com/acme/docs"


def test_detect_repo_finds_docusaurus_edit_link():
    html = (
        '<a class="theme-edit-this-page" '
        'href="https://github.com/acme/site/edit/main/docs/intro.mdx">Edit this page</a>'
    )
    assert source.detect_repo(html) == "https://github.com/acme/site"


def test_detect_repo_resolves_relative_edit_href_against_base():
    # Some themes emit a host-relative edit href; resolve it against the page.
    html = '<a href="/acme/docs/blob/main/x.md" class="edit-page">Edit</a>'
    # Relative href has no scheme/host, so it can only resolve onto the seed's
    # own (non-git) host -> no repo. A protocol-relative github link does work:
    html = '<a href="//github.com/acme/docs/blob/main/x.md">Edit on GitHub</a>'
    assert source.detect_repo(html, base_url="https://docs.acme.io/intro") == "https://github.com/acme/docs"


def test_detect_repo_prefers_edit_link_over_footer_mention():
    html = """
      <footer><a href="https://github.com/acme/marketing">Star us on GitHub</a></footer>
      <a href="https://github.com/acme/docs/edit/main/p.md" title="Edit this page">e</a>
    """
    assert source.detect_repo(html) == "https://github.com/acme/docs"


def test_detect_repo_returns_none_without_repo_links():
    assert source.detect_repo("<a href='https://acme.io/about'>About</a>") is None
    assert source.detect_repo("<html><body>no links</body></html>") is None


# --- clone_repo + find_docs_dir (real git, file:// remote) --------------------


def _make_bare_repo(tmp_path: Path, docs: dict[str, str]) -> Path:
    """Create a real local bare repo seeded with the given files."""
    work = tmp_path / "work"
    work.mkdir()
    for rel, body in docs.items():
        target = work / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body)
    env = {
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
    }
    run = lambda *args: subprocess.run(args, cwd=work, check=True, capture_output=True, env={**env})
    run("git", "init", "-q")
    run("git", "add", "-A")
    run("git", "commit", "-q", "-m", "init")
    bare = tmp_path / "repo.git"
    subprocess.run(["git", "clone", "--bare", "-q", str(work), str(bare)], check=True, capture_output=True)
    return bare


@pytest.mark.skipif(not __import__("shutil").which("git"), reason="git not installed")
def test_clone_repo_and_find_docs_dir(tmp_path):
    bare = _make_bare_repo(tmp_path, {"docs/index.md": "# Home", "README.md": "x"})
    out = tmp_path / "out"

    repo_dir = source.clone_repo(str(bare), out)
    assert repo_dir is not None
    assert (repo_dir / ".git").exists()
    assert repo_dir.name == "repo"  # .git suffix stripped

    docs_dir = source.find_docs_dir(repo_dir)
    assert docs_dir == repo_dir / "docs"

    # Idempotent: a second clone returns the existing checkout untouched.
    assert source.clone_repo(str(bare), out) == repo_dir


def test_find_docs_dir_falls_back_to_repo_root(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("# top-level docs")
    assert source.find_docs_dir(repo) == repo


def test_find_docs_dir_none_without_markdown(tmp_path):
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "main.py").write_text("print()")
    assert source.find_docs_dir(repo) is None


# --- write_mkdocs_config ------------------------------------------------------


def test_write_mkdocs_config(tmp_path):
    import yaml

    docs = tmp_path / "repo" / "docs"
    docs.mkdir(parents=True)
    out = tmp_path / "out"

    path = source.write_mkdocs_config(out, docs, "docs.acme.io")
    config = yaml.safe_load(path.read_text())

    assert path == out / "mkdocs.yml"
    assert config["site_name"] == "docs.acme.io"
    assert config["docs_dir"] == str(docs.resolve())
    assert config["use_directory_urls"] is True


# --- clone_source_for orchestration (network/git stubbed) ---------------------


def test_clone_source_for_clones_and_writes_config(tmp_path, monkeypatch):
    out = tmp_path / "out"
    monkeypatch.setattr(source, "fetch_html", lambda url: '<a href="https://github.com/acme/docs/edit/main/p.md" title="Edit this page">e</a>')

    def fake_clone(repo_url, dest_parent, timeout=180.0):
        assert repo_url == "https://github.com/acme/docs"
        repo = dest_parent / "docs"
        (repo / "docs").mkdir(parents=True)
        (repo / "docs" / "index.md").write_text("# Home")
        return repo

    monkeypatch.setattr(source, "clone_repo", fake_clone)

    config = CrawlConfig(seeds=["https://docs.acme.io/intro"], output_dir=out)
    result = source.clone_source_for(config)

    assert result == out / "docs"
    assert (out / "mkdocs.yml").exists()


def test_clone_source_for_falls_back_when_no_repo(tmp_path, monkeypatch):
    monkeypatch.setattr(source, "fetch_html", lambda url: "<html>no repo here</html>")
    config = CrawlConfig(seeds=["https://docs.acme.io/intro"], output_dir=tmp_path / "out")
    assert source.clone_source_for(config) is None


def test_clone_source_for_skips_non_http_seed(tmp_path):
    config = CrawlConfig(seeds=["file:///local/docs"], output_dir=tmp_path / "out")
    assert source.clone_source_for(config) is None


def test_clone_source_for_uses_repos_own_mkdocs_yml(tmp_path, monkeypatch):
    out = tmp_path / "out"
    monkeypatch.setattr(source, "fetch_html", lambda url: '<a href="https://github.com/acme/docs">GitHub</a>')

    def fake_clone(repo_url, dest_parent, timeout=180.0):
        repo = dest_parent / "docs"
        repo.mkdir(parents=True)
        (repo / "mkdocs.yml").write_text("site_name: Acme\n")
        return repo

    monkeypatch.setattr(source, "clone_repo", fake_clone)
    config = CrawlConfig(seeds=["https://docs.acme.io/"], output_dir=out)

    assert source.clone_source_for(config) == out / "docs"
    # We don't overwrite a repo that already ships its own config.
    assert not (out / "mkdocs.yml").exists()
