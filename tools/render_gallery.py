"""Render the public Gallery from the catalog-owned public manifest."""
from __future__ import annotations

import html
import json
from pathlib import Path
from urllib.parse import quote
import xml.etree.ElementTree as ET

from localization import LOCALES

SITE = "https://enterlocus.com"
APP_STORE = "https://apps.apple.com/app/id6802168265"

COPY = {
    "en": {"gallery": "Gallery", "eyebrow": "Locus Gallery", "title": "Find a place for what’s next.",
           "intro": "Browse the Views and Rooms available in Locus.", "filters": "Filter Places",
           "search": "Search Places", "search_hint": "Search by name or mood", "all_places": "All Places",
           "views": "Views", "rooms": "Rooms", "all_access": "All access", "free": "Free",
           "supporter": "Supporter", "animated": "Animated", "sound": "With sound", "reset": "Reset filters",
           "places": "All Places", "series": "Series", "count": "{count} places", "empty_title": "No places match these filters.",
           "empty_copy": "Try another search or reset filters.", "view": "View", "room": "Room",
           "get_app": "Get Locus on the App Store", "back": "Back to Gallery", "members": "Places in this series",
           "series_intro": "Explore related Places in Locus.", "available": "Available in Locus {version}."},
    "zh-Hans": {"gallery": "画廊", "eyebrow": "Locus 画廊", "title": "为下一刻找到一个地方。", "intro": "浏览 Locus 中可用的 View 和 Room。", "filters": "筛选地点", "search": "搜索地点", "search_hint": "按名称或氛围搜索", "all_places": "所有地点", "views": "View", "rooms": "Room", "all_access": "所有访问权限", "free": "免费", "supporter": "支持者", "animated": "动态", "sound": "含声音", "reset": "重置筛选", "places": "所有地点", "series": "系列", "count": "{count} 个地点", "empty_title": "没有地点符合这些筛选条件。", "empty_copy": "换个搜索词，或重置筛选条件。", "view": "View", "room": "Room", "get_app": "在 App Store 获取 Locus", "back": "返回画廊", "members": "此系列中的地点", "series_intro": "在 Locus 中探索相关地点。", "available": "可在 Locus {version} 中使用。"},
    "zh-Hant": {"gallery": "藝廊", "eyebrow": "Locus 藝廊", "title": "為下一刻找到一個地方。", "intro": "瀏覽 Locus 中可用的 View 和 Room。", "filters": "篩選地點", "search": "搜尋地點", "search_hint": "依名稱或氛圍搜尋", "all_places": "所有地點", "views": "View", "rooms": "Room", "all_access": "所有存取權", "free": "免費", "supporter": "支持者", "animated": "動態", "sound": "含聲音", "reset": "重設篩選", "places": "所有地點", "series": "系列", "count": "{count} 個地點", "empty_title": "沒有地點符合這些篩選條件。", "empty_copy": "換個搜尋詞，或重設篩選條件。", "view": "View", "room": "Room", "get_app": "在 App Store 取得 Locus", "back": "返回藝廊", "members": "此系列中的地點", "series_intro": "在 Locus 中探索相關地點。", "available": "可在 Locus {version} 中使用。"},
    "ja": {"gallery": "ギャラリー", "eyebrow": "Locus ギャラリー", "title": "次の時間のための場所を見つけよう。", "intro": "Locus で利用できる View と Room をご覧ください。", "filters": "場所を絞り込む", "search": "場所を検索", "search_hint": "名前や雰囲気で検索", "all_places": "すべての場所", "views": "View", "rooms": "Room", "all_access": "すべてのアクセス", "free": "無料", "supporter": "Supporter", "animated": "アニメーション", "sound": "サウンドあり", "reset": "絞り込みをリセット", "places": "すべての場所", "series": "シリーズ", "count": "{count} 件の場所", "empty_title": "条件に合う場所はありません。", "empty_copy": "別の語句で検索するか、絞り込みをリセットしてください。", "view": "View", "room": "Room", "get_app": "App Store で Locus を入手", "back": "ギャラリーに戻る", "members": "このシリーズの場所", "series_intro": "Locus で関連する場所を見つけましょう。", "available": "Locus {version} で利用できます。"},
    "ko": {"gallery": "갤러리", "eyebrow": "Locus 갤러리", "title": "다음 시간을 위한 장소를 찾아보세요.", "intro": "Locus에서 사용할 수 있는 View와 Room을 둘러보세요.", "filters": "장소 필터", "search": "장소 검색", "search_hint": "이름이나 분위기로 검색", "all_places": "모든 장소", "views": "View", "rooms": "Room", "all_access": "모든 이용 권한", "free": "무료", "supporter": "Supporter", "animated": "애니메이션", "sound": "사운드 포함", "reset": "필터 재설정", "places": "모든 장소", "series": "시리즈", "count": "장소 {count}개", "empty_title": "이 필터에 맞는 장소가 없습니다.", "empty_copy": "다른 검색어를 입력하거나 필터를 재설정하세요.", "view": "View", "room": "Room", "get_app": "App Store에서 Locus 받기", "back": "갤러리로 돌아가기", "members": "이 시리즈의 장소", "series_intro": "Locus에서 관련 장소를 살펴보세요.", "available": "Locus {version}에서 이용할 수 있습니다."},
    "de": {"gallery": "Galerie", "eyebrow": "Locus Galerie", "title": "Finde einen Ort für das, was als Nächstes kommt.", "intro": "Entdecke die in Locus verfügbaren Views und Räume.", "filters": "Orte filtern", "search": "Orte suchen", "search_hint": "Nach Name oder Stimmung suchen", "all_places": "Alle Orte", "views": "Views", "rooms": "Räume", "all_access": "Jeder Zugriff", "free": "Kostenlos", "supporter": "Supporter", "animated": "Animiert", "sound": "Mit Ton", "reset": "Filter zurücksetzen", "places": "Alle Orte", "series": "Serien", "count": "{count} Orte", "empty_title": "Keine Orte entsprechen diesen Filtern.", "empty_copy": "Versuche eine andere Suche oder setze die Filter zurück.", "view": "View", "room": "Raum", "get_app": "Locus im App Store laden", "back": "Zurück zur Galerie", "members": "Orte in dieser Serie", "series_intro": "Entdecke zusammengehörige Orte in Locus.", "available": "Verfügbar in Locus {version}."},
    "fr": {"gallery": "Galerie", "eyebrow": "Galerie Locus", "title": "Trouvez un lieu pour la suite.", "intro": "Parcourez les Views et les Rooms disponibles dans Locus.", "filters": "Filtrer les lieux", "search": "Rechercher des lieux", "search_hint": "Rechercher par nom ou ambiance", "all_places": "Tous les lieux", "views": "Views", "rooms": "Rooms", "all_access": "Tous les accès", "free": "Gratuit", "supporter": "Supporter", "animated": "Animé", "sound": "Avec son", "reset": "Réinitialiser les filtres", "places": "Tous les lieux", "series": "Séries", "count": "{count} lieux", "empty_title": "Aucun lieu ne correspond à ces filtres.", "empty_copy": "Essayez une autre recherche ou réinitialisez les filtres.", "view": "View", "room": "Room", "get_app": "Obtenir Locus sur l’App Store", "back": "Retour à la galerie", "members": "Lieux de cette série", "series_intro": "Découvrez des lieux associés dans Locus.", "available": "Disponible dans Locus {version}."},
    "es": {"gallery": "Galería", "eyebrow": "Galería de Locus", "title": "Encuentra un lugar para lo que viene.", "intro": "Explora las Views y Rooms disponibles en Locus.", "filters": "Filtrar lugares", "search": "Buscar lugares", "search_hint": "Busca por nombre o ambiente", "all_places": "Todos los lugares", "views": "Views", "rooms": "Rooms", "all_access": "Todo el acceso", "free": "Gratis", "supporter": "Supporter", "animated": "Animado", "sound": "Con sonido", "reset": "Restablecer filtros", "places": "Todos los lugares", "series": "Series", "count": "{count} lugares", "empty_title": "Ningún lugar coincide con estos filtros.", "empty_copy": "Prueba otra búsqueda o restablece los filtros.", "view": "View", "room": "Room", "get_app": "Obtener Locus en App Store", "back": "Volver a la galería", "members": "Lugares de esta serie", "series_intro": "Explora lugares relacionados en Locus.", "available": "Disponible en Locus {version}."},
}

