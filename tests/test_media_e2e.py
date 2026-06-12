import json
import subprocess
import sys

from conftest import FixtureSite

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
PDF = b"%PDF-1.4 fake datasheet " + b"\x00" * 64


def page(title, body):
    return f"<html><head><title>{title}</title></head><body><main>{body}</main></body></html>"


def run_getdocs(*args):
    return subprocess.run(
        [sys.executable, "-m", "getdocs", *args, "--delay", "0"],
        capture_output=True, text=True, timeout=120,
    )


def manifest_of(tmp_path):
    return json.loads((tmp_path / "crawl.json").read_text())


def build_media_site(site, cdn):
    site.add("/docs/", page("Home", f"""
        <h1>Home</h1>
        <img src="/img/diagram.png" alt="diagram">
        <a href="/files/datasheet.pdf">Datasheet</a>
        <a href="/docs/guide/install">Guide</a>"""))
    site.add("/docs/guide/install", page("Install", f"""
        <h1>Install</h1>
        <img src="/img/diagram.png" alt="same diagram again">
        <img src="{cdn.url}/logo.png" alt="cdn logo">"""))
    site.add_bytes("/img/diagram.png", PNG, "image/png")
    site.add_bytes("/files/datasheet.pdf", PDF, "application/pdf")
    cdn.add_bytes("/logo.png", PNG, "image/png")


def test_download_media_fetches_assets_and_rewrites_links(site, tmp_path):
    cdn = FixtureSite()
    try:
        build_media_site(site, cdn)

        result = run_getdocs(
            "crawl", f"{site.url}/docs/", "-o", str(tmp_path), "--download-media"
        )
        assert result.returncode == 0, result.stderr

        host = site.url.removeprefix("http://")
        cdn_host = cdn.url.removeprefix("http://")
        assert (tmp_path / "_media" / host / "img" / "diagram.png").read_bytes() == PNG
        assert (tmp_path / "_media" / host / "files" / "datasheet.pdf").read_bytes() == PDF
        assert (tmp_path / "_media" / cdn_host / "logo.png").exists()  # cross-host (ADR-0005)

        home = (tmp_path / "docs.md").read_text()
        assert f"(_media/{host}/img/diagram.png)" in home
        assert f"(_media/{host}/files/datasheet.pdf)" in home

        install = (tmp_path / "docs" / "guide" / "install.md").read_text()
        assert f"(../../_media/{host}/img/diagram.png)" in install  # relative from nesting
        assert f"(../../_media/{cdn_host}/logo.png)" in install

        assert site.hits["/img/diagram.png"] == 1  # referenced twice, fetched once
        assert manifest_of(tmp_path)["media_skipped"] == []
    finally:
        cdn.stop()


def test_oversized_asset_stays_hotlinked_and_is_noted(site, tmp_path):
    site.add("/docs/", page("Home", '<h1>Home</h1><img src="/img/huge.png" alt="huge">'))
    site.add_bytes("/img/huge.png", b"\x00" * 4096, "image/png")

    result = run_getdocs(
        "crawl", f"{site.url}/docs/", "-o", str(tmp_path),
        "--download-media", "--media-max-size", "0.002",  # ~2 KB cap
    )

    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "_media").exists()
    assert f"({site.url}/img/huge.png)" in (tmp_path / "docs.md").read_text()  # absolute kept
    skipped = manifest_of(tmp_path)["media_skipped"]
    assert len(skipped) == 1 and skipped[0]["url"] == f"{site.url}/img/huge.png"


def test_without_flag_no_media_dir_and_links_stay_absolute(site, tmp_path):
    site.add("/docs/", page("Home", '<h1>Home</h1><img src="/img/x.png" alt="x">'))
    site.add_bytes("/img/x.png", PNG, "image/png")

    result = run_getdocs("crawl", f"{site.url}/docs/", "-o", str(tmp_path))

    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "_media").exists()
    assert site.hits.get("/img/x.png") is None  # never fetched
    assert f"({site.url}/img/x.png)" in (tmp_path / "docs.md").read_text()


def test_jsonl_records_carry_root_relative_media_paths(site, tmp_path):
    site.add("/docs/", page("Home", '<h1>Home</h1><img src="/img/x.png" alt="x">'))
    site.add_bytes("/img/x.png", PNG, "image/png")

    result = run_getdocs(
        "crawl", f"{site.url}/docs/", "-o", str(tmp_path),
        "--download-media", "--format", "jsonl",
    )

    assert result.returncode == 0, result.stderr
    records = [json.loads(line) for line in result.stdout.strip().split("\n")]
    page_record = next(r for r in records if r["type"] == "page")
    host = site.url.removeprefix("http://")
    assert f"(_media/{host}/img/x.png)" in page_record["markdown"]
    assert (tmp_path / "_media" / host / "img" / "x.png").exists()
