from pathlib import Path

from getdocs.cli import parse_args


def test_crawl_args_become_crawl_config():
    config = parse_args(["crawl", "https://example.com/docs/page", "-o", "./out"])

    assert config.seeds == ["https://example.com/docs/page"]
    assert config.output_dir == Path("./out")