CREDIT_COPY = {
    "en": {"heading": "Credits", "creator": "Creator", "source": "Source", "license": "License", "changes": "Changes", "ai": "AI-generated"},
    "zh-Hans": {"heading": "署名", "creator": "创作者", "source": "来源", "license": "许可", "changes": "修改", "ai": "AI 生成"},
    "zh-Hant": {"heading": "署名", "creator": "創作者", "source": "來源", "license": "授權", "changes": "修改", "ai": "由 AI 生成"},
    "ja": {"heading": "クレジット", "creator": "作者", "source": "出典", "license": "ライセンス", "changes": "変更", "ai": "AI 生成"},
    "ko": {"heading": "크레딧", "creator": "제작자", "source": "출처", "license": "라이선스", "changes": "변경", "ai": "AI 생성"},
    "de": {"heading": "Credits", "creator": "Urheber", "source": "Quelle", "license": "Lizenz", "changes": "Änderungen", "ai": "KI-generiert"},
    "fr": {"heading": "Crédits", "creator": "Créateur", "source": "Source", "license": "Licence", "changes": "Modifications", "ai": "Généré par IA"},
    "es": {"heading": "Créditos", "creator": "Creador", "source": "Fuente", "license": "Licencia", "changes": "Cambios", "ai": "Generado con IA"},
}

