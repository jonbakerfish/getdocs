from pathlib import Path

from getdocs.cli import parse_args
from getdocs.config import ServeConfig


def test_crawl_args_become_crawl_config():
    config = parse_args(["crawl", "https://example.com/docs/page", "-o", "./out"])

    assert config.seeds == ["https://example.com/docs/page"]
    assert config.output_dir == Path("./out")


def test_scope_and_depth_flags_become_config_fields():
    config = parse_args([
        "crawl", "https://example.com/docs",
        "--allow-backward", "--allow-subdomains",
        "--include-paths", "/docs/api/*", "--include-paths", "/docs/cli/*",
        "--exclude-paths", "/docs/api/internal/*",
        "--depth", "3",
        "-o", "./out",
    ])

    assert config.allow_backward is True
    assert config.allow_subdomains is True
    assert config.include_paths == ["/docs/api/*", "/docs/cli/*"]
    assert config.exclude_paths == ["/docs/api/internal/*"]
    assert config.depth == 3


def test_scope_flags_default_to_strict():
    config = parse_args(["crawl", "https://example.com/docs"])

    assert config.allow_backward is False
    assert config.allow_subdomains is False
    assert config.include_paths == []
    assert config.exclude_paths == []
    assert config.depth == 0  # 0 = unlimited
    assert config.limit == 1000
    assert config.format == "files"
    assert config.keep_html is False


def test_sitemap_mode_flags():
    assert parse_args(["crawl", "https://x.com/d"]).sitemap == "both"
    assert parse_args(["crawl", "https://x.com/d", "--no-sitemap"]).sitemap == "off"
    assert parse_args(["crawl", "https://x.com/d", "--sitemap-only"]).sitemap == "only"


def test_format_and_keep_html_flags():
    config = parse_args([
        "crawl", "https://example.com/docs", "--format", "jsonl", "--keep-html",
    ])

    assert config.format == "jsonl"
    assert config.keep_html is True


def test_politeness_flags_and_defaults():
    config = parse_args(["crawl", "https://example.com/docs"])
    assert config.ignore_robots is False
    assert config.delay == 1.0
    assert config.concurrency == 4

    config = parse_args([
        "crawl", "https://example.com/docs",
        "--ignore-robots", "--delay", "0.5", "--concurrency", "8",
    ])
    assert config.ignore_robots is True
    assert config.delay == 0.5
    assert config.concurrency == 8


def test_render_mode_flag():
    assert parse_args(["crawl", "https://x.com/d"]).render == "auto"
    assert parse_args(["crawl", "https://x.com/d", "--render", "always"]).render == "always"
    assert parse_args(["crawl", "https://x.com/d", "--render", "never"]).render == "never"


def test_seeds_file_urls_are_added_to_positional_seeds(tmp_path):
    seeds_file = tmp_path / "urls.txt"
    seeds_file.write_text(
        "https://a.com/docs\n"
        "\n"
        "# a comment\n"
        "https://b.com/docs\n"
    )

    config = parse_args([
        "crawl", "https://c.com/docs", "--seeds-file", str(seeds_file),
    ])

    assert config.seeds == ["https://c.com/docs", "https://a.com/docs", "https://b.com/docs"]


def test_seeds_file_alone_satisfies_the_seed_requirement(tmp_path):
    seeds_file = tmp_path / "urls.txt"
    seeds_file.write_text("https://a.com/docs\n")

    config = parse_args(["crawl", "--seeds-file", str(seeds_file)])

    assert config.seeds == ["https://a.com/docs"]
    assert parse_args(["crawl", "-f", str(seeds_file)]).seeds == ["https://a.com/docs"]


def test_missing_seeds_file_is_a_usage_error(tmp_path):
    import pytest

    with pytest.raises(SystemExit):
        parse_args(["crawl", "--seeds-file", str(tmp_path / "nope.txt")])


def test_serve_subcommand_parses_host_and_port():
    config = parse_args(["serve", "--host", "0.0.0.0", "--port", "9000"])

    assert config == ServeConfig(host="0.0.0.0", port=9000)
    assert parse_args(["serve"]) == ServeConfig()


def test_selector_flag():
    config = parse_args(["crawl", "https://example.com/docs", "--selector", "#content"])

    assert config.selector == "#content"
