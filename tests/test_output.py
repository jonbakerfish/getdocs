import json

import yaml

from getdocs.output import FileTreeWriter, PageRecord


def make_record(**overrides):
    defaults = dict(
        url="https://example.com/docs/auth",
        title="Authentication",
        markdown="# Authentication\n\nUse a bearer token.",
        status=200,
        crawled_at="2026-06-12T10:00:00Z",
    )
    return PageRecord(**{**defaults, **overrides})


def read_frontmatter_and_body(path):
    text = path.read_text()
    assert text.startswith("---\n")
    frontmatter, body = text[4:].split("\n---\n", 1)
    return yaml.safe_load(frontmatter), body.strip()


def test_page_is_written_as_markdown_file_mirroring_url_path(tmp_path):
    writer = FileTreeWriter(tmp_path)

    writer.write_page(make_record())

    page_file = tmp_path / "docs" / "auth.md"
    assert page_file.exists()
    frontmatter, body = read_frontmatter_and_body(page_file)
    assert frontmatter["url"] == "https://example.com/docs/auth"
    assert frontmatter["title"] == "Authentication"
    assert frontmatter["status"] == 200
    assert frontmatter["crawled_at"] == "2026-06-12T10:00:00Z"
    assert body == "# Authentication\n\nUse a bearer token."


def test_manifest_records_seeds_and_page_count(tmp_path):
    writer = FileTreeWriter(tmp_path)
    writer.write_page(make_record())

    writer.write_manifest(seeds=["https://example.com/docs/auth"])

    manifest = json.loads((tmp_path / "crawl.json").read_text())
    assert manifest["seeds"] == ["https://example.com/docs/auth"]
    assert manifest["page_count"] == 1
