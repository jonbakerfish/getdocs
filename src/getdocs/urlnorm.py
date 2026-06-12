"""URL normalization for frontier dedup.

Two URLs that normalize identically are the same Page. rel=canonical is
deliberately NOT part of this (ADR-0003).
"""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TRACKING_PREFIXES = ("utm_",)
_TRACKING_PARAMS = {"fbclid", "gclid", "msclkid", "mc_cid", "mc_eid"}
_DEFAULT_PORTS = {"http": "80", "https": "443"}


def _is_tracking(param: str) -> bool:
    return param in _TRACKING_PARAMS or param.startswith(_TRACKING_PREFIXES)


def normalize(url: str) -> str:
    parts = urlsplit(url)
    scheme = parts.scheme.lower()

    host = parts.hostname.lower() if parts.hostname else ""
    if parts.port is not None and str(parts.port) != _DEFAULT_PORTS.get(scheme):
        host = f"{host}:{parts.port}"

    path = parts.path
    if path.endswith("/"):
        path = path.rstrip("/")

    query = urlencode(
        sorted((k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not _is_tracking(k))
    )

    return urlunsplit((scheme, host, path, query, ""))
