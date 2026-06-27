"""User-Agent identity: how getdocs names itself to the sites it fetches."""

from getdocs.identity import PROJECT_URL, build_user_agent


def test_default_user_agent_names_getdocs_and_project_url():
    ua = build_user_agent()
    assert ua.startswith("getdocs/")
    assert f"(+{PROJECT_URL})" in ua


def test_contact_is_appended():
    ua = build_user_agent(contact="you@example.com")
    assert PROJECT_URL in ua
    assert "you@example.com" in ua
    assert ua == f"getdocs/{ua.split('/')[1].split(' ')[0]} (+{PROJECT_URL}; you@example.com)"


def test_override_wins_verbatim():
    assert build_user_agent(contact="ignored@example.com", override="MyBot/9") == "MyBot/9"
