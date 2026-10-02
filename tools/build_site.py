"""Stage English and localized static pages without changing source HTML."""
from __future__ import annotations

import html
import json
from pathlib import Path
import posixpath
import re
import shutil
from urllib.parse import urlsplit, urlunsplit
import xml.etree.ElementTree as ET

from localization import (LOCALES, TRANSLATED_LOCALES, ATTRIBUTE_NAMES, SKIPPED_TAGS,
                          VOID_TAGS, _ATTR_RE, _TAG_RE, _HTML_PART_RE, load_catalog,
                          has_translation, public_html_files, runtime_strings, translate)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / '.site'
EXCLUDED = {'.git', '.github', '.claude', '.scratch', '.site', 'node_modules', '__pycache__',
            'test-results', 'playwright-report', 'tests', 'package.json', 'package-lock.json',
            'playwright.config.js', 'localization'}
SITE = 'https://enterlocus.com'


def page_url(relative: Path, locale: str = 'en') -> str:
    directory = relative.parent.as_posix()
    suffix = '' if directory == '.' else f'/{directory}'
    return f'{SITE}{"" if locale == "en" else "/" + locale}{suffix}/'


def _output_path(relative: Path, locale: str) -> Path:
    return OUTPUT / (relative if locale == 'en' else Path(locale) / relative)


def _translated_value(value: str, catalog: dict[str, str]) -> str:
    if not has_translation(value, catalog):
        return value
    return html.escape(translate(value, catalog), quote=True)


def _local_url(value: str, relative: Path, locale: str) -> str:
    """Keep public pages in their locale; make all other local files root URLs."""
    parsed = urlsplit(html.unescape(value))
    if parsed.scheme or parsed.netloc or not parsed.path:
        return value
    if parsed.path.startswith('/'):
        candidate = parsed.path.lstrip('/')
    else:
        candidate = posixpath.normpath(posixpath.join(relative.parent.as_posix(), parsed.path))
    candidate = candidate.lstrip('/')
    candidate_path = ROOT / candidate
    html_target = candidate_path / 'index.html' if candidate_path.is_dir() else candidate_path
    if html_target.is_file() and html_target.suffix == '.html':
        target = page_url(html_target.relative_to(ROOT), locale).removeprefix(SITE)
    else:
        target = '/' + candidate
    return urlunsplit(('', '', target, parsed.query, parsed.fragment))


def _rewrite_tag(part: str, relative: Path, locale: str, catalog: dict[str, str]) -> str:
    match = _TAG_RE.match(part)
    if not match or match.group(1):
        return part
    tag = match.group(2).lower()
    attrs = {name.lower(): html.unescape(value) for name, _quote, value in _ATTR_RE.findall(part)}

    def replace(attribute_match: re.Match[str]) -> str:
        name, quote, value = attribute_match.groups()
        lower = name.lower()
        meta_copy = (attrs.get('name') or attrs.get('property') or '').lower()
        if lower in ATTRIBUTE_NAMES or (tag == 'meta' and lower == 'content' and meta_copy in {
                'description', 'og:title', 'og:description', 'twitter:title', 'twitter:description'}):
            value = _translated_value(value, catalog)
        elif locale != 'en' and lower in {'href', 'src'}:
            value = _local_url(value, relative, locale)
        return f'{name}={quote}{value}{quote}'

    return _ATTR_RE.sub(replace, part)


