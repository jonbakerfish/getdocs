from getdocs.scope import Scope


def test_default_scope_is_seed_host_plus_path_prefix():
    scope = Scope.from_seeds(["https://example.com/docs/v2"])

    assert scope.allows("https://example.com/docs/v2/api/auth")
    assert scope.allows("https://example.com/docs/v2")
    assert not scope.allows("https://example.com/blog/post")  # outside path prefix
    assert not scope.allows("https://example.com/docs/v22")  # prefix is per-segment
    assert not scope.allows("https://api.example.com/docs/v2")  # subdomain
    assert not scope.allows("https://other.com/docs/v2")  # external
    assert not scope.allows("mailto:hi@example.com")  # non-http


def test_file_seed_scopes_to_its_containing_directory():
    # Seeding a specific Page must still discover its siblings: the final
    # document-file segment is not part of the path prefix.
    scope = Scope.from_seeds(["https://example.com/docs/v2/guide/intro.html"])

    assert scope.allows("https://example.com/docs/v2/guide/intro.html")
    assert scope.allows("https://example.com/docs/v2/guide/setup.html")
    assert scope.allows("https://example.com/docs/v2/guide/api/auth.html")
    assert not scope.allows("https://example.com/docs/v2/reference/intro.html")


def test_version_like_segment_stays_in_prefix():
    # A dotted segment that is not a known page file (e.g. a version) is a
    # directory, so it remains a required prefix segment.
    scope = Scope.from_seeds(["https://example.com/docs/v2.0"])

    assert scope.allows("https://example.com/docs/v2.0/api")
    assert not scope.allows("https://example.com/docs/v3.0/api")


def test_allow_backward_widens_scope_to_whole_host():
    scope = Scope.from_seeds(["https://example.com/docs"], allow_backward=True)

    assert scope.allows("https://example.com/blog/post")
    assert not scope.allows("https://other.com/docs")


def test_allow_subdomains_widens_scope_to_seed_subdomains():
    scope = Scope.from_seeds(["https://example.com/docs"], allow_subdomains=True)

    assert scope.allows("https://api.example.com/docs/auth")
    assert not scope.allows("https://api.example.com/blog")  # path prefix still applies
    assert not scope.allows("https://notexample.com/docs")  # suffix must be a label boundary


def test_path_globs_narrow_and_carve_scope():
    scope = Scope.from_seeds(
        ["https://example.com/docs"],
        include_paths=["/docs/api/*"],
        exclude_paths=["/docs/api/internal/*"],
    )

    assert scope.allows("https://example.com/docs/api/auth")
    assert not scope.allows("https://example.com/docs/guide")  # not in include globs
    assert not scope.allows("https://example.com/docs/api/internal/secrets")  # excluded