PREVIEW_COPY = {
    "en": {"still": "Still preview", "animated": "Animated in Locus"},
    "zh-Hans": {"still": "静态预览", "animated": "在 Locus 中动态播放"},
    "zh-Hant": {"still": "靜態預覽", "animated": "在 Locus 中動態播放"},
    "ja": {"still": "静止プレビュー", "animated": "Locus ではアニメーション"},
    "ko": {"still": "정지 미리보기", "animated": "Locus에서 애니메이션"},
    "de": {"still": "Standbildvorschau", "animated": "In Locus animiert"},
    "fr": {"still": "Aperçu fixe", "animated": "Animé dans Locus"},
    "es": {"still": "Vista previa fija", "animated": "Animado en Locus"},
}

SERIES_COPY = {
    "en": "Part of", "zh-Hans": "所属系列", "zh-Hant": "所屬系列", "ja": "シリーズ",
    "ko": "시리즈", "de": "Teil von", "fr": "Fait partie de", "es": "Parte de",
}


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def locale_url(path: str, locale: str) -> str:
    prefix = "" if locale == "en" else f"/{locale}"
    return f"{prefix}{path}"


def public_url(path: str, locale: str) -> str:
    return SITE + locale_url(path, locale)


def localize(item: dict, locale: str) -> dict:
    localized = item.get("localizations", {}).get(locale, {}) if locale != "en" else {}
    return {**item, "title": localized.get("title") or item["title"],
            "description": localized.get("description") or item.get("description", ""),
            "searchTerms": localized.get("searchTerms") or item.get("searchTerms", [])}


def image_markup(image: dict, alt: str, loading: str = "lazy") -> str:
    return (f'<img class="gallery-card-image" src="{esc(image["url"])}" width="{int(image["width"])}" '
            f'height="{int(image["height"])}" loading="{loading}" decoding="async" alt="{esc(alt)}">')


def series_image(item: dict, places: list[dict]) -> dict | None:
    if item.get("image"):
        return item["image"]
    hero = item.get("heroMember")
    member = next((place for place in places if place["id"] == hero), None)
    if not member:
        member = next((place for place in places if place["id"] in item.get("members", [])), None)
    return member.get("image") if member else None


def nav(locale: str, current: str) -> str:
    root = locale_url('/', locale)
    c = COPY[locale]
    def link(path: str, label: str, key: str) -> str:
        value = f'{root}{path}'
        current_attribute = ' aria-current="page"' if current == key else ''
        return f'<a{current_attribute} href="{value}">{esc(label)}</a>'
    return (f'<header class="site-header"><a class="brand" href="{root}" aria-label="Locus home"><span class="brand-mark" aria-hidden="true"><span></span></span><span>Locus</span></a>'
            f'<nav aria-label="Primary navigation">{link("whats-new/", "What’s New", "whats-new")}{link("gallery/", c["gallery"], "gallery")}{link("tutorials/", "Tutorials", "tutorials")}{link("faq/", "FAQ", "faq")}{link("support/", "Support", "support")}<a href="https://www.reddit.com/r/EnterLocus/">Community</a><button class="search-trigger" type="button" hidden aria-haspopup="dialog"><svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></svg>Search</button></nav></header>')


def footer(locale: str) -> str:
    root = locale_url('/', locale)
    c = COPY[locale]
    return (f'<footer><div><span class="brand-footer">Locus</span><span>Locus for Apple Vision Pro.</span></div><nav aria-label="Footer navigation">'
            f'<a href="{root}whats-new/">What’s New</a><a href="{root}gallery/">{esc(c["gallery"])}</a><a href="{root}tutorials/">Tutorials</a><a href="{root}faq/">FAQ</a><a href="{root}support/">Support</a><a href="{root}privacy/">Privacy</a><a href="https://www.reddit.com/r/EnterLocus/">Community</a><a href="https://github.com/EnterLocus/locus-support/issues/new?template=bug.yml">Report a Bug</a></nav></footer>')


