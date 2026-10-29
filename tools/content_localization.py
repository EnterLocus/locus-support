#!/usr/bin/env python3
"""Validation and staging helpers for optional Package-v2 display text.

Localized text deliberately has no effect on a package's capabilities or
minimum-app requirement.  It is authoring metadata: a reader which does not
understand it continues to use the package's English fields.
"""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any, Mapping


class LocalizationError(ValueError):
    pass


_LANGUAGE = re.compile(r"^[a-z]{2,3}$")
_SCRIPT = re.compile(r"^[A-Z][a-z]{3}$")
_REGION = re.compile(r"^(?:[A-Z]{2}|[0-9]{3})$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")

# Ordered tuples, not sets: validate_localizations copies fields in this order
# into packaged manifests, and string-set iteration order changes with
# PYTHONHASHSEED, which made identical builds produce different bytes.
TEXT_FIELDS = ("title", "caption", "libraryCaption")
LABEL_FIELDS = (
    "seatTitles", "seatGroupTitles", "soundTitles", "mediaTitles",
    "lightTitles", "animationTitles", "videoTitles", "particleTitles",
)
LOCALIZATION_FIELDS = frozenset(TEXT_FIELDS + ("searchTerms",) + LABEL_FIELDS)
MAX_LOCALIZATIONS = 32
MAX_SEARCH_TERMS = 64
MAX_LABELS = 256


def official_offer_records(repo: Path, source=None) -> dict[str, dict[str, Any]]:
    """Read the explicit official/Dev audit scope without changing publication.

    Main offers remain authoritative. Dev-only records supplement them; older
    overlays must not replace current main metadata. Missing overlays are valid
    in small fixtures and older checkouts. Never scan historical offer files.
    """
    if source is None:
        source = json.loads((repo / "catalog/library-offers.json").read_text(encoding="utf-8"))
    documents = [("library-offers.json", source)]
    for name in ("weekly-coastal-dev-offers.json", "dev-view-updates-20261007-offers.json"):
        path = repo / "catalog" / name
        if path.is_file():
            documents.append((name, json.loads(path.read_text(encoding="utf-8"))))
    records = {}
    for name, document in documents:
        require(isinstance(document, dict) and isinstance(document.get("offers"), list),
                name + " must contain an offers list")
        for offer in document["offers"]:
            require(isinstance(offer, dict), name + " offer must be an object")
            package_id = offer.get("packageID")
            _identifier(package_id, name + " package")
            records.setdefault(package_id, copy.deepcopy(offer))
    bundled_ids = set(source.get("legacyIncludedPackageIDs", []))
    for name in ("development.json", "release.json"):
        path = repo / "catalog" / name
        if path.is_file():
            document = json.loads(path.read_text(encoding="utf-8"))
            bundled_ids.update(item["id"] for item in document.get("packages", [])
                               if isinstance(item, dict) and isinstance(item.get("id"), str))
    for package_id in sorted(bundled_ids):
        records.setdefault(package_id, {"packageID": package_id, "access": "included",
                                        "searchTerms": []})
    return records


def selected_package_ids(official_ids, requested=None):
    """Limit resource coverage only, rejecting typos instead of hiding them."""
    if requested is None:
        return set(official_ids)
    selected = set(requested)
    unknown = sorted(selected - set(official_ids))
    require(not unknown, "unknown requested package ID: " + ", ".join(unknown))
    return selected


def require(condition: bool, message: str) -> None:
    if not condition:
        raise LocalizationError(message)


def canonical_language_tag(value: Any) -> str:
    """Return the supported canonical BCP-47 casing, or reject it.

    Package display metadata needs predictable keys, not a full BCP-47 parser:
    language plus optional script and region is enough for catalog
    and app selection, while explicitly preventing duplicate equivalent keys.
    """
    require(isinstance(value, str) and value, "language tag must be a non-empty string")
    pieces = value.split("-")
    require(1 <= len(pieces) <= 3 and _LANGUAGE.fullmatch(pieces[0]) is not None,
            "invalid language tag")
    normalized = [pieces[0].lower()]
    saw_script = False
    saw_region = False
    for piece in pieces[1:]:
        if _SCRIPT.fullmatch(piece):
            require(not saw_script and not saw_region, "invalid language tag order")
            normalized.append(piece.title())
            saw_script = True
        elif _REGION.fullmatch(piece):
            require(not saw_region, "invalid language tag order")
            normalized.append(piece.upper())
            saw_region = True
        else:
            raise LocalizationError("invalid language tag")
    canonical = "-".join(normalized)
    require(value == canonical, "language tag must use canonical BCP-47 casing")
    return canonical


