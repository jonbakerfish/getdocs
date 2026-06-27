# getdocs privacy

The getdocs plugin and CLI run entirely on your machine. getdocs collects no
personal data, contains no telemetry or analytics, and sends nothing to the
author or any third party.

The only network requests it makes are:

- fetching the getdocs package from PyPI via `uvx`, and
- fetching the documentation URL(s) you explicitly give it.

All output — markdown Pages, the `crawl.json` Manifest, or a cloned source
repository — is written only to the local output directory you choose.