def document(locale: str, title: str, description: str, path: str, body: str) -> str:
    canonical = public_url(path, locale)
    alternates = ''.join(f'<link rel="alternate" hreflang="{tag}" href="{public_url(path, tag)}">' for tag in LOCALES)
    return f'''<!doctype html>
<html lang="{locale}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="theme-color" content="#0d141a">
<title>{esc(title)}</title><meta name="description" content="{esc(description)}"><meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(description)}"><meta property="og:type" content="website"><meta property="og:url" content="{canonical}"><meta property="og:image" content="https://enterlocus.com/assets/og.png"><meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{esc(title)}"><meta name="twitter:description" content="{esc(description)}"><meta name="twitter:image" content="https://enterlocus.com/assets/og.png"><link rel="canonical" href="{canonical}">{alternates}<link rel="alternate" hreflang="x-default" href="{public_url(path, "en")}"><link rel="icon" type="image/png" href="/assets/favicon.png"><link rel="apple-touch-icon" href="/assets/apple-touch-icon.png"><link rel="stylesheet" href="/assets/site.css"><link rel="stylesheet" href="/assets/gallery.css"><link rel="stylesheet" href="/assets/search.css"><script>window.LocusLocalization={{"locale":{json.dumps(locale)},"strings":{{}}}};</script><script src="/assets/gallery.js" defer></script><script type="module" src="/assets/search.js"></script></head><body><a class="skip-link" href="#main">Skip to content</a>{nav(locale, "gallery")}<main data-pagefind-body id="main">{body}</main>{footer(locale)}</body></html>'''


def badges(place: dict, c: dict, locale: str) -> str:
    items = [f'<span class="gallery-badge">{esc(c[place["type"]])}</span>',
             f'<span class="gallery-badge {"warm" if place["access"] == "supporter" else ""}">{esc(c[place["access"]])}</span>']
    if place.get("animated"):
        items.append(f'<span class="gallery-badge">{esc(PREVIEW_COPY[locale]["animated"])}</span>')
    if place.get("hasSound"):
        items.append(f'<span class="gallery-badge">{esc(c["sound"])}</span>')
    return ''.join(items)


def credits_markup(place: dict, locale: str) -> str:
    credits = place.get("credits")
    if not credits:
        return ""
    c = CREDIT_COPY[locale]
    rows = []
    if credits.get("creator"):
        rows.append((c["creator"], esc(credits["creator"])))
    if credits.get("credit"):
        rows.append((c["heading"], esc(credits["credit"])))
    if credits.get("sourceURL"):
        url = esc(credits["sourceURL"])
        rows.append((c["source"], f'<a href="{url}">{url}</a>'))
    if credits.get("licenseName"):
        value = esc(credits["licenseName"])
        if credits.get("licenseURL"):
            url = esc(credits["licenseURL"])
            value = f'<a href="{url}">{value}</a>'
        rows.append((c["license"], value))
    if credits.get("modification"):
        rows.append((c["changes"], esc(credits["modification"])))
    if credits.get("aiGenerated"):
        provider = esc(credits["aiProvider"]) if credits.get("aiProvider") else esc(c["ai"])
        rows.append((c["ai"], provider))
    if not rows:
        return ""
    values = ''.join(f'<dt>{esc(label)}</dt><dd>{value}</dd>' for label, value in rows)
    return f'<section class="gallery-credits"><h2>{esc(c["heading"])}</h2><dl>{values}</dl></section>'


def place_card(place: dict, locale: str) -> str:
    c = COPY[locale]
    search = ' '.join([place["title"], place.get("description", ""), *place.get("searchTerms", [])]).lower()
    path = locale_url(f'/gallery/place/{quote(place["slug"])}/', locale)
    return f'''<article class="gallery-card" data-gallery-card data-type="{esc(place["type"])}" data-access="{esc(place["access"])}" data-animated="{str(bool(place.get("animated"))).lower()}" data-sound="{str(bool(place.get("hasSound"))).lower()}" data-search="{esc(search)}"><a href="{path}">{image_markup(place["image"], place["title"])}<div class="gallery-card-copy"><span class="gallery-preview-note">{esc(PREVIEW_COPY[locale]["still"])}</span><h3>{esc(place["title"])}</h3><p>{esc(place.get("description", ""))}</p><div class="gallery-badges">{badges(place, c, locale)}</div></div></a></article>'''


