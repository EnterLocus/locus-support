#!/usr/bin/env python3
"""Validate a public Locus Room or View ZIP without installing it."""

from __future__ import annotations

import argparse
import json
import math
import shutil
import stat
import subprocess
import sys
import tempfile
import unicodedata
import urllib.parse
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

# Support both direct CLI use and import-by-path test runners.
_TOOLS_DIRECTORY = str(Path(__file__).resolve().parent)
if _TOOLS_DIRECTORY not in sys.path:
    sys.path.insert(0, _TOOLS_DIRECTORY)

from content_localization import LABEL_FIELDS, LocalizationError, validate_localizations


ARCHIVE_BYTES = 1_073_741_824
FILE_BYTES = 805_306_368
TOTAL_BYTES = 2_147_483_648
JSON_BYTES = 1_048_576
PROVENANCE_BYTES = 65_536
ENTRY_COUNT = 4_096
COMPRESSION_RATIO = 200
COMPONENT_BYTES = 128
IMAGE_DIMENSION = 32_768
IMAGE_PIXELS = 150_000_000
MODEL_TEXTURE_DIMENSION = 16_384
MODEL_TEXTURE_PIXELS = 500_000_000
MODEL_ENTRIES = 4_096
MODEL_EXPANDED_BYTES = 1_610_612_736
IDENTIFIER_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
)
ROOM_FILES = {
    "space.json",
    "provenance.json",
    "teleport-points.json",
    "scene.usdz",
    "thumbnail.jpg",
}
VIEW_REQUIRED_FILES = {
    "view.json",
    "provenance.json",
    "panorama.jpg",
    "thumbnail.jpg",
}
VIEW_OPTIONAL_FILES = {"lighting.jpg", "point-lights.json"}
USDZ_EXTENSIONS = {
    "usd", "usda", "usdc", "png", "jpg", "jpeg", "exr", "m4a", "wav", "mp3"
}


