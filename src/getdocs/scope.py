"""Scope: decides whether a discovered URL belongs to a Crawl.

Default: same host + path prefix of each Seed URL, loosened by explicit
overrides. Discovery method never matters — Scope gates fetching no matter
how a URL was found.

A Seed URL whose final path segment names a document file (``guide.html``,
``parameters.html``, …) scopes to its *containing directory*, not to that one
file — otherwise seeding a specific Page could never discover its siblings.
"""

from dataclasses import dataclass
from fnmatch import fnmatch
from urllib.parse import urlsplit

# Extensions that mark a final path segment as a document leaf rather than a
# directory, so the Scope prefix drops it (see module docstring). Version-like
# segments (``v2``, ``v2.0``) carry no such extension and stay in the prefix.
_PAGE_EXTENSIONS = frozenset(
    {"html", "htm", "xhtml", "shtml", "php", "asp", "aspx", "jsp", "md", "rst"}
)


def _segments(path: str) -> list[str]:
    return [s for s in path.split("/") if s]


def _prefix_segments(path: str) -> list[str]:
    """The scoping segments of a Seed path: its segments minus a trailing
    document-file segment (``.../revo2/parameters.html`` -> ``.../revo2``)."""
    segments = _segments(path)
    if segments:
        _, dot, ext = segments[-1].rpartition(".")
        if dot and ext.lower() in _PAGE_EXTENSIONS:
            segments = segments[:-1]
    return segments


@dataclass(frozen=True)
class _SeedRule:
    host: str
    path_segments: tuple[str, ...]

    def matches_host(self, host: str, allow_subdomains: bool) -> bool:
        if host == self.host:
            return True
        return allow_subdomains and host.endswith("." + self.host)

    def matches_path(self, segments: list[str], allow_backward: bool) -> bool:
        if allow_backward:
            return True
        return tuple(segments[: len(self.path_segments)]) == self.path_segments


@dataclass(frozen=True)
class Scope:
    rules: tuple[_SeedRule, ...]
    allow_backward: bool = False
    allow_subdomains: bool = False
    include_paths: tuple[str, ...] = ()
    exclude_paths: tuple[str, ...] = ()

    @classmethod
    def from_seeds(
        cls,
        seeds: list[str],
        allow_backward: bool = False,
        allow_subdomains: bool = False,
        include_paths: list[str] | tuple[str, ...] = (),
        exclude_paths: list[str] | tuple[str, ...] = (),
    ) -> "Scope":
        rules = []
        for seed in seeds:
            parts = urlsplit(seed)
            rules.append(
                _SeedRule(
                    host=parts.netloc.lower(),
                    path_segments=tuple(_prefix_segments(parts.path)),
                )
            )
        return cls(
            rules=tuple(rules),
            allow_backward=allow_backward,
            allow_subdomains=allow_subdomains,
            include_paths=tuple(include_paths),
            exclude_paths=tuple(exclude_paths),
        )

    def allows(self, url: str) -> bool:
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https"):
            return False
        host = parts.netloc.lower()
        segments = _segments(parts.path)

        in_seed_scope = any(
            rule.matches_host(host, self.allow_subdomains)
            and rule.matches_path(segments, self.allow_backward)
            for rule in self.rules
        )
        if not in_seed_scope:
            return False

        path = parts.path or "/"
        if self.include_paths and not any(fnmatch(path, g) for g in self.include_paths):
            return False
        if any(fnmatch(path, g) for g in self.exclude_paths):
            return False
        return True
