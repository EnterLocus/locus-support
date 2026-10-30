"""Render the public Gallery from the catalog-owned public manifest."""
from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
import xml.etree.ElementTree as ET

from localization import LOCALES

SITE = "https://enterlocus.com"
APP_STORE = "https://apps.apple.com/app/id6802168265"

COPY = {
    "en": {"gallery": "Gallery", "eyebrow": "Locus Gallery", "title": "Find a place for what’s next.",
           "intro": "Explore Views and Rooms for Locus.", "filters": "Filter Places",
           "search": "Search Places", "search_hint": "Search by name or mood", "all_places": "All Places",
           "views": "Views", "rooms": "Rooms", "all_access": "All access", "free": "Free",
           "supporter": "Supporter", "animated": "Animated", "sound": "With sound", "reset": "Reset filters",
           "places": "All Places", "series": "Series", "count": "{count} places", "empty_title": "No places match these filters.",
           "empty_copy": "Try another search or reset filters.", "view": "View", "room": "Room",
           "get_app": "Get Locus on the App Store", "back": "Back to Gallery", "members": "Places in this series",
           "series_intro": "Explore related Places in Locus.", "available": "Available in Locus {version}.", "photos": "Rendered in Locus · Simulator", "open_photo": "Open photo {current} of {total}", "photo_strip": "Rendered photos", "previous_photo": "Previous photo", "next_photo": "Next photo", "close_photo": "Close photo", "photo_counter": "Photo {current} of {total}"},
    "zh-Hans": {"gallery": "画廊", "eyebrow": "Locus 画廊", "title": "为下一刻找到一个地方。", "intro": "探索 Locus 的 View 和 Room。", "filters": "筛选地点", "search": "搜索地点", "search_hint": "按名称或氛围搜索", "all_places": "所有地点", "views": "View", "rooms": "Room", "all_access": "所有访问权限", "free": "免费", "supporter": "支持者", "animated": "动态", "sound": "含声音", "reset": "重置筛选", "places": "所有地点", "series": "系列", "count": "{count} 个地点", "empty_title": "没有地点符合这些筛选条件。", "empty_copy": "换个搜索词，或重置筛选条件。", "view": "View", "room": "Room", "get_app": "在 App Store 获取 Locus", "back": "返回画廊", "members": "此系列中的地点", "series_intro": "在 Locus 中探索相关地点。", "available": "可在 Locus {version} 中使用。", "photos": "在 Locus 中渲染 · 模拟器", "open_photo": "打开第 {current} 张，共 {total} 张", "photo_strip": "渲染照片", "previous_photo": "上一张照片", "next_photo": "下一张照片", "close_photo": "关闭照片", "photo_counter": "第 {current} 张，共 {total} 张"},
    "zh-Hant": {"gallery": "藝廊", "eyebrow": "Locus 藝廊", "title": "為下一刻找到一個地方。", "intro": "探索 Locus 的 View 和 Room。", "filters": "篩選地點", "search": "搜尋地點", "search_hint": "依名稱或氛圍搜尋", "all_places": "所有地點", "views": "View", "rooms": "Room", "all_access": "所有存取權", "free": "免費", "supporter": "支持者", "animated": "動態", "sound": "含聲音", "reset": "重設篩選", "places": "所有地點", "series": "系列", "count": "{count} 個地點", "empty_title": "沒有地點符合這些篩選條件。", "empty_copy": "換個搜尋詞，或重設篩選條件。", "view": "View", "room": "Room", "get_app": "在 App Store 取得 Locus", "back": "返回藝廊", "members": "此系列中的地點", "series_intro": "在 Locus 中探索相關地點。", "available": "可在 Locus {version} 中使用。", "photos": "在 Locus 中渲染 · 模擬器", "open_photo": "開啟第 {current} 張，共 {total} 張", "photo_strip": "渲染照片", "previous_photo": "上一張照片", "next_photo": "下一張照片", "close_photo": "關閉照片", "photo_counter": "第 {current} 張，共 {total} 張"},
    "ja": {"gallery": "ギャラリー", "eyebrow": "Locus ギャラリー", "title": "次の時間のための場所を見つけよう。", "intro": "Locus の View と Room をご覧ください。", "filters": "場所を絞り込む", "search": "場所を検索", "search_hint": "名前や雰囲気で検索", "all_places": "すべての場所", "views": "View", "rooms": "Room", "all_access": "すべてのアクセス", "free": "無料", "supporter": "Supporter", "animated": "アニメーション", "sound": "サウンドあり", "reset": "絞り込みをリセット", "places": "すべての場所", "series": "シリーズ", "count": "{count} 件の場所", "empty_title": "条件に合う場所はありません。", "empty_copy": "別の語句で検索するか、絞り込みをリセットしてください。", "view": "View", "room": "Room", "get_app": "App Store で Locus を入手", "back": "ギャラリーに戻る", "members": "このシリーズの場所", "series_intro": "Locus で関連する場所を見つけましょう。", "available": "Locus {version} で利用できます。", "photos": "Locus でレンダリング · シミュレータ", "open_photo": "写真 {current} / {total} を開く", "photo_strip": "レンダリング写真", "previous_photo": "前の写真", "next_photo": "次の写真", "close_photo": "写真を閉じる", "photo_counter": "写真 {current} / {total}"},
    "ko": {"gallery": "갤러리", "eyebrow": "Locus 갤러리", "title": "다음 시간을 위한 장소를 찾아보세요.", "intro": "Locus의 View와 Room을 둘러보세요.", "filters": "장소 필터", "search": "장소 검색", "search_hint": "이름이나 분위기로 검색", "all_places": "모든 장소", "views": "View", "rooms": "Room", "all_access": "모든 이용 권한", "free": "무료", "supporter": "Supporter", "animated": "애니메이션", "sound": "사운드 포함", "reset": "필터 재설정", "places": "모든 장소", "series": "시리즈", "count": "장소 {count}개", "empty_title": "이 필터에 맞는 장소가 없습니다.", "empty_copy": "다른 검색어를 입력하거나 필터를 재설정하세요.", "view": "View", "room": "Room", "get_app": "App Store에서 Locus 받기", "back": "갤러리로 돌아가기", "members": "이 시리즈의 장소", "series_intro": "Locus에서 관련 장소를 살펴보세요.", "available": "Locus {version}에서 이용할 수 있습니다.", "photos": "Locus에서 렌더링 · 시뮬레이터", "open_photo": "사진 {current}/{total} 열기", "photo_strip": "렌더링 사진", "previous_photo": "이전 사진", "next_photo": "다음 사진", "close_photo": "사진 닫기", "photo_counter": "사진 {current}/{total}"},
    "de": {"gallery": "Galerie", "eyebrow": "Locus Galerie", "title": "Finde einen Ort für das, was als Nächstes kommt.", "intro": "Entdecke Views und Räume für Locus.", "filters": "Orte filtern", "search": "Orte suchen", "search_hint": "Nach Name oder Stimmung suchen", "all_places": "Alle Orte", "views": "Views", "rooms": "Räume", "all_access": "Jeder Zugriff", "free": "Kostenlos", "supporter": "Supporter", "animated": "Animiert", "sound": "Mit Ton", "reset": "Filter zurücksetzen", "places": "Alle Orte", "series": "Serien", "count": "{count} Orte", "empty_title": "Keine Orte entsprechen diesen Filtern.", "empty_copy": "Versuche eine andere Suche oder setze die Filter zurück.", "view": "View", "room": "Raum", "get_app": "Locus im App Store laden", "back": "Zurück zur Galerie", "members": "Orte in dieser Serie", "series_intro": "Entdecke zusammengehörige Orte in Locus.", "available": "Verfügbar in Locus {version}.", "photos": "In Locus gerendert · Simulator", "open_photo": "Foto {current} von {total} öffnen", "photo_strip": "Gerenderte Fotos", "previous_photo": "Vorheriges Foto", "next_photo": "Nächstes Foto", "close_photo": "Foto schließen", "photo_counter": "Foto {current} von {total}"},
    "fr": {"gallery": "Galerie", "eyebrow": "Galerie Locus", "title": "Trouvez un lieu pour la suite.", "intro": "Découvrez les Views et les Rooms de Locus.", "filters": "Filtrer les lieux", "search": "Rechercher des lieux", "search_hint": "Rechercher par nom ou ambiance", "all_places": "Tous les lieux", "views": "Views", "rooms": "Rooms", "all_access": "Tous les accès", "free": "Gratuit", "supporter": "Supporter", "animated": "Animé", "sound": "Avec son", "reset": "Réinitialiser les filtres", "places": "Tous les lieux", "series": "Séries", "count": "{count} lieux", "empty_title": "Aucun lieu ne correspond à ces filtres.", "empty_copy": "Essayez une autre recherche ou réinitialisez les filtres.", "view": "View", "room": "Room", "get_app": "Obtenir Locus sur l’App Store", "back": "Retour à la galerie", "members": "Lieux de cette série", "series_intro": "Découvrez des lieux associés dans Locus.", "available": "Disponible dans Locus {version}.", "photos": "Rendu dans Locus · Simulateur", "open_photo": "Ouvrir la photo {current} sur {total}", "photo_strip": "Photos rendues", "previous_photo": "Photo précédente", "next_photo": "Photo suivante", "close_photo": "Fermer la photo", "photo_counter": "Photo {current} sur {total}"},
    "es": {"gallery": "Galería", "eyebrow": "Galería de Locus", "title": "Encuentra un lugar para lo que viene.", "intro": "Explora las Views y Rooms de Locus.", "filters": "Filtrar lugares", "search": "Buscar lugares", "search_hint": "Busca por nombre o ambiente", "all_places": "Todos los lugares", "views": "Views", "rooms": "Rooms", "all_access": "Todo el acceso", "free": "Gratis", "supporter": "Supporter", "animated": "Animado", "sound": "Con sonido", "reset": "Restablecer filtros", "places": "Todos los lugares", "series": "Series", "count": "{count} lugares", "empty_title": "Ningún lugar coincide con estos filtros.", "empty_copy": "Prueba otra búsqueda o restablece los filtros.", "view": "View", "room": "Room", "get_app": "Obtener Locus en App Store", "back": "Volver a la galería", "members": "Lugares de esta serie", "series_intro": "Explora lugares relacionados en Locus.", "available": "Disponible en Locus {version}.", "photos": "Renderizado en Locus · Simulador", "open_photo": "Abrir foto {current} de {total}", "photo_strip": "Fotos renderizadas", "previous_photo": "Foto anterior", "next_photo": "Foto siguiente", "close_photo": "Cerrar foto", "photo_counter": "Foto {current} de {total}"},
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

PHOTO_LABELS = {
    "en": {"front": "Front view", "left": "Left view", "right": "Right view", "alternate-seat": "Alternate seat"},
    "zh-Hans": {"front": "正面视角", "left": "左侧视角", "right": "右侧视角", "alternate-seat": "另一座位"},
    "zh-Hant": {"front": "正面視角", "left": "左側視角", "right": "右側視角", "alternate-seat": "另一座位"},
    "ja": {"front": "正面ビュー", "left": "左側ビュー", "right": "右側ビュー", "alternate-seat": "別の座席"},
    "ko": {"front": "정면 보기", "left": "왼쪽 보기", "right": "오른쪽 보기", "alternate-seat": "다른 좌석"},
    "de": {"front": "Vorderansicht", "left": "Linke Ansicht", "right": "Rechte Ansicht", "alternate-seat": "Anderer Sitzplatz"},
    "fr": {"front": "Vue de face", "left": "Vue de gauche", "right": "Vue de droite", "alternate-seat": "Autre siège"},
    "es": {"front": "Vista frontal", "left": "Vista izquierda", "right": "Vista derecha", "alternate-seat": "Otro asiento"},
}

SERIES_BACK_COPY = {
    "en": "Back to {title}", "zh-Hans": "返回{title}系列", "zh-Hant": "返回{title}系列",
    "ja": "{title}に戻る", "ko": "{title}(으)로 돌아가기", "de": "Zurück zu {title}",
    "fr": "Retour à {title}", "es": "Volver a {title}",
}

RELEASE_PREVIEW_COPY = {
    "en": {"badge": "Locus {version} preview", "available": "Coming in Locus {version}."},
    "zh-Hans": {"badge": "Locus {version} 预览", "available": "将在 Locus {version} 上架后推出。"},
    "zh-Hant": {"badge": "Locus {version} 預覽", "available": "將在 Locus {version} 上架後推出。"},
    "ja": {"badge": "Locus {version} プレビュー", "available": "Locus {version} で登場予定。"},
    "ko": {"badge": "Locus {version} 미리보기", "available": "Locus {version}에서 출시 예정입니다."},
    "de": {"badge": "Vorschau auf Locus {version}", "available": "Demnächst in Locus {version}."},
    "fr": {"badge": "Aperçu de Locus {version}", "available": "À venir dans Locus {version}."},
    "es": {"badge": "Avance de Locus {version}", "available": "Próximamente en Locus {version}."},
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


def image_markup(image: dict, alt: str, loading: str = "lazy", css_class: str = "gallery-card-image") -> str:
    return (f'<img class="{css_class}" src="{esc(image["url"])}" width="{int(image["width"])}" '
            f'height="{int(image["height"])}" loading="{loading}" decoding="async" alt="{esc(alt)}">')


def newest_date(item: dict) -> float:
    """Return a normalized UTC sort key for the Library's added/updated semantics."""
    values = []
    for value in (item.get("addedAt"), item.get("updatedAt")):
        if not value:
            continue
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        values.append(parsed.astimezone(timezone.utc).timestamp())
    return max(values, default=float("-inf"))


def newest_first(items: list[dict]) -> list[dict]:
    """Sort dated Places like the Library, with localized titles breaking ties."""
    titled = sorted(enumerate(items), key=lambda pair: (pair[1]["title"].casefold(), pair[0]))
    return [item for _index, item in sorted(titled, key=lambda pair: newest_date(pair[1]), reverse=True)]


def eligible_series(places: list[dict], series: list[dict]) -> list[dict]:
    """Return the first eligible owner for each public Place, in catalog order."""
    by_id = {place["id"]: place for place in places}
    claimed: set[str] = set()
    result = []
    for source_index, item in enumerate(series):
        members = [by_id[member] for member in item.get("members", [])
                   if member in by_id and member not in claimed]
        kinds = {member["type"] for member in members}
        kind = item.get("type") or (next(iter(kinds)) if len(kinds) == 1 else None)
        if kind not in {"view", "room"} or kinds != {kind} or len(members) < 2:
            continue
        claimed.update(member["id"] for member in members)
        result.append({"series": item, "members": newest_first(members), "type": kind,
                       "source_index": source_index})
    return result


def collection_order(places: list[dict], series: list[dict]) -> list[dict]:
    groups = eligible_series(places, series)
    claimed = {member["id"] for group in groups for member in group["members"]}
    items = ([{"kind": "series", **group, "date": max(newest_date(member) for member in group["members"]),
               "title": group["series"]["title"]} for group in groups] +
             [{"kind": "place", "place": place, "date": newest_date(place), "title": place["title"],
               "source_index": index} for index, place in enumerate(places) if place["id"] not in claimed])
    titled = sorted(items, key=lambda item: (item["title"].casefold(), item["source_index"]))
    return sorted(titled, key=lambda item: item["date"], reverse=True)


def card_cover_members(item: dict, members: list[dict]) -> list[dict]:
    cover = item.get("cover", [])
    if isinstance(cover, str):
        cover = [cover]
    by_id = {member["id"]: member for member in members}
    selected = [by_id[member_id] for member_id in cover if member_id in by_id]
    selected += [member for member in members if member not in selected]
    return selected[:3]


def series_image(item: dict, places: list[dict]) -> dict | None:
    if item.get("image"):
        return item["image"]
    hero = item.get("heroMember")
    member = next((place for place in places if place["id"] == hero), None)
    if not member:
        member = next((place for place in places if place["id"] in item.get("members", [])), None)
    return member["image"] if member else None


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
    if place.get("previewRelease"):
        label = RELEASE_PREVIEW_COPY[locale]["badge"].format(version=place["previewRelease"])
        items.append(f'<span class="gallery-badge release-preview">{esc(label)}</span>')
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
        credit = esc(credits["credit"]).replace('CC BY 4.0',
            '<a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>')
        rows.append((c["heading"], credit))
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


def place_card(place: dict, locale: str, series_titles: list[str] | None = None,
               recent_order: int | None = None, return_series: str | None = None) -> str:
    c = COPY[locale]
    search = ' '.join(term for term in [place["title"], place.get("description", ""), *place.get("searchTerms", []), *(series_titles or [])] if term).lower()
    path = locale_url(f'/gallery/place/{quote(place["slug"])}/', locale)
    if return_series:
        path += "?series=" + quote(return_series, safe="")
    membership = f' data-series-member="true"' if series_titles else ''
    recent = f' data-gallery-recent-order="{int(recent_order)}"' if recent_order is not None else ''
    return f'''<article class="gallery-card" data-gallery-card{membership}{recent} data-type="{esc(place["type"])}" data-access="{esc(place["access"])}" data-animated="{str(bool(place.get("animated"))).lower()}" data-sound="{str(bool(place.get("hasSound"))).lower()}" data-search="{esc(search)}"><a href="{path}">{image_markup(place["image"], place["title"])}<div class="gallery-card-copy"><span class="gallery-preview-note">{esc(PREVIEW_COPY[locale]["still"])}</span><h3>{esc(place["title"])}</h3><p>{esc(place.get("description", ""))}</p><div class="gallery-badges">{badges(place, c, locale)}</div></div></a></article>'''


def series_card(item: dict, members: list[dict], kind: str, locale: str) -> str:
    c = COPY[locale]
    path = locale_url(f'/gallery/series/{quote(item["id"])}/', locale)
    covers = ''.join(image_markup(member["image"], member["title"], css_class="gallery-collage-image")
                     for member in card_cover_members(item, members))
    return f'''<article class="gallery-card gallery-series-card" data-gallery-series-card data-type="{esc(kind)}"><a href="{path}"><div class="gallery-series-collage" aria-hidden="true">{covers}</div><div class="gallery-card-copy"><span class="gallery-preview-note">{esc(c["series"])}</span><h3>{esc(item["title"])}</h3><p>{esc(item.get("description", c["series_intro"]))}</p></div></a></article>'''


def gallery_page(manifest: dict, locale: str) -> str:
    c = COPY[locale]
    places = [localize(place, locale) for place in manifest["places"]]
    series = [localize(item, locale) for item in manifest.get("series", [])]
    recent_order = {place["id"]: index for index, place in enumerate(newest_first(places))}
    groups = eligible_series(places, series)
    source_series = {item["id"]: item for item in manifest.get("series", [])}
    member_series = {member["id"]: [] for group in groups for member in group["members"]}
    for group in groups:
        source = source_series[group["series"]["id"]]
        titles = list(dict.fromkeys([source["title"], group["series"]["title"],
                     *(value["title"] for value in source.get("localizations", {}).values()
                       if value.get("title"))]))
        for member in group["members"]:
            member_series[member["id"]].extend(titles)
    cards = []
    for collection in collection_order(places, series):
        if collection["kind"] == "series":
            cards.append(series_card(collection["series"], collection["members"], collection["type"], locale))
            cards.extend(place_card(member, locale, member_series.get(member["id"]), recent_order[member["id"]])
                         for member in collection["members"])
        else:
            place = collection["place"]
            cards.append(place_card(place, locale, member_series.get(place["id"]), recent_order[place["id"]]))
    body = f'''<div class="gallery-page" data-gallery><header class="gallery-header"><p class="kicker">{esc(c["eyebrow"])}</p><h1>{esc(c["title"])}</h1><p>{esc(c["intro"])}</p><nav class="gallery-mode-tabs" aria-label="{esc(c["filters"])}"><button type="button" data-gallery-mode data-value="all">{esc(c["all_places"])}</button><button type="button" data-gallery-mode data-value="view">{esc(c["views"])}</button><button type="button" data-gallery-mode data-value="room">{esc(c["rooms"])}</button></nav></header><div class="gallery-filters" data-gallery-filters aria-label="{esc(c["filters"])}"><label class="gallery-search-label">{esc(c["search"])}<input data-gallery-search type="search" placeholder="{esc(c["search_hint"])}" autocomplete="off"></label><div class="gallery-filter-group"><button class="gallery-filter" type="button" data-gallery-filter="access" data-value="all">{esc(c["all_access"])}</button><button class="gallery-filter" type="button" data-gallery-filter="access" data-value="free">{esc(c["free"])}</button><button class="gallery-filter" type="button" data-gallery-filter="access" data-value="supporter">{esc(c["supporter"])}</button></div><div class="gallery-filter-group"><button class="gallery-filter" type="button" data-gallery-filter="animated" data-value="true">{esc(c["animated"])}</button><button class="gallery-filter" type="button" data-gallery-filter="sound" data-value="true">{esc(c["sound"])}</button></div><button class="gallery-reset" type="button" data-gallery-reset>{esc(c["reset"])}</button></div><section class="gallery-section" data-gallery-places aria-labelledby="places-heading"><div class="gallery-section-heading"><h2 id="places-heading">{esc(c["places"])}</h2><p data-gallery-status data-gallery-count="{esc(c["count"])}" aria-live="polite"></p></div><div class="gallery-grid">{"".join(cards)}</div><div class="gallery-empty" data-gallery-empty hidden><h2>{esc(c["empty_title"])}</h2><p>{esc(c["empty_copy"])}</p><button class="gallery-reset" type="button" data-gallery-reset>{esc(c["reset"])}</button></div></section></div>'''
    return document(locale, f'{c["gallery"]} — Locus', c["intro"], '/gallery/', body)


def photo_gallery(place: dict, locale: str) -> str:
    photos = place.get("photos") or []
    if not photos:
        return f'<figure class="gallery-detail-media">{image_markup(place["image"], place["title"], "eager", "gallery-detail-image")}</figure>'
    c = COPY[locale]
    first = photos[0]
    photo_data = json.dumps(photos, ensure_ascii=False).replace('</', '<\\/')
    def label(photo: dict, index: int) -> str:
        return PHOTO_LABELS[locale].get(photo.get("label"), c["photo_counter"].format(current=index + 1, total=len(photos)))
    def thumb(photo: dict, index: int) -> str:
        caption = label(photo, index)
        alt = f'{place["title"]} — {caption}'
        return (f'<button type="button" class="gallery-photo-thumb" data-gallery-photo-thumb data-index="{index}" '
                f'aria-label="{esc(caption)}">{image_markup(photo, alt, css_class="gallery-photo-thumb-image")}</button>')
    thumbs = ''.join(thumb(photo, index) for index, photo in enumerate(photos))
    return f'''<section class="gallery-photo-gallery" data-gallery-photos data-photos="{esc(photo_data)}">
<figure class="gallery-detail-media"><button type="button" class="gallery-photo-main" data-gallery-photo-open data-template="{esc(c["open_photo"])}" aria-haspopup="dialog" aria-label="{esc(c["open_photo"].format(current=1, total=len(photos)))}">{image_markup(first, place["title"], "eager", "gallery-detail-image")}</button><figcaption>{esc(c["photos"])}</figcaption></figure>
<div class="gallery-photo-strip" aria-label="{esc(c["photo_strip"])}">{thumbs}</div>
<dialog class="gallery-photo-dialog" data-gallery-photo-dialog aria-label="{esc(place["title"])}"><button type="button" class="gallery-photo-close" data-gallery-photo-close aria-label="{esc(c["close_photo"])}">×</button><button type="button" class="gallery-photo-nav previous" data-gallery-photo-previous aria-label="{esc(c["previous_photo"])}">←</button><img data-gallery-photo-dialog-image src="{esc(first["url"])}" width="{int(first["width"])}" height="{int(first["height"])}" alt="{esc(place["title"])}"><button type="button" class="gallery-photo-nav next" data-gallery-photo-next aria-label="{esc(c["next_photo"])}">→</button><p data-gallery-photo-counter data-template="{esc(c["photo_counter"])}">{esc(c["photo_counter"].format(current=1, total=len(photos)))}</p></dialog>
</section>'''


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
    return_options = [{"id": item["id"],
                       "url": locale_url("/gallery/series/" + quote(item["id"]) + "/", locale),
                       "label": SERIES_BACK_COPY[locale].format(title=item["title"])} for item in series]
    return_data = esc(json.dumps(return_options, ensure_ascii=False))
    availability = (RELEASE_PREVIEW_COPY[locale]["available"].format(version=place["previewRelease"])
                    if place.get("previewRelease") else c["available"].format(version=version))
    cta = (f'<a class="gallery-cta" href="{APP_STORE}">{esc(c["get_app"])}</a>'
           if not place.get("previewRelease") else '')
    body = f'''<div class="gallery-detail">{photo_gallery(place, locale)}<section class="gallery-detail-copy"><p class="kicker">{esc(c[place["type"]])}</p><h1>{esc(place["title"])}</h1><p>{esc(description)}</p><div class="gallery-meta">{meta}</div>{membership_markup}<p>{esc(availability)}</p>{cta}<a class="gallery-back" data-gallery-back data-gallery-return-options="{return_data}" href="{locale_url("/gallery/", locale)}">← {esc(c["back"])}</a></section></div>{credits_markup(place, locale)}'''
    return document(locale, f'{place["title"]} — {c["gallery"]} — Locus', description, f'/gallery/place/{quote(place["slug"])}/', body)


def series_page(item: dict, places: list[dict], locale: str) -> str:
    c = COPY[locale]
    members = newest_first([place for place in places if place["id"] in item.get("members", [])])
    image = series_image(item, places)
    hero = f'<figure class="gallery-detail-media">{image_markup(image, item["title"], "eager")}</figure>' if image else ''
    body = f'''<div class="gallery-detail"><section class="gallery-detail-copy"><p class="kicker">{esc(c["series"])}</p><h1>{esc(item["title"])}</h1><p>{esc(item.get("description", c["series_intro"]))}</p><a class="gallery-back" href="{locale_url("/gallery/", locale)}">← {esc(c["back"])}</a></section>{hero}</div><section class="gallery-series-members"><div class="gallery-section-heading"><h2>{esc(c["members"])}</h2></div><div class="gallery-grid">{"".join(place_card(place, locale, return_series=item["id"]) for place in members)}</div></section>'''
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