class ValidationError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def finite(value: Any) -> bool:
    return type(value) in {int, float} and math.isfinite(value)


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValidationError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def decode_json(path: Path, name: str) -> dict[str, Any]:
    require(path.stat().st_size <= JSON_BYTES, f"{name} exceeds the JSON byte limit")
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=unique_object,
            parse_constant=lambda raw: (_ for _ in ()).throw(
                ValidationError(f"{name} contains non-standard number {raw}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError(f"{name} is not valid UTF-8 JSON: {error}") from error
    require(isinstance(value, dict), f"{name} root must be an object")
    return value


def exact_keys(
    value: dict[str, Any],
    *,
    required: set[str],
    optional: set[str] = frozenset(),
    context: str,
) -> None:
    unknown = set(value) - required - optional
    missing = required - set(value)
    if unknown:
        raise ValidationError(f"{context} has unsupported field {sorted(unknown)[0]}")
    if missing:
        raise ValidationError(f"{context} is missing field {sorted(missing)[0]}")


def require_text(value: Any, field: str, maximum: int) -> None:
    require(
        isinstance(value, str)
        and bool(value.strip())
        and len(value.encode("utf-8")) <= maximum,
        f"{field} is missing or too long",
    )


def require_https(value: Any, field: str) -> None:
    require(isinstance(value, str), f"{field} must be an HTTPS URL")
    parsed = urllib.parse.urlsplit(value)
    require(
        parsed.scheme.lower() == "https"
        and bool(parsed.hostname)
        and parsed.username is None
        and parsed.password is None
        and not parsed.fragment,
        f"{field} must be an HTTPS URL without credentials or a fragment",
    )


def valid_identifier(value: Any) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and len(value.encode("utf-8")) <= 128
        and value[0].isascii()
        and value[0].isalnum()
        and all(character in IDENTIFIER_CHARS for character in value)
    )


def safe_root_name(value: str) -> bool:
    return (
        bool(value)
        and "/" not in value
        and "\\" not in value
        and value not in {".", ".."}
        and value == unicodedata.normalize("NFC", value)
        and len(value.encode("utf-8")) <= COMPONENT_BYTES
        and not any(ord(character) < 32 or ord(character) == 127 for character in value)
    )


def is_symlink(info: zipfile.ZipInfo) -> bool:
    return stat.S_IFMT(info.external_attr >> 16) == stat.S_IFLNK


def extract_archive(source: Path, destination: Path) -> set[str]:
    require(source.is_file() and not source.is_symlink(), "source must be a regular ZIP file")
    require(source.stat().st_size <= ARCHIVE_BYTES, "ZIP exceeds the archive byte limit")
    try:
        archive = zipfile.ZipFile(source)
    except zipfile.BadZipFile as error:
        raise ValidationError(f"file is not a readable ZIP: {error}") from error
    with archive:
        infos = archive.infolist()
        require(len(infos) <= ENTRY_COUNT, "ZIP contains too many entries")
        seen: set[str] = set()
        total = 0
        for info in infos:
            require(not info.is_dir(), f"directories are not allowed: {info.filename}")
            require(not is_symlink(info), f"symbolic links are not allowed: {info.filename}")
            require(safe_root_name(info.filename), f"nested or unsafe entry: {info.filename}")
            key = unicodedata.normalize("NFC", info.filename).casefold()
            require(key not in seen, f"duplicate or colliding entry: {info.filename}")
            seen.add(key)
            require(info.file_size <= FILE_BYTES, f"file exceeds byte limit: {info.filename}")
            total += info.file_size
            require(total <= TOTAL_BYTES, "ZIP expands beyond the total byte limit")
            if info.file_size:
                require(info.compress_size > 0, f"invalid compression: {info.filename}")
                require(
                    info.file_size <= info.compress_size * COMPRESSION_RATIO,
                    f"suspicious compression ratio: {info.filename}",
                )
            target = destination / info.filename
            written = 0
            try:
                with archive.open(info) as input_file, target.open("xb") as output:
                    while chunk := input_file.read(1024 * 1024):
                        written += len(chunk)
                        require(written <= info.file_size, f"entry expanded past size: {info.filename}")
                        output.write(chunk)
            except (RuntimeError, zipfile.BadZipFile) as error:
                raise ValidationError(f"could not extract {info.filename}: {error}") from error
            require(written == info.file_size, f"entry size changed: {info.filename}")
        return {info.filename for info in infos}


def validate_provenance(path: Path) -> None:
    require(path.stat().st_size <= PROVENANCE_BYTES, "provenance.json exceeds its byte limit")
    value = decode_json(path, "provenance.json")
    exact_keys(
        value,
        required={
            "formatVersion", "creatorOrAgency", "requestedCredit",
            "modificationNotes", "aiGenerated",
        },
        optional={
            "sourcePageURL", "originalAssetURL", "license", "rights",
            "aiProvider",
        },
        context="provenance.json",
    )
    require(value["formatVersion"] == 1 and type(value["formatVersion"]) is int,
            "provenance.json.formatVersion must be 1")
    require_text(value["creatorOrAgency"], "creatorOrAgency", 200)
    require_text(value["requestedCredit"], "requestedCredit", 1_000)
    require_text(value["modificationNotes"], "modificationNotes", 2_000)
    require(type(value["aiGenerated"]) is bool, "aiGenerated must be boolean")
    has_license = "license" in value
    has_rights = "rights" in value
    require(
        has_license != has_rights,
        "provenance.json must contain exactly one of license or rights",
    )
    if has_license:
        license_value = value["license"]
        require(isinstance(license_value, dict), "license must be an object")
        exact_keys(
            license_value,
            required={"identifier", "name", "url"},
            context="provenance.json.license",
        )
        require_text(license_value["identifier"], "license.identifier", 100)
        require_text(license_value["name"], "license.name", 200)
        require_https(license_value["url"], "license.url")
    else:
        rights_value = value["rights"]
        require(isinstance(rights_value, dict), "rights must be an object")
        exact_keys(
            rights_value,
            required={"statement", "url"},
            context="provenance.json.rights",
        )
        require_text(rights_value["statement"], "rights.statement", 1_000)
        require_https(rights_value["url"], "rights.url")
    for field in ("sourcePageURL", "originalAssetURL"):
        if field in value:
            require_https(value[field], field)
    if value["aiGenerated"]:
        require_text(value.get("aiProvider"), "aiProvider", 200)
    else:
        require("aiProvider" not in value, "aiProvider requires aiGenerated=true")


def require_number_list(value: Any, count: int, field: str) -> None:
    require(
        isinstance(value, list) and len(value) == count and all(finite(item) for item in value),
        f"{field} must contain {count} finite numbers",
    )


def validate_pose(value: Any, field: str) -> None:
    require(isinstance(value, dict), f"{field} must be an object")
    exact_keys(
        value,
        required={"translationMeters", "orientationXYZW"},
        context=field,
    )
    require_number_list(value["translationMeters"], 3, f"{field}.translationMeters")
    require_number_list(value["orientationXYZW"], 4, f"{field}.orientationXYZW")


def validate_image(path: Path, *, equirectangular: bool,
                   maximum_dimension: int = IMAGE_DIMENSION) -> tuple[int, int]:
    sips = shutil.which("sips")
    require(sips is not None, "macOS sips is required to validate images")
    try:
        metadata = subprocess.run(
            [sips, "-g", "pixelWidth", "-g", "pixelHeight", str(path)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise ValidationError(f"image inspection timed out: {path.name}") from error
    require(metadata.returncode == 0, f"image cannot be decoded: {path.name}")
    properties = {}
    for line in metadata.stdout.splitlines():
        if ":" in line:
            key, raw = line.strip().split(":", 1)
            properties[key] = raw.strip()
    try:
        width = int(properties["pixelWidth"])
        height = int(properties["pixelHeight"])
    except (KeyError, ValueError) as error:
        raise ValidationError(f"image dimensions unavailable: {path.name}") from error
    require(
        0 < width <= maximum_dimension
        and 0 < height <= maximum_dimension
        and width * height <= IMAGE_PIXELS,
        f"image exceeds dimension or pixel limit: {path.name}",
    )
    if equirectangular:
        require(width == 2 * height, f"{path.name} must be a 2:1 equirectangular image")
    with tempfile.TemporaryDirectory(prefix="locus-image-") as directory:
        output = Path(directory) / "decoded.png"
        decoded = subprocess.run(
            [sips, "-s", "format", "png", "-z", "1", "2", str(path), "--out", str(output)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=180,
            check=False,
        )
        require(decoded.returncode == 0 and output.is_file() and output.stat().st_size > 0,
                f"image pixel payload cannot be decoded: {path.name}")
    return width, height


def safe_model_path(raw: str, directory: bool) -> bool:
    value = raw[:-1] if directory and raw.endswith("/") else raw
    components = value.split("/")
    return (
        bool(value)
        and value == unicodedata.normalize("NFC", value)
        and not value.startswith("/")
        and "\\" not in value
        and all(
            component not in {"", ".", ".."}
            and len(component.encode("utf-8")) <= COMPONENT_BYTES
            and not any(ord(character) < 32 or ord(character) == 127
                        for character in component)
            for component in components
        )
    )


def validate_usdz(path: Path) -> None:
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile as error:
        raise ValidationError("scene.usdz is not a valid USDZ archive") from error
    with archive:
        infos = archive.infolist()
        require(0 < len(infos) <= MODEL_ENTRIES, "scene.usdz has too many entries")
        expanded = 0
        texture_pixels = 0
        root_layer = False
        seen: set[str] = set()
        for info in infos:
            require(not is_symlink(info), f"USDZ symlink is not allowed: {info.filename}")
            require(safe_model_path(info.filename, info.is_dir()),
                    f"unsafe USDZ path: {info.filename}")
            key = unicodedata.normalize("NFC", info.filename.rstrip("/")).casefold()
            require(key not in seen, f"duplicate USDZ path: {info.filename}")
            seen.add(key)
            if info.is_dir():
                continue
            require(info.compress_type == zipfile.ZIP_STORED,
                    f"USDZ entry must be stored without compression: {info.filename}")
            expanded += info.file_size
            require(expanded <= MODEL_EXPANDED_BYTES, "scene.usdz exceeds expanded byte limit")
            extension = PurePosixPath(info.filename).suffix.lower().lstrip(".")
            require(extension in USDZ_EXTENSIONS, f"unsupported USDZ file: {info.filename}")
            if extension in {"png", "jpg", "jpeg", "exr"}:
                with tempfile.TemporaryDirectory(prefix="locus-model-texture-") as directory:
                    texture = Path(directory) / ("texture." + extension)
                    with archive.open(info) as source, texture.open("wb") as output:
                        shutil.copyfileobj(source, output)
                    width, height = validate_image(
                        texture, equirectangular=False,
                        maximum_dimension=MODEL_TEXTURE_DIMENSION)
                texture_pixels += width * height
                require(texture_pixels <= MODEL_TEXTURE_PIXELS,
                        "scene.usdz exceeds the total model texture pixel limit")
            if "/" not in info.filename and extension in {"usd", "usda", "usdc"}:
                root_layer = True
        require(root_layer, "scene.usdz has no root USD layer")

    checker = shutil.which("usdchecker")
    require(checker is not None, "usdchecker is required to validate scene.usdz")
    try:
        checked = subprocess.run(
            [checker, "--arkit", str(path)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=120,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise ValidationError("scene.usdz validation timed out") from error
    require(checked.returncode == 0, "scene.usdz fails RealityKit USD validation")

# Standalone public distribution of the binding contract and resolver used by
# Locus import. Keep this native source synchronized with the app's
# RoomEntityBindings.swift, RoomModelBindingValidator.swift and CLI entry point.
ROOM_BINDING_SWIFT = r"""
import Foundation
import RealityKit

/// Resolves an explicit author interface before committing a Room load.
/// Names are exact identities, never material or size classification rules.
@MainActor
enum RoomEntityBindings {
    enum BindingError: LocalizedError, Equatable {
        case missing(String)
        case ambiguous(String)
        case overlapping(String, String)
        case noGeometry(String)

        var errorDescription: String? {
            switch self {
            case .missing(let name): "Room entity '\(name)' was not found."
            case .ambiguous(let name): "Room entity '\(name)' is not uniquely named."
            case .overlapping(let first, let second):
                "Room bindings '\(first)' and '\(second)' overlap in the model hierarchy."
            case .noGeometry(let name): "Room entity '\(name)' has no renderable geometry."
            }
        }
    }

    static func entity(named name: String, in root: Entity) throws -> Entity {
        var matches: [Entity] = []
        func walk(_ entity: Entity) {
            if entity.name == name { matches.append(entity) }
            entity.children.forEach(walk)
        }
        walk(root)
        guard !matches.isEmpty else { throw BindingError.missing(name) }
        guard matches.count == 1 else { throw BindingError.ambiguous(name) }
        return matches[0]
    }

    static func subtrees(named names: [String], in root: Entity) throws -> [Entity] {
        var uniqueNames = Set<String>()
        for name in names where !uniqueNames.insert(name).inserted {
            throw BindingError.ambiguous(name)
        }
        let entities = try names.map { try entity(named: $0, in: root) }
        let ids = Set(entities.map(\.id))
        for entity in entities {
            var parent = entity.parent
            while let ancestor = parent {
                guard !ids.contains(ancestor.id) else {
                    throw BindingError.overlapping(ancestor.name, entity.name)
                }
                parent = ancestor.parent
            }
            guard containsGeometry(entity) else { throw BindingError.noGeometry(entity.name) }
        }
        return entities
    }

    private static func containsGeometry(_ entity: Entity) -> Bool {
        entity.components[ModelComponent.self] != nil
            || entity.children.contains(where: containsGeometry)
    }

    static func requireNoAncestryOverlap(
        _ entity: Entity, named name: String,
        against other: Entity, named otherName: String
    ) throws {
        var current: Entity? = entity
        while let node = current {
            if node === other { throw BindingError.overlapping(otherName, name) }
            current = node.parent
        }
        current = other
        while let node = current {
            if node === entity { throw BindingError.overlapping(name, otherName) }
            current = node.parent
        }
    }
}

import Foundation
import RealityKit

/// The subset of the author contract that refers to model entities. Both the
/// public CLI and import preflight decode this, then use the runtime resolver.
/// Full schema and resource-budget validation must precede this check.
struct RoomModelBindingContract: Decodable, Sendable {
    struct Adaptation: Decodable, Sendable {
        let wallEntities: [String]
        let roofEntities: [String]
        let deskEntitiesByTeleportID: [String: String]
        let deskGroupEntitiesByTeleportID: [String: String]?
    }
    struct Rendering: Decodable, Sendable {
        let softenedReflectionEntities: [String]
        let uiFadeEntities: [String]
    }
    struct Lighting: Decodable, Sendable {
        struct Proxy: Decodable, Sendable { let anchorEntity: String }
        struct Group: Decodable, Sendable {
            let entities: [String]
            let illuminatedEntities: [String]?
            let proxy: Proxy?
            let proxies: [Proxy]?
        }
        struct Indirect: Decodable, Sendable { let entities: [String] }
        let luminaireGroups: [Group]
        let bakedIndirect: Indirect?
    }
    struct Animation: Decodable, Sendable { let entityName: String }
    struct VideoSurface: Decodable, Sendable { let entityName: String }
    struct ParticleEffect: Decodable, Sendable { let anchorEntity: String }
    let spatialAdaptation: Adaptation?
    let rendering: Rendering?
    let lighting: Lighting?
    let ambientAnimations: [Animation]?
    let videoSurfaces: [VideoSurface]?
    let particleEffects: [ParticleEffect]?

    var names: [String] {
        var names: [String] = []
        if let a = spatialAdaptation {
            names += a.wallEntities + a.roofEntities
            names += a.deskEntitiesByTeleportID.sorted { $0.key < $1.key }.map(\.value)
            names += (a.deskGroupEntitiesByTeleportID ?? [:])
                .sorted { $0.key < $1.key }.map(\.value)
        }
        if let r = rendering {
            names += r.softenedReflectionEntities + r.uiFadeEntities
        }
        if let lighting {
            for group in lighting.luminaireGroups {
                names += group.entities
                if let proxy = group.proxy { names.append(proxy.anchorEntity) }
                names += (group.proxies ?? []).map(\.anchorEntity)
            }
            names += lighting.bakedIndirect?.entities ?? []
        }
        names += (ambientAnimations ?? []).map(\.entityName)
        names += (videoSurfaces ?? []).map(\.entityName)
        names += (particleEffects ?? []).map(\.anchorEntity)
        return names
    }
}

@MainActor
enum RoomModelBindingValidator {
    static func validate(modelURL: URL, contract: RoomModelBindingContract) async throws {
        // Models without authored name references have nothing to bind. Keep
        // their existing format/budget checks without an extra GPU load.
        guard !contract.names.isEmpty else { return }
        let model = try await Entity(contentsOf: modelURL)
        try Task.checkCancellation()
        for name in Set(contract.names).sorted() {
            _ = try RoomEntityBindings.entity(named: name, in: model)
        }
        if let rendering = contract.rendering {
            _ = try RoomEntityBindings.subtrees(named: rendering.softenedReflectionEntities, in: model)
            _ = try RoomEntityBindings.subtrees(named: rendering.uiFadeEntities, in: model)
        }
        if let videoSurfaces = contract.videoSurfaces, !videoSurfaces.isEmpty {
            _ = try RoomEntityBindings.subtrees(
                named: videoSurfaces.map(\.entityName), in: model)
        }
        if let lighting = contract.lighting {
            try validateIlluminatedEntities(lighting, in: model)
        }
    }

    private static func validateIlluminatedEntities(
        _ lighting: RoomModelBindingContract.Lighting, in model: Entity
    ) throws {
        guard lighting.luminaireGroups.contains(where: {
            $0.illuminatedEntities?.isEmpty == false
        }) else { return }
        let entityNames = Set(lighting.luminaireGroups.flatMap(\.entities))
        let bakedNames = Set(lighting.bakedIndirect?.entities ?? [])
        var resolved: [String: Entity] = [:]
        func entity(named name: String) throws -> Entity {
            if let cached = resolved[name] { return cached }
            let value = try RoomEntityBindings.entity(named: name, in: model)
            resolved[name] = value
            return value
        }
        for (index, group) in lighting.luminaireGroups.enumerated()
        where group.illuminatedEntities?.isEmpty == false {
            var otherIlluminatedNames = Set<String>()
            for (otherIndex, other) in lighting.luminaireGroups.enumerated()
            where otherIndex != index {
                otherIlluminatedNames.formUnion(other.illuminatedEntities ?? [])
            }
            let protectedNames = entityNames
                .union(bakedNames)
                .union(otherIlluminatedNames)
            for illuminatedName in group.illuminatedEntities ?? [] {
                let illuminatedEntity = try entity(named: illuminatedName)
                for protectedName in protectedNames {
                    let protectedEntity = try entity(named: protectedName)
                    try RoomEntityBindings.requireNoAncestryOverlap(
                        illuminatedEntity, named: illuminatedName,
                        against: protectedEntity, named: protectedName)
                }
            }
        }
    }
}

import Foundation
import ModelIO

/// Match the app's actual-model budget check; author-declared quality numbers
/// must never substitute for inspecting the USD composition and topology.
func validateModelBudget(_ url: URL) throws {
    func reject() throws -> Never {
        throw NSError(domain: "Locus", code: 2, userInfo: [NSLocalizedDescriptionKey:
            "scene.usdz exceeds model budget (5,000,000 triangles, 1,024 materials, 100,000 entities; instances are not supported)"])
    }
    let asset = MDLAsset(url: url)
    guard asset.count > 0, asset.originals.objects.isEmpty else { try reject() }
    var pending = (0..<asset.count).map { asset.object(at: $0) }
    var entities = 0
    var triangles = 0
    var materials = Set<ObjectIdentifier>()
    while let object = pending.popLast() {
        guard object.instance == nil else { try reject() }
        entities += 1
        guard entities <= 100_000 else { try reject() }
        pending.append(contentsOf: object.children.objects)
        guard let mesh = object as? MDLMesh, let submeshes = mesh.submeshes else { continue }
        for case let submesh as MDLSubmesh in submeshes {
            let count: Int
            switch submesh.geometryType {
            case .triangles: count = submesh.indexCount / 3
            case .triangleStrips: count = max(0, submesh.indexCount - 2)
            case .quads: count = (submesh.indexCount / 4) * 2
            default: count = submesh.indexCount
            }
            let (sum, overflow) = triangles.addingReportingOverflow(count)
            guard !overflow, sum <= 5_000_000 else { try reject() }
            triangles = sum
            if let material = submesh.material { materials.insert(ObjectIdentifier(material)) }
            guard materials.count <= 1_024 else { try reject() }
        }
    }
}

/// Compiled with the same binding contract/resolver used by the visionOS app.
@main
struct ValidateRoomBindings {
    static func main() async {
        do {
            guard CommandLine.arguments.count == 3 else {
                throw NSError(domain: "Locus", code: 2, userInfo: [NSLocalizedDescriptionKey:
                    "Usage: validate-room-bindings scene.usdz space.json"])
            }
            try validateModelBudget(URL(fileURLWithPath: CommandLine.arguments[1]))
            let contract = try JSONDecoder().decode(RoomModelBindingContract.self,
                from: Data(contentsOf: URL(fileURLWithPath: CommandLine.arguments[2])))
            try await RoomModelBindingValidator.validate(
                modelURL: URL(fileURLWithPath: CommandLine.arguments[1]), contract: contract)
        } catch {
            FileHandle.standardError.write(Data((error.localizedDescription + "\n").utf8))
            exit(2)
        }
    }
}
"""

# One dedicated executable per Python process; never execute a shared cache entry.
_binding_tool_directory = None


def validate_room_bindings(model: Path, manifest: Path) -> None:
    global _binding_tool_directory
    if _binding_tool_directory is None:
        directory = tempfile.TemporaryDirectory(prefix="locus-binding-validator-")
        source = Path(directory.name) / "validate-room-bindings.swift"
        source.write_text(ROOM_BINDING_SWIFT, encoding="utf-8")
        try:
            result = subprocess.run(
                ["xcrun", "swiftc", "-parse-as-library", str(source),
                 "-o", str(Path(directory.name) / "validate-room-bindings")],
                capture_output=True, text=True, timeout=180, check=False)
        except subprocess.TimeoutExpired as error:
            raise ValidationError("Room binding validator compilation timed out") from error
        require(result.returncode == 0,
                "Could not build RealityKit binding validator (Xcode is required): " + result.stderr[-4000:])
        _binding_tool_directory = directory
    try:
        result = subprocess.run(
            [str(Path(_binding_tool_directory.name) / "validate-room-bindings"), str(model), str(manifest)],
            capture_output=True, text=True, timeout=120, check=False)
    except subprocess.TimeoutExpired as error:
        raise ValidationError("scene.usdz entity binding validation timed out") from error
    require(result.returncode == 0,
            "scene.usdz entity bindings failed: " + (result.stderr.strip()[-4000:] or "RealityKit could not load the model"))
def validate_teleports(path: Path) -> set[str]:
    value = decode_json(path, "teleport-points.json")
    exact_keys(
        value,
        required={"formatVersion", "points"},
        context="teleport-points.json",
    )
    require(value["formatVersion"] == 1 and type(value["formatVersion"]) is int,
            "teleport-points.json.formatVersion must be 1")
    points = value["points"]
    require(isinstance(points, list) and bool(points),
            "teleport-points.json must contain at least one seat")
    identifiers: set[str] = set()
    for index, point in enumerate(points):
        context = f"teleport-points.json.points[{index}]"
        require(isinstance(point, dict), f"{context} must be an object")
        exact_keys(
            point,
            required={
                "id", "title", "anchorXZ", "sourceFloorOffset", "eyeHeight",
                "yawRadians",
            },
            context=context,
        )
        require(valid_identifier(point["id"]), f"{context}.id is invalid")
        require(point["id"] not in identifiers, f"duplicate teleport id {point['id']}")
        identifiers.add(point["id"])
        require_text(point["title"], f"{context}.title", 200)
        require_number_list(point["anchorXZ"], 2, f"{context}.anchorXZ")
        require(all(0 <= number <= 1 for number in point["anchorXZ"]),
                f"{context}.anchorXZ must be normalized from 0 to 1")
        require(finite(point["sourceFloorOffset"]) and point["sourceFloorOffset"] >= 0,
                f"{context}.sourceFloorOffset is invalid")
        require(finite(point["eyeHeight"]) and point["eyeHeight"] > 0,
                f"{context}.eyeHeight is invalid")
        require(finite(point["yawRadians"]), f"{context}.yawRadians is invalid")
    return identifiers


def validate_spatial_adaptation(value: Any, teleport_ids: set[str]) -> None:
    require(isinstance(value, dict), "space.json.spatialAdaptation must be an object")
    exact_keys(
        value,
        required={"wallEntities", "roofEntities", "deskEntitiesByTeleportID"},
        optional={"deskGroupEntitiesByTeleportID"},
        context="space.json.spatialAdaptation",
    )
    walls = value["wallEntities"]
    roofs = value["roofEntities"]
    desks = value["deskEntitiesByTeleportID"]
    require(isinstance(walls, list) and all(isinstance(item, str) and item.strip() for item in walls),
            "wallEntities must contain non-empty names")
    require(isinstance(roofs, list) and all(isinstance(item, str) and item.strip() for item in roofs),
            "roofEntities must contain non-empty names")
    require(len(walls) == len(set(walls)), "wallEntities contains duplicates")
    require(len(roofs) == len(set(roofs)), "roofEntities contains duplicates")
    require(set(walls).isdisjoint(roofs), "wallEntities overlaps roofEntities")
    require(isinstance(desks, dict), "deskEntitiesByTeleportID must be an object")
    for teleport_id, entity in desks.items():
        require(teleport_id in teleport_ids and isinstance(entity, str) and entity.strip(),
                f"desk mapping is invalid for teleport {teleport_id}")
    if "deskGroupEntitiesByTeleportID" in value:
        groups = value["deskGroupEntitiesByTeleportID"]
        require(isinstance(groups, dict), "deskGroupEntitiesByTeleportID must be an object")
        for teleport_id, entity in groups.items():
            require(
                isinstance(teleport_id, str) and isinstance(entity, str) and entity.strip(),
                f"desk group mapping is invalid for teleport {teleport_id}",
            )
            require(
                teleport_id in desks,
                f"desk group mapping for teleport {teleport_id} has no desk surface",
            )


def validate_light_color(value: Any, context: str) -> None:
    require(isinstance(value, dict), f"{context} must be an object")
    exact_keys(
        value,
        required={"mode"},
        optional={"kelvin", "components"},
        context=context,
    )
    if value["mode"] == "temperature":
        require("components" not in value, f"{context} cannot mix color modes")
        require(finite(value.get("kelvin")) and 1_000 <= value["kelvin"] <= 12_000,
                f"{context}.kelvin must be between 1000 and 12000")
    elif value["mode"] == "srgb":
        require("kelvin" not in value, f"{context} cannot mix color modes")
        require_number_list(value.get("components"), 3, f"{context}.components")
        require(all(0 <= item <= 1 for item in value["components"]),
                f"{context}.components must be between 0 and 1")
    else:
        raise ValidationError(f"{context}.mode is unsupported")


def validate_proxy_light(
    proxy: Any,
    context: str,
    room_format_version: int,
) -> bool:
    require(isinstance(proxy, dict), f"{context} must be an object")
    exact_keys(
        proxy,
        required={
            "type", "anchorEntity", "intensityLumens",
            "attenuationRadiusMeters", "castsShadow",
        },
        optional={
            "colorTemperatureKelvin", "innerAngleDegrees",
            "outerAngleDegrees",
        } | ({"direction"} if room_format_version >= 5 else set()),
        context=context,
    )
    require(proxy["type"] in {"point", "spot"}, f"{context}.type is invalid")
    require_text(proxy["anchorEntity"], f"{context}.anchorEntity", 200)
    require(finite(proxy["intensityLumens"])
            and proxy["intensityLumens"] >= 0
            and (room_format_version < 3
                 or proxy["intensityLumens"] <= 10_000),
            f"{context}.intensityLumens is invalid")
    require(finite(proxy["attenuationRadiusMeters"])
            and 0 < proxy["attenuationRadiusMeters"] <= 6,
            f"{context}.attenuationRadiusMeters is invalid")
    require(type(proxy["castsShadow"]) is bool,
            f"{context}.castsShadow must be boolean")
    if "colorTemperatureKelvin" in proxy:
        require(finite(proxy["colorTemperatureKelvin"])
                and 1_000 <= proxy["colorTemperatureKelvin"] <= 12_000,
                f"{context}.colorTemperatureKelvin is invalid")
    if "direction" in proxy:
        direction = proxy["direction"]
        require_number_list(direction, 3, f"{context}.direction")
        require(abs(sum(component * component for component in direction) - 1) < 0.001,
                f"{context}.direction must be a unit vector")
        require(proxy["type"] == "spot", f"{context}.direction requires a spot light")
    if room_format_version >= 5 and proxy["type"] == "spot":
        require("direction" in proxy, f"{context}.direction is required")
    if proxy["type"] == "point":
        require(not proxy["castsShadow"],
                f"{context} point lights cannot cast shadows")
    else:
        inner = proxy.get("innerAngleDegrees", 30)
        outer = proxy.get("outerAngleDegrees", 60)
        require(finite(inner) and finite(outer)
                and 0 < inner <= outer <= 175,
                f"{context} angles are invalid")
    return proxy["castsShadow"]


def valid_light_layer_image_name(value: Any) -> bool:
    return (
        isinstance(value, str) and bool(value)
        and "/" not in value and "\\" not in value
        and value.lower().endswith(".png")
    )


def validate_baked_light_layers(
    value: Any, luminaire_group_ids: set[str]
) -> set[str]:
    """Structural shape only; every referenced `.png` is a bare root ZIP
    filename cross-checked against the actual extracted files (byte limit,
    PNG header, and matching cross-layer dimensions) by the caller, matching
    how `validate_video_surfaces` splits its own two-stage check.
    """
    require(isinstance(value, list) and value and len(value) <= 12,
            "lighting.bakedIndirect.layers must contain 1 to 12 entries")
    used_group_ids: set[str] = set()
    images: set[str] = set()
    for index, layer in enumerate(value):
        context = f"lighting.bakedIndirect.layers[{index}]"
        require(isinstance(layer, dict), f"{context} must be an object")
        exact_keys(
            layer,
            required={"luminaireGroupID", "image"},
            context=context,
        )
        group_id = layer["luminaireGroupID"]
        require(isinstance(group_id, str) and group_id in luminaire_group_ids,
                f"{context}.luminaireGroupID is unknown")
        require(group_id not in used_group_ids,
                f"{context}.luminaireGroupID is already used by another layer")
        used_group_ids.add(group_id)
        image = layer["image"]
        require(valid_light_layer_image_name(image), f"{context}.image is invalid")
        require(image not in images, f"duplicate light layer image {image}")
        images.add(image)
    return images


def read_png_ihdr(path: Path) -> tuple[int, int, int, int]:
    """(width, height, bit depth, color type) from a PNG's leading IHDR
    chunk. Header-only: this checks shape and encoding, not that the
    compressed pixel payload itself is well-formed (the pipeline that
    produces these atlases is trusted the same way `videoSurfaces`' `.mp4`
    only gets an `ftyp` header check, not a full decode).
    """
    with path.open("rb") as handle:
        header = handle.read(33)
    require(len(header) == 33 and header[:8] == b"\x89PNG\r\n\x1a\n",
            f"{path.name} is not a PNG file")
    require(header[12:16] == b"IHDR", f"{path.name} has no leading IHDR chunk")
    width = int.from_bytes(header[16:20], "big")
    height = int.from_bytes(header[20:24], "big")
    bit_depth = header[24]
    color_type = header[25]
    return width, height, bit_depth, color_type


def validate_light_layer_image(path: Path) -> tuple[int, int]:
    width, height, bit_depth, color_type = read_png_ihdr(path)
    require(0 < width <= 4096 and 0 < height <= 4096,
            f"{path.name} exceeds the 4096x4096 light layer dimension limit")
    require(bit_depth in (8, 16) and color_type in (2, 6),
            f"{path.name} must be an 8- or 16-bit RGB or RGBA PNG")
    return width, height


def validate_lighting(
    value: Any,
    teleport_ids: set[str],
    room_format_version: int,
) -> set[str]:
    require(isinstance(value, dict), "space.json.lighting must be an object")
    exact_keys(
        value,
        required={"luminaireGroups"},
        optional={"bakedIndirect"} if room_format_version >= 3 else set(),
        context="space.json.lighting",
    )
    groups = value["luminaireGroups"]
    require(isinstance(groups, list) and groups,
            "lighting.luminaireGroups must not be empty")
    identifiers: set[str] = set()
    proxy_count = 0
    unscoped_proxy_count = 0
    scoped_proxy_counts = {teleport_id: 0 for teleport_id in teleport_ids}
    shadowing_count = 0
    luminaire_entities: set[str] = set()
    for index, group in enumerate(groups):
        context = f"lighting.luminaireGroups[{index}]"
        require(isinstance(group, dict), f"{context} must be an object")
        group_optional = {"nearTeleportIDs", "authoredColor", "proxy"}
        if room_format_version >= 3:
            group_optional.add("proxies")
        if room_format_version >= 8:
            group_optional.add("illuminatedEntities")
        exact_keys(
            group,
            required={"id", "displayName", "entities", "controls"},
            optional=group_optional,
            context=context,
        )
        require(valid_identifier(group["id"]), f"{context}.id is invalid")
        require(group["id"] not in identifiers, f"duplicate light id {group['id']}")
        identifiers.add(group["id"])
        require_text(group["displayName"], f"{context}.displayName", 200)
        entities = group["entities"]
        require(isinstance(entities, list) and entities
                and all(isinstance(item, str) and item.strip() for item in entities),
                f"{context}.entities must contain names")
        require(len(entities) == len(set(entities)), f"{context}.entities has duplicates")
        require(luminaire_entities.isdisjoint(entities),
                f"{context}.entities belongs to another lighting group")
        luminaire_entities.update(entities)
        if "illuminatedEntities" in group:
            # Room v8: surfaces an authored emissive texture washes with this
            # group's light (a cove-lit wall) rather than the fixture itself.
            # Exact-name overlap only; ancestor/descendant containment needs
            # the live USDZ hierarchy and is checked by
            # `validate_room_bindings` (RealityKit), not here.
            illuminated = group["illuminatedEntities"]
            require(isinstance(illuminated, list) and illuminated
                    and all(isinstance(item, str) and item.strip() for item in illuminated),
                    f"{context}.illuminatedEntities must contain names")
            require(len(illuminated) == len(set(illuminated)),
                    f"{context}.illuminatedEntities has duplicates")
            require(luminaire_entities.isdisjoint(illuminated),
                    f"{context}.illuminatedEntities belongs to another lighting group")
            luminaire_entities.update(illuminated)
        near: list[str] | None = None
        if "nearTeleportIDs" in group:
            near = group["nearTeleportIDs"]
            require(isinstance(near, list),
                    f"{context}.nearTeleportIDs is invalid")
            require(all(isinstance(item, str) and item.strip() for item in near)
                    and (room_format_version < 3 or bool(near))
                    and len(near) == len(set(near))
                    and set(near).issubset(teleport_ids),
                    f"{context}.nearTeleportIDs is invalid")
        if "authoredColor" in group:
            validate_light_color(group["authoredColor"], f"{context}.authoredColor")
        controls = group["controls"]
        require(isinstance(controls, dict), f"{context}.controls must be an object")
        exact_keys(
            controls,
            required={"brightnessEVRange", "supportsFullColor"},
            optional={"temperatureKelvinRange"},
            context=f"{context}.controls",
        )
        brightness = controls["brightnessEVRange"]
        require_number_list(brightness, 2, f"{context}.controls.brightnessEVRange")
        brightness_minimum = -4 if room_format_version >= 3 else -8
        brightness_maximum = 1 if room_format_version >= 3 else 4
        require(brightness_minimum <= brightness[0]
                <= brightness[1] <= brightness_maximum,
                f"{context}.controls.brightnessEVRange is invalid")
        require(type(controls["supportsFullColor"]) is bool,
                f"{context}.controls.supportsFullColor must be boolean")
        if "temperatureKelvinRange" in controls:
            temperature = controls["temperatureKelvinRange"]
            require_number_list(temperature, 2, f"{context}.controls.temperatureKelvinRange")
            require(1_000 <= temperature[0] <= temperature[1] <= 12_000,
                    f"{context}.controls.temperatureKelvinRange is invalid")
        require(not ("proxy" in group and "proxies" in group),
                f"{context} cannot contain both proxy and proxies")
        if "proxies" in group:
            require(isinstance(group["proxies"], list) and group["proxies"],
                    f"{context}.proxies must be a non-empty array")
            proxy_fields = [
                (proxy, f"{context}.proxies[{proxy_index}]")
                for proxy_index, proxy in enumerate(group["proxies"])
            ]
        elif "proxy" in group:
            proxy_fields = [(group["proxy"], f"{context}.proxy")]
        else:
            proxy_fields = []
        proxy_count += len(proxy_fields)
        if near:
            for teleport_id in near:
                scoped_proxy_counts[teleport_id] += len(proxy_fields)
        else:
            unscoped_proxy_count += len(proxy_fields)
        for proxy, proxy_context in proxy_fields:
            if validate_proxy_light(proxy, proxy_context, room_format_version):
                shadowing_count += 1
    require(proxy_count <= 12, "lighting exceeds the twelve-authored-proxy budget")
    require(unscoped_proxy_count <= 4
            and all(unscoped_proxy_count + count <= 4
                    for count in scoped_proxy_counts.values()),
            "lighting exceeds the four-active-proxy budget")
    require(shadowing_count <= 1,
            "lighting exceeds the one-shadow-light budget")
    referenced_layer_images: set[str] = set()
    if "bakedIndirect" in value:
        require(room_format_version >= 3,
                "lighting.bakedIndirect requires space.json formatVersion 3")
        baked = value["bakedIndirect"]
        require(isinstance(baked, dict), "lighting.bakedIndirect must be an object")
        exact_keys(
            baked,
            required={"entities"},
            optional={"layers"} if room_format_version >= 10 else set(),
            context="lighting.bakedIndirect",
        )
        entities = baked["entities"]
        require(isinstance(entities, list) and entities
                and all(isinstance(item, str) and item.strip() for item in entities),
                "lighting.bakedIndirect.entities must contain names")
        require(len(entities) == len(set(entities)),
                "lighting.bakedIndirect.entities has duplicates")
        require(luminaire_entities.isdisjoint(entities),
                "lighting.bakedIndirect.entities must not name luminaires")
        if "layers" in baked:
            # Room v10 (docs/locus-asset-format.md "Room baked light
            # layers"): one PNG per declared luminaire group, holding that
            # group's own contribution to the shared bakedIndirect atlas.
            # Structural shape only; PNG header/byte checks on the
            # referenced files happen against the real extracted bytes in
            # `validate_room`, matching how `videoSurfaces` checks `.mp4`.
            referenced_layer_images = validate_baked_light_layers(
                baked["layers"], identifiers)
    return referenced_layer_images


def validate_number_range(
    value: Any,
    field: str,
    minimum: float,
    maximum: float,
) -> tuple[float, float]:
    require_number_list(value, 2, field)
    require(minimum <= value[0] <= value[1] <= maximum,
            f"{field} is invalid")
    return value[0], value[1]


def validate_ambient_animations(value: Any) -> None:
    require(isinstance(value, list) and value,
            "space.json.ambientAnimations must be a non-empty array")
    identifiers: set[str] = set()
    for index, animation in enumerate(value):
        context = f"space.json.ambientAnimations[{index}]"
        require(isinstance(animation, dict), f"{context} must be an object")
        exact_keys(
            animation,
            required={
                "id", "displayName", "entityName", "animationName",
                "isEnabledByDefault", "defaultSpeed", "speedRange",
                "defaultIntervalRangeSeconds", "intervalRangeSeconds",
            },
            context=context,
        )
        require(valid_identifier(animation["id"]), f"{context}.id is invalid")
        require(animation["id"] not in identifiers,
                f"duplicate ambient animation id {animation['id']}")
        identifiers.add(animation["id"])
        for field in ("displayName", "entityName", "animationName"):
            require_text(animation[field], f"{context}.{field}", 200)
        require(type(animation["isEnabledByDefault"]) is bool,
                f"{context}.isEnabledByDefault must be boolean")
        speed = validate_number_range(
            animation["speedRange"], f"{context}.speedRange", 0.25, 2)
        require(finite(animation["defaultSpeed"])
                and speed[0] <= animation["defaultSpeed"] <= speed[1],
                f"{context}.defaultSpeed is invalid")
        default_interval = validate_number_range(
            animation["defaultIntervalRangeSeconds"],
            f"{context}.defaultIntervalRangeSeconds", 0, 3_600)
        interval = validate_number_range(
            animation["intervalRangeSeconds"],
            f"{context}.intervalRangeSeconds", 0, 3_600)
        require(interval[0] <= default_interval[0]
                and default_interval[1] <= interval[1],
                f"{context}.defaultIntervalRangeSeconds exceeds its allowed range")


def valid_video_surface_identifier(value: Any) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and len(value.encode("utf-8")) <= 64
        and all(character in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in value)
    )


PARTICLE_EFFECT_PRESETS = {"fire"}


def validate_particle_effects(value: Any) -> None:
    """Structural shape only; `anchorEntity` resolution happens in
    `validate_room_bindings` (RealityKit), matching every other authored
    entity reference in this format (see the lighting proxy `anchorEntity`).
    """
    require(isinstance(value, list) and value and len(value) <= 4,
            "space.json.particleEffects must contain 1 to 4 entries")
    identifiers: set[str] = set()
    for index, effect in enumerate(value):
        context = f"space.json.particleEffects[{index}]"
        require(isinstance(effect, dict), f"{context} must be an object")
        exact_keys(
            effect,
            required={
                "id", "displayName", "preset", "anchorEntity", "sizeMeters",
            },
            context=context,
        )
        require(valid_video_surface_identifier(effect["id"]),
                f"{context}.id is invalid")
        require(effect["id"] not in identifiers,
                f"duplicate particle effect id {effect['id']}")
        identifiers.add(effect["id"])
        require_text(effect["displayName"], f"{context}.displayName", 200)
        require(effect["preset"] in PARTICLE_EFFECT_PRESETS,
                f"{context}.preset is unknown")
        require_text(effect["anchorEntity"], f"{context}.anchorEntity", 200)
        size = effect["sizeMeters"]
        require_number_list(size, 3, f"{context}.sizeMeters")
        require(all(0 < component <= 3 for component in size),
                f"{context}.sizeMeters components must be within (0, 3]")


def validate_video_surfaces(value: Any, luminaire_groups: Any) -> set[str]:
    """Structural + reference shape only; byte limit, `ftyp` header, and
    referenced-set-equals-actual-files are checked by the caller against the
    real extracted files, and entity/geometry resolution happens in
    `validate_room_bindings` (RealityKit), matching every other authored
    entity reference in this format.
    """
    require(isinstance(value, list) and value and len(value) <= 2,
            "space.json.videoSurfaces must contain 1 or 2 surfaces")
    luminaire_group_ids = {
        group.get("id") for group in luminaire_groups if isinstance(group, dict)
    } if isinstance(luminaire_groups, list) else set()
    identifiers: set[str] = set()
    videos: set[str] = set()
    for index, surface in enumerate(value):
        context = f"space.json.videoSurfaces[{index}]"
        require(isinstance(surface, dict), f"{context} must be an object")
        exact_keys(
            surface,
            required={"id", "displayName", "entityName", "video"},
            optional={"luminaireGroupID"},
            context=context,
        )
        require(valid_video_surface_identifier(surface["id"]), f"{context}.id is invalid")
        require(surface["id"] not in identifiers,
                f"duplicate video surface id {surface['id']}")
        identifiers.add(surface["id"])
        require_text(surface["displayName"], f"{context}.displayName", 200)
        require_text(surface["entityName"], f"{context}.entityName", 200)
        video = surface["video"]
        require(
            isinstance(video, str) and video
            and "/" not in video and "\\" not in video
            and video.lower().endswith(".mp4"),
            f"{context}.video is invalid",
        )
        require(video not in videos, f"duplicate video surface file {video}")
        videos.add(video)
        if "luminaireGroupID" in surface:
            require(surface["luminaireGroupID"] in luminaire_group_ids,
                    f"{context}.luminaireGroupID is unknown")
    return videos


def validate_rendering(value: Any) -> None:
    context = "space.json.rendering"
    require(isinstance(value, dict), f"{context} must be an object")
    exact_keys(value, required={"softenedReflectionEntities", "uiFadeEntities"}, context=context)
    for field, names in value.items():
        require(isinstance(names, list), f"{context}.{field} must be an array")
        for name in names:
            require_text(name, f"{context}.{field}", 200)
        require(len(names) == len(set(names)), f"{context}.{field} contains duplicates")


def validate_seat_groups(value: Any, teleport_ids: set[str]) -> None:
    require(isinstance(value, list) and value,
            "space.json.seatGroups must be a non-empty array")
    group_ids: set[str] = set()
    grouped_seat_ids: set[str] = set()
    for index, group in enumerate(value):
        context = f"space.json.seatGroups[{index}]"
        require(isinstance(group, dict), f"{context} must be an object")
        exact_keys(
            group,
            required={"id", "title", "seatIDs"},
            context=context,
        )
        require(valid_identifier(group["id"]), f"{context}.id is invalid")
        require(group["id"] not in group_ids,
                f"{context}.id is duplicated")
        group_ids.add(group["id"])
        require_text(group["title"], f"{context}.title", 200)
        seat_ids = group["seatIDs"]
        require(isinstance(seat_ids, list) and seat_ids,
                f"{context}.seatIDs must be a non-empty array")
        for seat_index, seat_id in enumerate(seat_ids):
            seat_context = f"{context}.seatIDs[{seat_index}]"
            require(valid_identifier(seat_id) and seat_id in teleport_ids,
                    f"{seat_context} is not an authored seat")
            require(seat_id not in grouped_seat_ids,
                    f"{seat_context} is already grouped")
            grouped_seat_ids.add(seat_id)


def validate_display_localizations(value, root, seats=()):
    if "localizations" not in value:
        return
    def ids(items):
        return {item["id"] for item in items}
    references = {field: set() for field in LABEL_FIELDS}
    references.update({
        "seatTitles": set(seats),
        "seatGroupTitles": ids(value.get("seatGroups", [])),
        "lightTitles": ids((value.get("lighting") or {}).get("luminaireGroups", [])),
        "animationTitles": ids(value.get("ambientAnimations", [])),
        "videoTitles": ids(value.get("videoSurfaces", [])),
        "particleTitles": ids(value.get("particleEffects", [])),
    })
    if (root / "sound.json").is_file():
        references["soundTitles"] = ids(decode_json(root / "sound.json", "sound.json")["sources"])
    try:
        validate_localizations(value["localizations"], references=references)
    except LocalizationError as error:
        raise ValidationError(str(error)) from error


def validate_room(
    root: Path,
    video_files: set[str] = frozenset(),
    image_files: set[str] = frozenset(),
) -> dict[str, Any]:
    value = decode_json(root / "space.json", "space.json")
    exact_keys(
        value,
        required={
            "formatVersion", "displayName", "seatedOrigin", "safeHeadVolume",
            "viewOpenings",
        },
        optional={
            "caption", "previewCamera", "spatialAdaptation", "lighting",
            "ambientAnimations", "videoSurfaces", "rendering", "seatGroups",
            "viewForwardYawRadians", "particleEffects", "localizations",
        },
        context="space.json",
    )
    require(type(value["formatVersion"]) is int
            and value["formatVersion"] in {1, 2, 3, 4, 5, 6, 7, 8, 9, 10},
            "space.json.formatVersion must be 1, 2, 3, 4, 5, 6, 7, 8, 9, or 10")
    require(value["formatVersion"] >= 2 or "lighting" not in value,
            "space.json.lighting requires formatVersion 2")
    require(value["formatVersion"] >= 4 or "ambientAnimations" not in value,
            "space.json.ambientAnimations requires formatVersion 4")
    if "rendering" in value:
        require(value["formatVersion"] >= 5, "space.json.rendering requires formatVersion 5")
        validate_rendering(value["rendering"])
    require(value["formatVersion"] >= 6 or "seatGroups" not in value,
            "space.json.seatGroups requires formatVersion 6")
    require(value["formatVersion"] >= 7 or "videoSurfaces" not in value,
            "space.json.videoSurfaces requires formatVersion 7")
    require(value["formatVersion"] >= 8 or "viewForwardYawRadians" not in value,
            "space.json.viewForwardYawRadians requires formatVersion 8")
    require(value["formatVersion"] >= 9 or "particleEffects" not in value,
            "space.json.particleEffects requires formatVersion 9")
    if "particleEffects" in value:
        validate_particle_effects(value["particleEffects"])
    if "viewForwardYawRadians" in value:
        yaw = value["viewForwardYawRadians"]
        require(finite(yaw) and -math.pi <= yaw <= math.pi,
                "space.json.viewForwardYawRadians must be finite and within [-pi, pi]")
    if "videoSurfaces" in value:
        referenced = validate_video_surfaces(
            value["videoSurfaces"],
            (value.get("lighting") or {}).get("luminaireGroups", []),
        )
        require(referenced == video_files,
                "space.json.videoSurfaces must reference every .mp4 file, and no others")
        for name in referenced:
            path = root / name
            require(0 < path.stat().st_size <= 64 * 1024 * 1024,
                    f"{name} exceeds the video surface byte limit")
            with path.open("rb") as handle:
                header = handle.read(12)
            require(len(header) == 12 and header[4:8] == b"ftyp",
                    f"{name} must start with an MP4 ftyp box")
    else:
        require(not video_files, "video assets require space.json videoSurfaces")
    require_text(value["displayName"], "space.json.displayName", 200)
    if "caption" in value:
        require_text(value["caption"], "space.json.caption", 1_000)
    if "previewCamera" in value:
        camera = value["previewCamera"]
        require(isinstance(camera, dict), "space.json.previewCamera must be an object")
        exact_keys(
            camera,
            required={"yawDegrees", "pitchDegrees", "zoom"},
            context="space.json.previewCamera",
        )
        require(finite(camera["yawDegrees"]), "previewCamera.yawDegrees must be finite")
        require(finite(camera["pitchDegrees"]), "previewCamera.pitchDegrees must be finite")
        require(finite(camera["zoom"]) and camera["zoom"] > 0,
                "previewCamera.zoom must be positive")
    validate_pose(value["seatedOrigin"], "space.json.seatedOrigin")
    volume = value["safeHeadVolume"]
    require(isinstance(volume, dict), "space.json.safeHeadVolume must be an object")
    exact_keys(volume, required={"centerMeters", "sizeMeters"}, context="safeHeadVolume")
    require_number_list(volume["centerMeters"], 3, "safeHeadVolume.centerMeters")
    require_number_list(volume["sizeMeters"], 3, "safeHeadVolume.sizeMeters")
    require(all(number > 0 for number in volume["sizeMeters"]),
            "safeHeadVolume.sizeMeters must be positive")
    openings = value["viewOpenings"]
    require(isinstance(openings, list) and len(openings) == 1,
            "space.json.viewOpenings must contain exactly one opening")
    opening = openings[0]
    require(isinstance(opening, dict), "viewOpenings[0] must be an object")
    exact_keys(
        opening,
        required={"id", "transform", "widthMeters", "heightMeters"},
        context="viewOpenings[0]",
    )
    require(valid_identifier(opening["id"]), "viewOpenings[0].id is invalid")
    validate_pose(opening["transform"], "viewOpenings[0].transform")
    require(finite(opening["widthMeters"]) and opening["widthMeters"] > 0,
            "viewOpenings[0].widthMeters must be positive")
    require(finite(opening["heightMeters"]) and opening["heightMeters"] > 0,
            "viewOpenings[0].heightMeters must be positive")
    teleports = validate_teleports(root / "teleport-points.json")
    if "seatGroups" in value:
        validate_seat_groups(value["seatGroups"], teleports)
    if "spatialAdaptation" in value:
        validate_spatial_adaptation(value["spatialAdaptation"], teleports)
    if "lighting" in value:
        referenced_layer_images = validate_lighting(
            value["lighting"], teleports, value["formatVersion"])
        require(referenced_layer_images == image_files,
                "lighting.bakedIndirect.layers must reference every .png file, and no others")
        dimensions_seen: tuple[int, int] | None = None
        for name in referenced_layer_images:
            path = root / name
            width, height = validate_light_layer_image(path)
            if dimensions_seen is None:
                dimensions_seen = (width, height)
            else:
                require(dimensions_seen == (width, height),
                        "lighting.bakedIndirect.layers images must share identical pixel dimensions")
    else:
        require(not image_files, "light layer image assets require space.json lighting.bakedIndirect.layers")
    if "ambientAnimations" in value:
        validate_ambient_animations(value["ambientAnimations"])
    validate_display_localizations(value, root, teleports)
    validate_provenance(root / "provenance.json")
    validate_image(root / "thumbnail.jpg", equirectangular=False)
    validate_usdz(root / "scene.usdz")
    validate_room_bindings(root / "scene.usdz", root / "space.json")
    return {"kind": "room", "displayName": value["displayName"], "seats": len(teleports)}


def validate_environment(value: Any) -> None:
    require(isinstance(value, dict), "view.json.environment must be an object")
    exact_keys(
        value,
        required=set(),
        optional={
            "skyGainEV", "exposureEV", "horizonPitchDegrees", "colorGrade", "directSun",
            "condition",
        },
        context="view.json.environment",
    )
    for field in ("skyGainEV", "exposureEV", "horizonPitchDegrees"):
        if field in value:
            require(finite(value[field]), f"environment.{field} must be finite")
    if "condition" in value:
        require(value["condition"] in {"day", "dusk", "night", "overcast"},
                "environment.condition is invalid")
    if "colorGrade" in value:
        grade = value["colorGrade"]
        require(isinstance(grade, dict), "environment.colorGrade must be an object")
        exact_keys(grade, required={"contrast", "saturation"}, context="colorGrade")
        require(finite(grade["contrast"]) and 0.5 <= grade["contrast"] <= 2,
                "colorGrade.contrast must be between 0.5 and 2")
        require(finite(grade["saturation"]) and 0 <= grade["saturation"] <= 2,
                "colorGrade.saturation must be between 0 and 2")
    if "directSun" in value:
        sun = value["directSun"]
        require(isinstance(sun, dict), "environment.directSun must be an object")
        exact_keys(
            sun,
            required={"enabled", "illuminanceLux"},
            optional={"azimuthDegrees", "elevationDegrees"},
            context="directSun",
        )
        require(type(sun["enabled"]) is bool, "directSun.enabled must be boolean")
        require(finite(sun["illuminanceLux"]) and sun["illuminanceLux"] >= 0,
                "directSun.illuminanceLux must be non-negative")
        for field in ("azimuthDegrees", "elevationDegrees"):
            if field in sun:
                require(finite(sun[field]), f"directSun.{field} must be finite")
        if sun["enabled"]:
            require("azimuthDegrees" in sun and "elevationDegrees" in sun,
                    "enabled directSun requires azimuthDegrees and elevationDegrees")


def validate_view(root: Path, files: set[str]) -> dict[str, Any]:
    value = decode_json(root / "view.json", "view.json")
    exact_keys(
        value,
        required={"formatVersion", "displayName", "panorama"},
        optional={"caption", "environment", "localizations"},
        context="view.json",
    )
    require(type(value["formatVersion"]) is int and value["formatVersion"] in {1, 2},
            "view.json.formatVersion must be 1 or 2")
    require(value["formatVersion"] == 2
            or "condition" not in value.get("environment", {}),
            "view.json.environment.condition requires formatVersion 2")
    require_text(value["displayName"], "view.json.displayName", 200)
    panorama = value["panorama"]
    require(isinstance(panorama, dict), "view.json.panorama must be an object")
    exact_keys(
        panorama,
        required={"projection", "width", "height"},
        optional={"initialYawDegrees"},
        context="view.json.panorama",
    )
    require(panorama["projection"] == "equirectangular", "unsupported panorama projection")
    require(type(panorama["width"]) is int and type(panorama["height"]) is int,
            "panorama width and height must be integers")
    dimensions = validate_image(root / "panorama.jpg", equirectangular=True)
    require(dimensions == (panorama["width"], panorama["height"]),
            "panorama dimensions do not match view.json")
    if "initialYawDegrees" in panorama:
        require(finite(panorama["initialYawDegrees"]), "initialYawDegrees must be finite")
    if "environment" in value:
        validate_environment(value["environment"])
    validate_display_localizations(value, root)
    validate_provenance(root / "provenance.json")
    validate_image(root / "thumbnail.jpg", equirectangular=False)
    if "lighting.jpg" in files:
        validate_image(root / "lighting.jpg", equirectangular=True)
    if "point-lights.json" in files:
        from point_lights import validate_table

        validate_table(
            decode_json(root / "point-lights.json", "point-lights.json"),
            require,
        )
    return {"kind": "view", "displayName": value["displayName"], "seats": 0}


def validate(path: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="locus-asset-") as directory:
        root = Path(directory)
        files = extract_archive(path, root)
        audio_files = {p for p in files if Path(p).suffix.lower() in ('.m4a', '.mp3', '.wav')}
        if 'sound.json' in files:
            from package_sound import validate_definition
            sound = decode_json(root / 'sound.json', 'sound.json')
            paths = validate_definition(sound, require, 'room' if 'space.json' in files else 'view')
            require(set(paths) == audio_files, 'sound.json must reference every audio file')
            for p in paths:
                require(0 < (root / p).stat().st_size <= 128 * 1024 * 1024, 'sound asset byte limit')
            files = files - audio_files - {'sound.json'}
        else:
            require(not audio_files, 'audio assets require sound.json')
        if "space.json" in files and "view.json" not in files:
            # Room v7's `videoSurfaces` names its `.mp4` files directly in
            # space.json; there is no separate sidecar manifest to gate their
            # presence on ahead of decoding it, unlike `sound.json` above.
            # Room v10's `lighting.bakedIndirect.layers` does the same for
            # its `.png` files.
            video_files = {p for p in files if Path(p).suffix.lower() == ".mp4"}
            image_files = {p for p in files if Path(p).suffix.lower() == ".png"}
            files = files - video_files - image_files
            missing = ROOM_FILES - files
            extra = files - ROOM_FILES
            if missing:
                raise ValidationError(f"Room ZIP is missing {sorted(missing)[0]}")
            if extra:
                raise ValidationError(f"Room ZIP contains unsupported file {sorted(extra)[0]}")
            return validate_room(root, video_files, image_files)
        if "view.json" in files and "space.json" not in files:
            missing = VIEW_REQUIRED_FILES - files
            extra = files - VIEW_REQUIRED_FILES - VIEW_OPTIONAL_FILES
            if missing:
                raise ValidationError(f"View ZIP is missing {sorted(missing)[0]}")
            if extra:
                raise ValidationError(f"View ZIP contains unsupported file {sorted(extra)[0]}")
            return validate_view(root, files)
        raise ValidationError("ZIP must contain either space.json or view.json, but not both")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--json", action="store_true")
    arguments = parser.parse_args(argv)
    try:
        summary = validate(arguments.archive)
    except (OSError, ValidationError, zipfile.BadZipFile) as error:
        print(f"INVALID: {error}", file=sys.stderr)
        return 2
    if arguments.json:
        print(json.dumps(summary, sort_keys=True))
    else:
        print(
            f"VALID: {summary['kind']} \"{summary['displayName']}\""
            + (f" ({summary['seats']} seats)" if summary["kind"] == "room" else "")
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