def _translate_document(source: str, relative: Path, locale: str, catalog: dict[str, str]) -> str:
    parts = []
    stack: list[str] = []
    for part in _HTML_PART_RE.split(source):
        if not part:
            continue
        if part.startswith('<!--') or part.startswith('<!'):
            parts.append(part)
            continue
        match = _TAG_RE.match(part)
        if match:
            closing, tag = match.groups()
            tag = tag.lower()
            if closing:
                parts.append(part)
                if stack and stack[-1] == tag:
                    stack.pop()
                continue
            parts.append(_rewrite_tag(part, relative, locale, catalog))
            if tag not in VOID_TAGS and not part.rstrip().endswith('/>'):
                stack.append(tag)
        elif not any(tag in SKIPPED_TAGS for tag in stack):
            parts.append(_translated_value(part, catalog))
        else:
            parts.append(part)
    document = ''.join(parts)
    document = re.sub(r'(<html\b[^>]*\blang=)(["\'])[^"\']*\2',
                      lambda match: f'{match.group(1)}"{locale}"', document, count=1, flags=re.I)
    document = re.sub(r'\s*<link\b(?=[^>]*\brel=["\']canonical["\'])[^>]*>', '', document, flags=re.I)
    document = re.sub(r'\s*<link\b(?=[^>]*\brel=["\']alternate["\'])(?=[^>]*\bhreflang=)[^>]*>', '', document, flags=re.I)
    document = re.sub(r'(<meta\s+[^>]*property=("|\')og:url\2[^>]*content=("|\'))[^"\']*(["\'])',
                      lambda match: match.group(1) + page_url(relative, locale) + match.group(4), document,
                      flags=re.I)
    alternates = ''.join(
        f'<link rel="alternate" hreflang="{tag}" href="{page_url(relative, tag)}">'
        for tag in LOCALES)
    alternates += f'<link rel="alternate" hreflang="x-default" href="{page_url(relative)}">'
    document = document.replace('</head>',
                                f'<link rel="canonical" href="{page_url(relative, locale)}">{alternates}</head>', 1)
    picker = (
        '<label class="language-picker"><span class="visually-hidden">'
        f'{_translated_value("Language", catalog)}</span><select data-language-select '
        f'aria-label="{_translated_value("Language", catalog)}">'
        f'<option value="system">{_translated_value("System", catalog)}</option>'
        '<option value="en">English</option><option value="zh-Hans">简体中文</option>'
        '<option value="zh-Hant">繁體中文</option><option value="ja">日本語</option>'
        '<option value="ko">한국어</option><option value="de">Deutsch</option>'
        '<option value="fr">Français</option><option value="es">Español</option></select></label>'
    )
    document = re.sub(r'(<header\b[^>]*class=("|\')[^"\']*site-header[^"\']*\2.*?<nav\b[^>]*>.*?)(</nav>)',
                      lambda match: match.group(1) + picker + match.group(3), document,
                      count=1, flags=re.S | re.I)
    config = json.dumps({'locale': locale, 'strings': runtime_strings(catalog)}, ensure_ascii=False).replace('</', '<\\/')
    shared = (f'<link rel="stylesheet" href="/assets/language.css">'
              f'<script>window.LocusLocalization={config};</script>'
              '<script src="/assets/language.js" defer></script>')
    return document.replace('</head>', shared + '</head>', 1)


def _build_sitemap() -> None:
    source = ET.parse(ROOT / 'sitemap.xml')
    root = source.getroot()
    namespace = '{http://www.sitemaps.org/schemas/sitemap/0.9}'
    existing = [node.find(f'{namespace}loc').text for node in root.findall(f'{namespace}url')]
    for loc in existing:
        relative = Path(urlsplit(loc).path.lstrip('/') or '.') / 'index.html'
        for locale in TRANSLATED_LOCALES:
            url = ET.SubElement(root, f'{namespace}url')
            ET.SubElement(url, f'{namespace}loc').text = page_url(relative, locale)
    ET.register_namespace('', 'http://www.sitemaps.org/schemas/sitemap/0.9')
    source.write(OUTPUT / 'sitemap.xml', encoding='utf-8', xml_declaration=True)


def build() -> None:
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    shutil.copytree(ROOT, OUTPUT, ignore=lambda directory, names:
                    [name for name in names if name in EXCLUDED])
    pages = public_html_files(ROOT)
    catalogs = {locale: load_catalog(ROOT, locale) for locale in LOCALES}
    for relative in pages:
        source = (ROOT / relative).read_text(encoding='utf-8')
        for locale in LOCALES:
            target = _output_path(relative, locale)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(_translate_document(source, relative, locale, catalogs[locale]), encoding='utf-8')
    _build_sitemap()


if __name__ == '__main__':
    build()