def _text(value: Any, context: str, maximum: int) -> None:
    require(isinstance(value, str) and value == value.strip() and value,
            context + " must be non-empty trimmed text")
    require(len(value) <= maximum, context + " exceeds text limit")
    require(not any(ord(character) < 32 and character not in "\n\t" for character in value),
            context + " contains control characters")


def _identifier(value: Any, context: str) -> None:
    require(isinstance(value, str) and _IDENTIFIER.fullmatch(value) is not None,
            context + " has an invalid ID")


def validate_localizations(
    value: Any,
    *,
    references: Mapping[str, set[str]] | None = None,
    context: str = "localizations",
) -> dict[str, dict[str, Any]]:
    """Validate and copy a manifest or catalog localization map.

    ``references`` associates a label-map field with IDs declared by the
    package.  Missing fields are valid; a provided label must name a real ID.
    """
    require(isinstance(value, dict) and len(value) <= MAX_LOCALIZATIONS,
            context + " must be an object with at most 32 languages")
    result: dict[str, dict[str, Any]] = {}
    references = references or {}
    for language, localized in value.items():
        canonical = canonical_language_tag(language)
        require(canonical not in result, context + " has duplicate language")
        require(isinstance(localized, dict) and localized,
                context + "." + canonical + " must be a non-empty object")
        unknown = set(localized) - LOCALIZATION_FIELDS
        if unknown:
            raise LocalizationError(
                context + "." + canonical + " has unknown field " + sorted(unknown)[0])
        copy_value: dict[str, Any] = {}
        for field in TEXT_FIELDS:
            if field in localized:
                _text(localized[field], context + "." + canonical + "." + field,
                      200 if field == "title" else (500 if field == "libraryCaption" else 10_000))
                copy_value[field] = localized[field]
        if "searchTerms" in localized:
            terms = localized["searchTerms"]
            require(isinstance(terms, list) and 0 < len(terms) <= MAX_SEARCH_TERMS,
                    context + "." + canonical + ".searchTerms must be a non-empty bounded list")
            for term in terms:
                _text(term, context + "." + canonical + ".searchTerms", 200)
            require(len(set(terms)) == len(terms),
                    context + "." + canonical + ".searchTerms contains duplicates")
            copy_value["searchTerms"] = list(terms)
        for field in LABEL_FIELDS:
            if field not in localized:
                continue
            labels = localized[field]
            require(isinstance(labels, dict) and 0 < len(labels) <= MAX_LABELS,
                    context + "." + canonical + "." + field + " must be a non-empty bounded object")
            allowed = references.get(field)
            checked: dict[str, str] = {}
            for item_id, label in labels.items():
                _identifier(item_id, context + "." + canonical + "." + field)
                if allowed is not None:
                    require(item_id in allowed,
                            context + "." + canonical + "." + field + " references unknown ID " + item_id)
                _text(label, context + "." + canonical + "." + field + "." + item_id, 200)
                checked[item_id] = label
            copy_value[field] = checked
        require(copy_value, context + "." + canonical + " has no display fields")
        result[canonical] = copy_value
    return result


def load_registry(path: Path) -> dict[str, dict[str, dict[str, Any]]]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise LocalizationError("cannot read localization registry %s: %s" % (path, error)) from error
    require(isinstance(document, dict) and set(document) == {"formatVersion", "packages"}
            and document["formatVersion"] == 1, "invalid localization registry")
    packages = document["packages"]
    require(isinstance(packages, dict), "localization registry packages must be an object")
    result: dict[str, dict[str, dict[str, Any]]] = {}
    for package_id, localizations in packages.items():
        _identifier(package_id, "localization registry package")
        result[package_id] = validate_localizations(
            localizations, context="localization registry." + package_id)
    return result


def merge_localizations(
    manifest: Mapping[str, Any],
    registry_localizations: Mapping[str, Mapping[str, Any]] | None,
    *,
    references: Mapping[str, set[str]] | None = None,
    context: str = "localizations",
) -> dict[str, Any]:
    """Return a copy with registry values merged into optional manifest text.

    Registry translations intentionally replace equal-language source entries:
    it is the reviewed official source of truth.  No registry entry means the
    input manifest is preserved after strict validation.
    """
    result = copy.deepcopy(dict(manifest))
    existing = result.get("localizations", {})
    existing_checked = validate_localizations(existing, references=references,
                                               context=context) if existing else {}
    registry_checked = validate_localizations(
        registry_localizations or {}, references=references, context=context)
    merged = dict(existing_checked)
    merged.update(registry_checked)
    if merged:
        result["localizations"] = merged
    elif "localizations" in result:
        del result["localizations"]
    return result
