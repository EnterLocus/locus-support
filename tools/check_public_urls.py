#!/usr/bin/env python3
"""Verify the published Locus routes without credentials or session state."""

from __future__ import annotations

import argparse
import time
import urllib.error
import urllib.parse
import urllib.request


PUBLIC_SITE_PATHS = (
    "",
    "support/",
    "privacy/",
    "pricing/",
    "experimental-mac-virtual-display/",
    "create-your-own-place/",
    "package-format/",
    "schemas/locusplace-v1.schema.json",
    "schemas/locusplace-provenance-v1.schema.json",
    "tools/validate_locusplace.py",
    "tools/pack_locusplace.py",
)


def public_urls(base: str) -> list[str]:
    normalized = base.rstrip("/") + "/"
    return [urllib.parse.urljoin(normalized, path) for path in PUBLIC_SITE_PATHS]


def fetch(url: str, *, timeout: float) -> None:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Locus-Public-Launch-Check/1"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f"{url}: HTTP {response.status}")
        response.read(1)


def verify(base: str, *, attempts: int = 6, timeout: float = 15) -> None:
    pending = public_urls(base)
    failures: dict[str, str] = {}
    for attempt in range(attempts):
        failures = {}
        for url in pending:
            try:
                fetch(url, timeout=timeout)
            except (OSError, RuntimeError, urllib.error.URLError) as error:
                failures[url] = str(error)
        if not failures:
            return
        pending = list(failures)
        if attempt + 1 < attempts:
            time.sleep(3)
    details = "\n".join(f"- {url}: {error}" for url, error in failures.items())
    raise RuntimeError(f"public routes did not load signed out:\n{details}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base",
        default="https://enterlocus.github.io/locus-support/",
    )
    args = parser.parse_args()
    verify(args.base)
    print(f"Verified {len(PUBLIC_SITE_PATHS)} signed-out public routes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
