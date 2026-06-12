"""Nav harvesting: capture the original site's Nav Order and Reading Order.

Per ADR-0004, three signals are harvested from each fetched Page's raw HTML
and merged at Crawl end: header tabs and sidebar trees build the Nav Order
(grouping, labels, nesting); prev/next link chains are authoritative for the
linear Reading Order. Everything is plain dicts so harvests serialize
directly into the resume state and the Manifest.

Node shape: {"title": str, "url": str | None, "children": [node, ...]}
Harvest shape: {"tree": [node], "tabs": [node], "prev": url?, "next": url?}
"""

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from getdocs.urlnorm import normalize

_TAB_SELECTORS = [
    ".md-tabs a.md-tabs__link",        # MkDocs Material tabs
    "nav.navbar a.navbar__item[href]",  # Docusaurus navbar
]
_SIDEBAR_SELECTORS = [
    "nav.md-nav--primary",             # MkDocs Material
    "nav.menu",                        # Docusaurus
    "div.sphinxsidebarwrapper",        # Sphinx
    "aside nav",
    "aside",
    '[class*="sidebar"] nav',
]
_PREV_SELECTORS = ['a[rel="prev"]', "a.md-footer__link--prev", "a.pagination-nav__link--prev"]
_NEXT_SELECTORS = ['a[rel="next"]', "a.md-footer__link--next", "a.pagination-nav__link--next"]


def _node(title: str, url: str | None, children: list) -> dict:
    return {"title": title, "url": url, "children": children}


def _own_link(li, nested_ul):
    for a in li.find_all("a", href=True):
        if nested_ul is None or nested_ul not in a.parents:
            return a
    return None


def _parse_list(ul, page_url: str) -> list[dict]:
    nodes = []
    for li in ul.find_all("li", recursive=False):
        nested = li.find("ul")
        link = _own_link(li, nested)
        if link is not None:
            title = link.get_text(strip=True)
            url = urljoin(page_url, link["href"])
        else:
            label = li.find("label")
            title = (label or li).find(string=True, recursive=bool(label))
            title = (title or "").strip()
            url = None
        children = _parse_list(nested, page_url) if nested else []
        if title or children:
            nodes.append(_node(title, url, children))
    return nodes


def _first_href(soup, selectors: list[str], page_url: str) -> str | None:
    for selector in selectors:
        el = soup.select_one(selector)
        if el is not None and el.get("href"):
            return urljoin(page_url, el["href"])
    return None