def gallery_page(manifest: dict, locale: str) -> str:
    c = COPY[locale]
    places = [localize(place, locale) for place in manifest["places"]]
    series = [localize(item, locale) for item in manifest.get("series", [])]
    series_markup = ''
    if series:
        cards = []
        for item in series:
            image = series_image(item, places)
            if not image:
                continue
            path = locale_url(f'/gallery/series/{quote(item["id"])}/', locale)
            cards.append(f'<article class="gallery-card gallery-series-card"><a href="{path}">{image_markup(image, item["title"], "eager")}<div class="gallery-card-copy"><h3>{esc(item["title"])}</h3><p>{esc(item.get("description", c["series_intro"]))}</p></div></a></article>')
        if cards:
            series_markup = f'<section class="gallery-section" data-gallery-series aria-labelledby="series-heading" hidden><div class="gallery-section-heading"><h2 id="series-heading">{esc(c["series"])}</h2></div><div class="gallery-grid">{"".join(cards)}</div></section>'
    cards = ''.join(place_card(place, locale) for place in places)
    body = f'''<div class="gallery-page" data-gallery><header class="gallery-header"><p class="kicker">{esc(c["eyebrow"])}</p><h1>{esc(c["title"])}</h1><p>{esc(c["intro"])}</p><nav class="gallery-mode-tabs" aria-label="{esc(c["filters"])}"><button type="button" data-gallery-mode="places" data-value="all">{esc(c["all_places"])}</button><button type="button" data-gallery-mode="places" data-value="view">{esc(c["views"])}</button><button type="button" data-gallery-mode="places" data-value="room">{esc(c["rooms"])}</button><button type="button" data-gallery-mode="series">{esc(c["series"])}</button></nav></header><div class="gallery-filters" data-gallery-filters aria-label="{esc(c["filters"])}"><label class="gallery-search-label">{esc(c["search"])}<input data-gallery-search type="search" placeholder="{esc(c["search_hint"])}" autocomplete="off"></label><div class="gallery-filter-group"><button class="gallery-filter" type="button" data-gallery-filter="access" data-value="all">{esc(c["all_access"])}</button><button class="gallery-filter" type="button" data-gallery-filter="access" data-value="free">{esc(c["free"])}</button><button class="gallery-filter" type="button" data-gallery-filter="access" data-value="supporter">{esc(c["supporter"])}</button></div><div class="gallery-filter-group"><button class="gallery-filter" type="button" data-gallery-filter="animated" data-value="true">{esc(c["animated"])}</button><button class="gallery-filter" type="button" data-gallery-filter="sound" data-value="true">{esc(c["sound"])}</button></div><button class="gallery-reset" type="button" data-gallery-reset>{esc(c["reset"])}</button></div><section class="gallery-section" data-gallery-places aria-labelledby="places-heading"><div class="gallery-section-heading"><h2 id="places-heading">{esc(c["places"])}</h2><p data-gallery-status data-gallery-count="{esc(c["count"])}" aria-live="polite"></p></div><div class="gallery-grid">{cards}</div><div class="gallery-empty" data-gallery-empty hidden><h2>{esc(c["empty_title"])}</h2><p>{esc(c["empty_copy"])}</p><button class="gallery-reset" type="button" data-gallery-reset>{esc(c["reset"])}</button></div></section>{series_markup}</div>'''
    return document(locale, f'{c["gallery"]} — Locus', c["intro"], '/gallery/', body)


def place_page(place: dict, manifest: dict, locale: str) -> str:
    c = COPY[locale]
    description = place.get("description", "")
    meta = badges(place, c, locale)
    version = manifest.get("appVersion", "")
    series = [localize(item, locale) for item in manifest.get("series", []) if place["id"] in item.get("members", [])]
    memberships = ''.join(
        f'<a href="{locale_url("/gallery/series/" + quote(item["id"]) + "/", locale)}">{esc(item["title"])}</a>'
        for item in series)
    membership_markup = f'<div class="gallery-membership"><span>{esc(SERIES_COPY[locale])}</span>{memberships}</div>' if memberships else ''
    body = f'''<div class="gallery-detail"><figure class="gallery-detail-media">{image_markup(place["image"], place["title"], "eager")}</figure><section class="gallery-detail-copy"><p class="kicker">{esc(c[place["type"]])}</p><h1>{esc(place["title"])}</h1><p>{esc(description)}</p><div class="gallery-meta">{meta}</div>{membership_markup}<p>{esc(c["available"].format(version=version))}</p><a class="gallery-cta" href="{APP_STORE}">{esc(c["get_app"])}</a><a class="gallery-back" href="{locale_url("/gallery/", locale)}">← {esc(c["back"])}</a></section></div>{credits_markup(place, locale)}'''
    return document(locale, f'{place["title"]} — {c["gallery"]} — Locus', description, f'/gallery/place/{quote(place["slug"])}/', body)


