"""Source-first: before crawling, check whether the docs site is open-source.

Most documentation generators embed a link back to the repository that hosts
the docs source — MkDocs/Material and Docusaurus render an "Edit this page"
link, Sphinx/Read-the-Docs an "Edit on GitHub". When we can find that repo we
clone it and write an mkdocs.yml so the docs can be served locally, which is
faster and higher-fidelity than crawling the rendered HTML.

Detection is a pure function over the seed page's HTML (`detect_repo`); the
network and git side-effects live in `fetch_html`, `clone_repo`, and the
`clone_source_for` orchestrator the CLI calls before `run_crawl`.
"""

import importlib.util
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import yaml
from bs4 import BeautifulSoup

from getdocs.config import CrawlConfig
from getdocs.identity import build_user_agent
from getdocs.outcome import CloneOutcome

# Hosts whose /ORG/REPO paths we recognize as clonable repositories.
_GIT_HOSTS = {"github.com", "gitlab.com", "bitbucket.org", "codeberg.org"}

# First path segments on github.com that are product pages, not orgs/users.
_RESERVED_OWNERS = {
    "about", "apps", "collections", "contact", "customer-stories", "explore",
    "features", "join", "login", "marketplace", "new", "notifications",
    "organizations", "orgs", "pricing", "readme", "security", "settings",
    "site", "sponsors", "topics",
}

# Sub-paths a repo URL deep-links through (github.com/o/r/edit/main/docs/x.md).
_REPO_SUBPATHS = {"edit", "blob", "tree", "raw", "commits", "blame", "wiki"}

# Where doc sources commonly live inside a repo, in preference order.
_DOCS_CANDIDATES = ["docs", "doc", "documentation", "site/docs", "website/docs", "content"]


def repo_root_from_url(url: str) -> str | None:
    """Reduce any URL on a known Git host to its canonical repo root, or None.

    https://github.com/org/repo/edit/main/docs/x.md -> https://github.com/org/repo
    Anything off a known host, or shallower than /ORG/REPO, returns None.
    """
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        return None
    host = parts.netloc.lower().rsplit("@", 1)[-1].split(":", 1)[0]
    if host.startswith("www."):
        host = host[4:]
    if host not in _GIT_HOSTS:
        return None
    segments = [s for s in parts.path.split("/") if s]
    if len(segments) < 2:
        return None
    owner, repo = segments[0], segments[1]
    if owner.lower() in _RESERVED_OWNERS:
        return None
    if repo.endswith(".git"):
        repo = repo[:-4]
    if not repo:
        return None
    return f"https://{host}/{owner}/{repo}"


def _link_score(url: str, blob: str) -> int:
    """Rank a repo link by how strongly it signals 'this is the docs source'.

    An explicit "edit this page" affordance is the gold signal; a "source"/
    "github" label is next; a bare deep-link into the repo beats a plain
    repo-root link that might just be a footer cross-reference.
    """
    if "edit" in blob:
        return 100
    if any(word in blob for word in ("source", "github", "gitlab", "view on", "improve")):
        return 80
    segments = [s for s in urlsplit(url).path.split("/") if s]
    if len(segments) >= 3 and segments[2] in _REPO_SUBPATHS:
        return 60
    return 20


def detect_repo(html: str, base_url: str = "") -> str | None:
    """Find the repository a docs page links back to, as a canonical repo URL.

    Scans anchors for links onto a known Git host, scores each by how clearly
    it names the docs source, and returns the highest-scoring repo root
    (ties broken by how often that repo is linked). None when nothing matches.
    """
    soup = BeautifulSoup(html, "html.parser")
    # root -> [best score seen, link count]
    candidates: dict[str, list[int]] = {}
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if base_url and not urlsplit(href).scheme:
            href = urljoin(base_url, href)
        root = repo_root_from_url(href)
        if not root:
            continue
        blob = " ".join([
            anchor.get_text(" ", strip=True),
            anchor.get("title", ""),
            " ".join(anchor.get("class") or []),
            " ".join(anchor.get("rel") or []),
            anchor.get("aria-label", ""),
        ]).lower()
        score = _link_score(href, blob)
        entry = candidates.setdefault(root, [0, 0])
        entry[0] = max(entry[0], score)
        entry[1] += 1
    if not candidates:
        return None
    return max(candidates, key=lambda root: (candidates[root][0], candidates[root][1]))