def harvest_nav(html: str, page_url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    tabs = []
    for selector in _TAB_SELECTORS:
        links = soup.select(selector)
        if links:
            tabs = [
                _node(a.get_text(strip=True), urljoin(page_url, a["href"]), [])
                for a in links
                if a.get("href") and a.get_text(strip=True)
            ]
            break

    tree: list[dict] = []
    for selector in _SIDEBAR_SELECTORS:
        container = soup.select_one(selector)
        if container is not None:
            ul = container if container.name == "ul" else container.find("ul")
            if ul is not None:
                tree = _parse_list(ul, page_url)
                if tree:
                    break

    return {
        "tree": tree,
        "tabs": tabs,
        "prev": _first_href(soup, _PREV_SELECTORS, page_url),
        "next": _first_href(soup, _NEXT_SELECTORS, page_url),
    }


# -- merging ----------------------------------------------------------------


def _count_nodes(nodes: list[dict]) -> int:
    return sum(1 + _count_nodes(n["children"]) for n in nodes)


def _index_tree(nodes: list[dict], index: dict) -> None:
    for node in nodes:
        if node["url"]:
            index.setdefault(normalize(node["url"]), node)
        _index_tree(node["children"], index)


def _first_seen_merge(skeleton: list[dict], index: dict, other: list[dict]) -> None:
    """Attach nodes unseen by the skeleton under their (known) parent."""

    def walk(nodes: list[dict], parent_children: list[dict]):
        for node in nodes:
            norm = normalize(node["url"]) if node["url"] else None
            if norm and norm in index:
                walk(node["children"], index[norm]["children"])
            elif norm:
                copy = _node(node["title"], node["url"], [])
                parent_children.append(copy)
                index[norm] = copy
                walk(node["children"], copy["children"])
            else:
                walk(node["children"], parent_children)

    walk(other, skeleton)


def _attach_tabs(tabs: list[dict], roots: list[dict]) -> list[dict]:
    """Tabs become the top level; existing roots nest under the tab whose
    URL path is their prefix. A root that IS a tab's page merges into it."""
    tab_nodes = [_node(t["title"], t["url"], []) for t in tabs]
    leftovers = []
    for root in roots:
        target = None
        if root["url"]:
            for tab in tab_nodes:
                tab_path = (tab["url"] or "").rstrip("/")
                if tab_path and (root["url"].rstrip("/") + "/").startswith(tab_path + "/"):
                    target = tab
                    break
        if target is None:
            leftovers.append(root)
        elif root["url"] and tab_nodes and normalize(root["url"]) == normalize(target["url"]):
            target["children"].extend(root["children"])
        else:
            target["children"].append(root)
    return tab_nodes + leftovers


def _prune(nodes: list[dict], written: set[str]) -> list[dict]:
    """Un-crawled nodes keep their label but lose the link; label-only nodes
    without children are dropped."""
    result = []
    for node in nodes:
        children = _prune(node["children"], written)
        url = node["url"] if node["url"] and normalize(node["url"]) in written else None
        if url is None and not children:
            continue
        result.append(_node(node["title"], url, children))
    return result


def _traversal(nodes: list[dict]) -> list[str]:
    urls = []
    for node in nodes:
        if node["url"]:
            urls.append(node["url"])
        urls.extend(_traversal(node["children"]))
    return urls


def _chain_sequences(harvests: list[dict], written: set[str]) -> list[str]:
    """Assemble prev/next links into ordered chains of normalized URLs."""
    next_of: dict[str, str] = {}
    has_incoming: set[str] = set()
    for harvest in harvests:
        page = normalize(harvest["page"])
        if harvest.get("next"):
            target = normalize(harvest["next"])
            next_of.setdefault(page, target)
            has_incoming.add(target)
        if harvest.get("prev"):
            source = normalize(harvest["prev"])
            next_of.setdefault(source, page)
            has_incoming.add(page)

    sequence, visited = [], set()
    heads = [p for p in next_of if p not in has_incoming]
    for head in heads:
        current: str | None = head
        while current and current not in visited:
            visited.add(current)
            if current in written:
                sequence.append(current)
            current = next_of.get(current)
    return sequence


def merge_harvests(
    harvests: list[dict], written_urls: list[str]
) -> tuple[list[dict], list[str]]:
    """Merge per-page harvests into (nav tree, reading order).

    harvests: [{"page": url, "tree": [...], "tabs": [...], "prev", "next"}]
    written_urls: Pages actually written, in crawl order (original URLs).
    """
    written = {normalize(u) for u in written_urls}
    original = {normalize(u): u for u in written_urls}

    trees = [h for h in harvests if h["tree"]]
    skeleton: list[dict] = []
    if trees:
        skeleton = max(trees, key=lambda h: _count_nodes(h["tree"]))["tree"]
        index: dict = {}
        _index_tree(skeleton, index)
        for harvest in trees:
            if harvest["tree"] is not skeleton:
                _first_seen_merge(skeleton, index, harvest["tree"])

    tabs = next((h["tabs"] for h in harvests if h["tabs"]), [])
    if tabs:
        skeleton = _attach_tabs(tabs, skeleton)

    nav = _prune(skeleton, written)

    ordered = _chain_sequences(harvests, written)
    for url in _traversal(nav) + written_urls:
        norm = normalize(url)
        if norm in written and norm not in ordered:
            ordered.append(norm)
    reading_order = [original[norm] for norm in dict.fromkeys(ordered)]
    return nav, reading_order
