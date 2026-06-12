from getdocs.urlnorm import normalize


def test_fragment_tracking_params_case_and_trailing_slash_collapse():
    canonical = normalize("https://example.com/docs/auth")

    assert normalize("https://EXAMPLE.com/docs/auth#section") == canonical
    assert normalize("https://example.com/docs/auth/") == canonical
    assert normalize("https://example.com/docs/auth?utm_source=x&fbclid=y") == canonical
    assert normalize("HTTPS://example.com:443/docs/auth") == canonical


def test_meaningful_query_params_survive_and_are_order_insensitive():
    a = normalize("https://example.com/page?id=42&lang=en")
    b = normalize("https://example.com/page?lang=en&id=42")

    assert a == b
    assert "id=42" in a and "lang=en" in a
    assert normalize("https://example.com/page?id=43") != a


def test_root_path_is_preserved():
    assert normalize("https://example.com/") == normalize("https://example.com")