def fetch_html(
    url: str, user_agent: str | None = None,
    timeout: float = 15.0, max_bytes: int = 3_000_000,
) -> str | None:
    """Fetch a single page's HTML for detection; None on any error/non-HTML."""
    request = urllib.request.Request(
        url, headers={"User-Agent": user_agent or build_user_agent()}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            content_type = response.headers.get("Content-Type", "").lower()
            if any(kind in content_type for kind in ("json", "image/", "pdf", "octet-stream")):
                return None
            data = response.read(max_bytes)
    except Exception:
        return None
    return data.decode("utf-8", errors="replace")


def clone_repo(repo_url: str, dest_parent: Path, timeout: float = 180.0) -> Path | None:
    """Shallow-clone repo_url under dest_parent; return the clone dir or None.

    Returns an existing clone untouched (idempotent for re-runs); None when git
    is missing or the clone fails.
    """
    if shutil.which("git") is None:
        return None
    name = repo_url.rstrip("/").rsplit("/", 1)[-1]
    if name.endswith(".git"):
        name = name[:-4]
    dest = dest_parent / name
    if dest.exists():
        return dest if (dest / ".git").exists() else None
    clone_url = repo_url if repo_url.endswith(".git") else repo_url + ".git"
    dest_parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", clone_url, str(dest)],
            check=True, capture_output=True, timeout=timeout,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return None
    return dest


def find_docs_dir(repo_dir: Path) -> Path | None:
    """Locate the markdown docs source inside a cloned repo, or None."""
    for candidate in _DOCS_CANDIDATES:
        path = repo_dir / candidate
        if path.is_dir() and (any(path.rglob("*.md")) or any(path.rglob("*.mdx"))):
            return path
    if any(repo_dir.glob("*.md")):
        return repo_dir
    return None


def write_mkdocs_config(output_dir: Path, docs_dir: Path, site_name: str) -> Path:
    """Write an mkdocs.yml in output_dir that serves docs_dir locally."""
    output_dir.mkdir(parents=True, exist_ok=True)
    theme = "material" if importlib.util.find_spec("material") else "mkdocs"
    config = {
        "site_name": site_name,
        "docs_dir": str(docs_dir.resolve()),
        "theme": {"name": theme},
        "use_directory_urls": True,
    }
    path = output_dir / "mkdocs.yml"
    path.write_text(yaml.safe_dump(config, sort_keys=False, allow_unicode=True))
    return path


def _repo_identity(repo_url: str) -> str:
    """Short owner/repo identity for a canonical repo URL ("acme/docs")."""
    return "/".join(s for s in urlsplit(repo_url).path.split("/") if s)


def clone_source_for(config: CrawlConfig) -> CloneOutcome | None:
    """Try to satisfy a crawl by cloning the docs' source repo instead.

    Returns a CloneOutcome when the site is open-source and was cloned (the
    caller should then skip crawling and report it); None to fall back to
    crawling. Progress is reported on stderr (stdout is the jsonl stream).
    """
    if not config.seeds:
        return None
    seed = config.seeds[0]
    if urlsplit(seed).scheme not in ("http", "https"):
        return None

    host = urlsplit(seed).netloc or seed
    print(f"checking whether {host} is open-source…", file=sys.stderr)
    html = fetch_html(seed, build_user_agent(config.contact, config.user_agent))
    if html is None:
        print("could not fetch the seed page — crawling instead", file=sys.stderr)
        return None
    repo_url = detect_repo(html, seed)
    if repo_url is None:
        print("no source repository linked from the page — crawling instead", file=sys.stderr)
        return None

    print(f"found source repository {repo_url} — cloning…", file=sys.stderr)
    repo_dir = clone_repo(repo_url, config.output_dir)
    if repo_dir is None:
        print("clone failed (git missing or repo unreachable) — crawling instead", file=sys.stderr)
        return None
    repo = _repo_identity(repo_url)

    own_config = repo_dir / "mkdocs.yml"
    if own_config.exists():
        print(f"cloned to {repo_dir} (ships its own mkdocs.yml)", file=sys.stderr)
        print(f"serve it with: mkdocs serve -f {own_config}", file=sys.stderr)
        return CloneOutcome(repo=repo, output_dir=repo_dir, mkdocs_config=own_config)

    docs_dir = find_docs_dir(repo_dir)
    if docs_dir is None:
        print(f"cloned to {repo_dir}, but found no markdown docs to serve", file=sys.stderr)
        return CloneOutcome(repo=repo, output_dir=repo_dir, mkdocs_config=None)

    written = write_mkdocs_config(config.output_dir, docs_dir, host)
    print(f"cloned to {repo_dir}; wrote {written}", file=sys.stderr)
    print(f"serve it with: mkdocs serve -f {written}", file=sys.stderr)
    return CloneOutcome(repo=repo, output_dir=repo_dir, mkdocs_config=written)
