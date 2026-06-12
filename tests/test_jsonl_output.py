import io
import json

from getdocs.output import JsonlWriter, PageRecord


def make_record(**overrides):
    defaults = dict(
        url="https://example.com/docs/auth",
        title="Authentication",
        markdown="# Auth",
        status=200,
        crawled_at="2026-06-12T10:00:00Z",
    )
    return PageRecord(**{**defaults, **overrides})


def test_each_page_is_one_typed_json_line_and_manifest_is_final_record():
    stream = io.StringIO()
    writer = JsonlWriter(stream)

    writer.write_page(make_record())
    writer.write_page(make_record(url="https://example.com/docs/intro", title="Intro"))
    writer.write_manifest(seeds=["https://example.com/docs"])

    lines = stream.getvalue().strip().split("\n")
    records = [json.loads(line) for line in lines]  # parses line-by-line
    assert len(records) == 3

    page = records[0]
    assert page["type"] == "page"
    assert page["url"] == "https://example.com/docs/auth"
    assert page["title"] == "Authentication"
    assert page["markdown"] == "# Auth"
    assert page["status"] == 200
    assert page["crawled_at"] == "2026-06-12T10:00:00Z"
    assert "canonical" not in page  # None fields omitted
    assert "html" not in page

    manifest = records[-1]
    assert manifest["type"] == "manifest"
    assert manifest["seeds"] == ["https://example.com/docs"]
    assert manifest["page_count"] == 2


def test_markdown_with_newlines_stays_on_one_line():
    stream = io.StringIO()
    writer = JsonlWriter(stream)

    writer.write_page(make_record(markdown="# Auth\n\nUse a *token*.\n"))

    assert len(stream.getvalue().strip().split("\n")) == 1


def test_kept_html_appears_in_jsonl_record():
    stream = io.StringIO()
    writer = JsonlWriter(stream)

    writer.write_page(make_record(html="<html><body>raw</body></html>"))

    record = json.loads(stream.getvalue())
    assert record["html"] == "<html><body>raw</body></html>"