def series_page(item: dict, places: list[dict], locale: str) -> str:
    c = COPY[locale]
    members = [place for place in places if place["id"] in item.get("members", [])]
    image = series_image(item, places)
    hero = f'<figure class="gallery-detail-media">{image_markup(image, item["title"], "eager")}</figure>' if image else ''
    body = f'''<div class="gallery-detail"><section class="gallery-detail-copy"><p class="kicker">{esc(c["series"])}</p><h1>{esc(item["title"])}</h1><p>{esc(item.get("description", c["series_intro"]))}</p><a class="gallery-back" href="{locale_url("/gallery/", locale)}">← {esc(c["back"])}</a></section>{hero}</div><section class="gallery-series-members"><div class="gallery-section-heading"><h2>{esc(c["members"])}</h2></div><div class="gallery-grid">{"".join(place_card(place, locale) for place in members)}</div></section>'''
    return document(locale, f'{item["title"]} — {c["series"]} — Locus', item.get("description", c["series_intro"]), f'/gallery/series/{quote(item["id"])}/', body)


def add_sitemap_urls(output: Path, paths: list[str]) -> None:
    sitemap = output / 'sitemap.xml'
    tree = ET.parse(sitemap)
    root = tree.getroot()
    namespace = '{http://www.sitemaps.org/schemas/sitemap/0.9}'
    known = {node.findtext(f'{namespace}loc') for node in root.findall(f'{namespace}url')}
    for path in paths:
        for locale in LOCALES:
            url = public_url(path, locale)
            if url not in known:
                node = ET.SubElement(root, f'{namespace}url')
                ET.SubElement(node, f'{namespace}loc').text = url
                known.add(url)
    ET.register_namespace('', 'http://www.sitemaps.org/schemas/sitemap/0.9')
    tree.write(sitemap, encoding='utf-8', xml_declaration=True)


def build(root: Path, output: Path, catalogs: dict | None = None, translator=None) -> None:
    source = root / 'data' / 'gallery.json'
    if not source.is_file():
        return
    manifest = json.loads(source.read_text(encoding='utf-8'))
    if manifest.get('formatVersion') != 1:
        raise ValueError('gallery.json must use formatVersion 1')
    paths = ['/gallery/']
    for locale in LOCALES:
        (output / ('' if locale == 'en' else locale) / 'gallery' / 'index.html').parent.mkdir(parents=True, exist_ok=True)
        page = gallery_page(manifest, locale)
        if translator:
            page = translator(page, Path('gallery/index.html'), locale, catalogs[locale])
        (output / ('' if locale == 'en' else locale) / 'gallery' / 'index.html').write_text(page, encoding='utf-8')
        places = [localize(place, locale) for place in manifest['places']]
        for place in places:
            path = f'/gallery/place/{quote(place["slug"])}/'
            target = output / ('' if locale == 'en' else locale) / 'gallery' / 'place' / place['slug'] / 'index.html'
            target.parent.mkdir(parents=True, exist_ok=True)
            page = place_page(place, manifest, locale)
            if translator:
                page = translator(page, Path('gallery/place') / place['slug'] / 'index.html', locale, catalogs[locale])
            target.write_text(page, encoding='utf-8')
            if locale == 'en': paths.append(path)
        for item in [localize(series, locale) for series in manifest.get('series', [])]:
            path = f'/gallery/series/{quote(item["id"])}/'
            target = output / ('' if locale == 'en' else locale) / 'gallery' / 'series' / item['id'] / 'index.html'
            target.parent.mkdir(parents=True, exist_ok=True)
            page = series_page(item, places, locale)
            if translator:
                page = translator(page, Path('gallery/series') / item['id'] / 'index.html', locale, catalogs[locale])
            target.write_text(page, encoding='utf-8')
            if locale == 'en': paths.append(path)
    add_sitemap_urls(output, paths)
