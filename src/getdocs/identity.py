"""How getdocs identifies itself to the sites it fetches.

One honest, descriptive User-Agent for every request — both the pre-crawl
source check (`source.py`) and the Scrapy crawl (`engine.py`) — so a site
operator reading their logs can tell it's getdocs and, when the user opts in
with `--contact`, reach whoever is crawling. Identifying yourself is crawling
etiquette (RFC 9309), not a hard requirement, so `contact` stays optional.
"""

import importlib.metadata

PROJECT_URL = "https://github.com/jonbakerfish/getdocs"


def _version() -> str:
    try:
        return importlib.metadata.version("getdocs")
    except importlib.metadata.PackageNotFoundError:
        return "0.0.0"


def build_user_agent(contact: str | None = None, override: str | None = None) -> str:
    """The User-Agent getdocs sends.

    `override` wins verbatim when given; otherwise the UA names getdocs and its
    version, with the project URL and — when supplied — the user's contact:
        getdocs/0.1.0 (+https://github.com/jonbakerfish/getdocs; you@example.com)
    """
    if override:
        return override
    detail = PROJECT_URL if not contact else f"{PROJECT_URL}; {contact}"
    return f"getdocs/{_version()} (+{detail})"
