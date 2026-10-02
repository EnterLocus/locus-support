"""Shared source extraction and safe catalog lookups for the staged site."""
from __future__ import annotations

from collections import Counter
import html
from pathlib import Path
import json
import re

LOCALES = ("en", "zh-Hans", "zh-Hant", "ja", "ko", "de", "fr", "es")
TRANSLATED_LOCALES = LOCALES[1:]
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
SKIPPED_TAGS = {"code", "pre", "script", "style"}
ATTRIBUTE_NAMES = {"alt", "aria-label", "title", "placeholder"}

# These strings originate in dynamically created UI rather than source HTML.
RUNTIME_SOURCE_STRINGS = (
    "Language", "Follow system", "Search", "Search Locus", "Close search", "Search results",
    "Search the website", "Search questions, guides, and more…",
    "Find answers across FAQ and guides.", "Searching…", "{count} result",
    "{count} results", "No results. Try another word, or browse the FAQ.",
    "Search is unavailable right now. Try again, or browse the FAQ.",
    "Browse the FAQ", "Try {first}, {second}, or {third}.", "lying down",
    "Room Lights", "imports",
)

_TOKEN_RE = re.compile(r"\{[^{}]+\}")
_HTML_PART_RE = re.compile(r"(?s)(<!--.*?-->|<![^>]*>|</?[^>]+>)")
_TAG_RE = re.compile(r"^<\s*(/?)\s*([A-Za-z][\w:-]*)")
_ATTR_RE = re.compile(r"\b([\w:-]+)\s*=\s*(['\"])(.*?)\2", re.DOTALL)
_VERSION_RE = re.compile(r"^v?\d+(?:\.\d+)+(?:\s+(?:or|and)\s+(?:later|earlier))?$", re.I)
_CODE_LIKE_RE = re.compile(r"(?:[_/\\]|\.(?:zip|json|js|css|html|md|usdz|jpg|png|heic|m4a|wav)|\b[a-f0-9]{8}-[a-f0-9-]{27,}\b)", re.I)
_LITERAL_NAMES = {
    "Locus", "Apple Vision Pro", "Package v2", "Apache License 2.0",
    "Creative Commons Attribution 4.0 International", "CC0 1.0",
}


def public_html_files(root: Path) -> list[Path]:
    excluded = {".git", ".site", ".scratch", "node_modules", "tests", "test-results", "playwright-report"}
    return sorted(path.relative_to(root) for path in root.rglob("*.html")
                  if not any(part in excluded for part in path.relative_to(root).parts))


def _key(value: str) -> str:
    return html.unescape(value).strip()


def is_translatable_source(value: str) -> bool:
    """Reject symbols and code/product literals that should remain exact."""
    source = _key(value)
    if not source or source in _LITERAL_NAMES:
        return False
    if not any(character.isalpha() for character in source):
        return False
    technical_literal = re.fullmatch(r"[A-Za-z0-9_.:/\\<>@+-]+", source) and _CODE_LIKE_RE.search(source)
    return not _VERSION_RE.fullmatch(source) and not technical_literal


def _translatable_attribute(tag: str, attrs: dict[str, str], name: str) -> bool:
    if name in ATTRIBUTE_NAMES:
        return True
    if tag != "meta" or name != "content":
        return False
    kind = (attrs.get("name") or attrs.get("property") or "").lower()
    return kind in {"description", "og:title", "og:description", "twitter:title", "twitter:description"}


def _sources_in_html(source: str) -> set[str]:
    strings: set[str] = set()
    stack: list[str] = []
    for part in _HTML_PART_RE.split(source):
        if not part:
            continue
        if part.startswith("<!--") or part.startswith("<!"):
            continue
        match = _TAG_RE.match(part)
        if not match:
            if not any(tag in SKIPPED_TAGS for tag in stack):
                key = _key(part)
                if is_translatable_source(key):
                    strings.add(key)
            continue
        closing, tag = match.groups()
        tag = tag.lower()
        if closing:
            if stack and stack[-1] == tag:
                stack.pop()
            continue
        attrs = {name.lower(): html.unescape(value) for name, _quote, value in _ATTR_RE.findall(part)}
        if not any(parent in SKIPPED_TAGS for parent in stack):
            for name, value in attrs.items():
                if _translatable_attribute(tag, attrs, name):
                    key = _key(value)
                    if is_translatable_source(key):
                        strings.add(key)
        if tag not in VOID_TAGS and not part.rstrip().endswith("/>"):
            stack.append(tag)
    return strings


def extract_sources(root: Path) -> dict[str, object]:
    """Return deterministic catalog keys and the pages that use each set."""
    pages = {}
    all_strings = set(RUNTIME_SOURCE_STRINGS)
    for relative in public_html_files(root):
        keys = _sources_in_html((root / relative).read_text(encoding="utf-8"))
        pages[relative.as_posix()] = sorted(keys)
        all_strings.update(keys)
    return {"strings": sorted(all_strings), "pages": dict(sorted(pages.items()))}


def load_catalog(root: Path, locale: str) -> dict[str, str]:
    if locale == "en":
        return {}
    path = root / "localization" / f"{locale}.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("language") != locale or not isinstance(data.get("strings"), dict):
        raise ValueError(f"{path} must contain language={locale!r} and a strings object")
    catalog = data["strings"]
    for source, translated in catalog.items():
        if not isinstance(source, str) or not isinstance(translated, str):
            raise ValueError(f"{path} strings must map strings to strings")
        if translated.strip() and Counter(_TOKEN_RE.findall(source)) != Counter(_TOKEN_RE.findall(translated)):
            raise ValueError(f"{path} does not retain interpolation tokens for {source!r}")
    return catalog


def has_translation(value: str, catalog: dict[str, str]) -> bool:
    key = _key(value)
    return is_translatable_source(key) and bool(catalog.get(key, "").strip())


def translate(value: str, catalog: dict[str, str]) -> str:
    """Translate only the trimmed decoded key, retaining source whitespace."""
    decoded = html.unescape(value)
    key = decoded.strip()
    if not has_translation(key, catalog):
        return value
    start = decoded[:len(decoded) - len(decoded.lstrip())]
    end = decoded[len(decoded.rstrip()):]
    return start + catalog[key] + end


def runtime_strings(catalog: dict[str, str]) -> dict[str, str]:
    return {source: catalog[source] if has_translation(source, catalog) else source
            for source in RUNTIME_SOURCE_STRINGS}
