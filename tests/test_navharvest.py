from getdocs.navharvest import harvest_nav, merge_harvests

MATERIAL_PAGE = """<html><head><title>Setup</title></head><body>
<header class="md-header"></header>
<nav class="md-tabs"><ul>
  <li><a class="md-tabs__link" href="/3.1.0/Products/">Products</a></li>
  <li><a class="md-tabs__link" href="/3.1.0/Software/">Software</a></li>
</ul></nav>
<div class="md-container">
  <nav class="md-nav md-nav--primary">
    <ul class="md-nav__list">
      <li class="md-nav__item"><a class="md-nav__link" href="/3.1.0/Products/">Overview</a></li>
      <li class="md-nav__item md-nav__item--nested">
        <label class="md-nav__link">Metagloves</label>
        <nav class="md-nav"><ul class="md-nav__list">
          <li class="md-nav__item"><a class="md-nav__link" href="/3.1.0/Products/Metagloves/Setup">Setup</a></li>
          <li class="md-nav__item"><a class="md-nav__link" href="/3.1.0/Products/Metagloves/Usage">Usage</a></li>
        </ul></nav>
      </li>
    </ul>
  </nav>
  <main><h1>Setup</h1></main>
</div>
<footer>
  <a class="md-footer__link md-footer__link--prev" href="/3.1.0/Products/">Previous</a>
  <a class="md-footer__link md-footer__link--next" href="/3.1.0/Products/Metagloves/Usage">Next</a>
</footer>
</body></html>"""


def test_material_sidebar_tree_tabs_and_chain_are_harvested():
    harvest = harvest_nav(MATERIAL_PAGE, "https://x.com/3.1.0/Products/Metagloves/Setup")

    assert [t["title"] for t in harvest["tabs"]] == ["Products", "Software"]
    assert harvest["tabs"][0]["url"] == "https://x.com/3.1.0/Products/"

    tree = harvest["tree"]
    assert tree[0]["title"] == "Overview"
    assert tree[0]["url"] == "https://x.com/3.1.0/Products/"
    assert tree[1]["title"] == "Metagloves"
    assert tree[1]["url"] is None  # section label without its own page
    assert [c["title"] for c in tree[1]["children"]] == ["Setup", "Usage"]

    assert harvest["prev"] == "https://x.com/3.1.0/Products/"
    assert harvest["next"] == "https://x.com/3.1.0/Products/Metagloves/Usage"


def test_generic_rel_links_and_plain_nav_lists_are_harvested():
    html = """<html><body>
    <aside><nav><ul>
      <li><a href="/docs/intro">Intro</a>
        <ul><li><a href="/docs/intro/install">Install</a></li></ul>
      </li>
      <li><a href="/docs/api">API</a></li>
    </ul></nav></aside>
    <main><h1>Intro</h1></main>
    <a rel="prev" href="/docs/">Back</a>
    <a rel="next" href="/docs/intro/install">Forward</a>
    </body></html>"""

    harvest = harvest_nav(html, "https://x.com/docs/intro")

    tree = harvest["tree"]
    assert tree[0]["title"] == "Intro"
    assert tree[0]["children"][0]["url"] == "https://x.com/docs/intro/install"
    assert tree[1]["title"] == "API"
    assert harvest["prev"] == "https://x.com/docs/"
    assert harvest["next"] == "https://x.com/docs/intro/install"


def test_page_without_nav_harvests_empty():
    harvest = harvest_nav("<html><body><main><h1>Hi</h1></main></body></html>", "https://x.com/p")

    assert harvest == {"tree": [], "tabs": [], "prev": None, "next": None}


def node(title, url=None, children=()):
    return {"title": title, "url": url, "children": list(children)}


def harvest(page, tree=(), tabs=(), prev=None, next=None):
    return {"page": page, "tree": list(tree), "tabs": list(tabs), "prev": prev, "next": next}


def test_largest_tree_is_skeleton_and_unseen_branches_merge_in():
    big = [
        node("A", "https://x.com/d/a"),
        node("B", "https://x.com/d/b", [node("B1", "https://x.com/d/b/1")]),
    ]
    other = [node("B", "https://x.com/d/b", [node("B2", "https://x.com/d/b/2")])]
    written = ["https://x.com/d/a", "https://x.com/d/b", "https://x.com/d/b/1", "https://x.com/d/b/2"]

    nav, order = merge_harvests(
        [harvest("https://x.com/d/b", tree=other), harvest("https://x.com/d/a", tree=big)],
        written,
    )

    b_children = [c["title"] for c in nav[1]["children"]]
    assert b_children == ["B1", "B2"]  # first-seen merge under the known parent
    assert order == written[:2] + ["https://x.com/d/b/1", "https://x.com/d/b/2"]


def test_chain_wins_reading_sequence_over_tree_order():
    tree = [node("A", "https://x.com/d/a"), node("B", "https://x.com/d/b"), node("C", "https://x.com/d/c")]
    harvests = [
        harvest("https://x.com/d/a", tree=tree, next="https://x.com/d/c"),
        harvest("https://x.com/d/c", prev="https://x.com/d/a", next="https://x.com/d/b"),
        harvest("https://x.com/d/b", prev="https://x.com/d/c"),
    ]
    written = ["https://x.com/d/a", "https://x.com/d/b", "https://x.com/d/c"]

    nav, order = merge_harvests(harvests, written)

    assert order == ["https://x.com/d/a", "https://x.com/d/c", "https://x.com/d/b"]


def test_orphans_append_in_crawl_order_and_uncrawled_nodes_lose_links():
    tree = [
        node("A", "https://x.com/d/a"),
        node("Gone section", "https://x.com/d/gone", [node("A1", "https://x.com/d/a1")]),
        node("Dead leaf", "https://x.com/d/dead"),
    ]
    written = ["https://x.com/d/a", "https://x.com/d/a1", "https://x.com/d/orphan"]

    nav, order = merge_harvests([harvest("https://x.com/d/a", tree=tree)], written)

    assert nav[1]["title"] == "Gone section"
    assert nav[1]["url"] is None  # label kept, link dropped
    assert nav[1]["children"][0]["url"] == "https://x.com/d/a1"
    assert all(n["title"] != "Dead leaf" for n in nav)  # label-only leaf dropped
    assert order == ["https://x.com/d/a", "https://x.com/d/a1", "https://x.com/d/orphan"]


def test_tabs_become_roots_and_adopt_matching_subtrees():
    tabs = [node("Products", "https://x.com/p/"), node("Software", "https://x.com/s/")]
    tree = [node("Products", "https://x.com/p/", [node("Gloves", "https://x.com/p/gloves")])]
    written = ["https://x.com/p/", "https://x.com/p/gloves", "https://x.com/s/"]

    nav, _ = merge_harvests([harvest("https://x.com/p/", tree=tree, tabs=tabs)], written)

    assert [n["title"] for n in nav] == ["Products", "Software"]
    assert [c["title"] for c in nav[0]["children"]] == ["Gloves"]  # merged, not nested twice
