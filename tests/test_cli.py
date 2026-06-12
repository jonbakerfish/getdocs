from pathlib import Path

from getdocs.cli import parse_args


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
