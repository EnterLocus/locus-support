"""Optional ASTC KTX1 GPU-texture sidecar for a View's sky
(`locus.view.gpu-texture.v1`), first supported by Locus 1.2.3.

See docs/package-spec-v2.md "View GPU texture sidecar" for the full field
contract. The JPEG (`panorama.jpg`) stays the source of truth -- edit,
export and import all continue to read it. Complete user packages may carry
the same sidecars as Library packages, with the same version, source-hash
and KTX validation. This module only builds
the sidecar and the `gpuTexture` manifest field; the archive-context checks
(payload registration, hash-against-the-packaged-JPEG, KTX-vs-manifest
cross-check) live in `validate_locusplace.py`, mirroring how `panorama_media`
and `validate_locusplace.py` split the same responsibility for `media`.

Library capability registration is independent of reader availability, same
note as `panorama_media.py`: a Dev catalog can preview a package carrying
this profile while older readers refuse installation on `minimumAppVersion`.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Callable

from ktx1 import (
    GL_COMPRESSED_RGBA_ASTC_6x6_KHR,
    GL_COMPRESSED_SRGB8_ALPHA8_ASTC_6x6_KHR,
    Ktx1Error,
    parse_header,
)

CAPABILITY = "locus.view.gpu-texture.v1"
MINIMUM_APP = (1, 2, 3)
MINIMUM_APP_STRING = "1.2.3"
FORMAT = "astc-6x6-srgb"
SIDECAR_NAME = "panorama.ktx"

# `locus.view.gpu-texture.v2` (docs/package-spec-v2.md "View GPU texture
# sidecar v2"): generalizes the v1 sidecar from just the sky panorama to any
# of a View's referenced images (currently: `panorama.path`, plus
# `celestial`'s `backgroundPanorama`/`dayTexture`/`nightTexture`/
# `cloudTexture`). A package carries v1 `gpuTexture` or v2 `gpuTextures`,
# never both.
CAPABILITY_V2 = "locus.view.gpu-texture.v2"
MINIMUM_APP_V2 = (1, 3, 0)
MINIMUM_APP_V2_STRING = "1.3.0"
FORMAT_LINEAR = "astc-6x6-linear"
V2_FORMATS = (FORMAT, FORMAT_LINEAR)

# Near-orbit v2 (docs/package-spec-v2.md "View near orbit v2"): the globals and
# every manifest tile are eligible sources; only `cloudTexture` is linear.
NEAR_ORBIT_GPU_TEXTURE_FIELDS = (
    "dayTexture", "nightTexture", "cloudTexture", "fallbackPanorama", "galaxyTexture",
)
NEAR_ORBIT_LINEAR_FIELDS = frozenset({"cloudTexture"})
WRAP_FULL_EQUIRECT = "Repeat"
WRAP_TILE = "Clamp"

# Of the celestial fields eligible for a sidecar, only `cloudTexture` is
# sampled with RealityKit's `.raw` semantic (no gamma decode) -- see
# `CelestialLayer.make` -- so it is the only one whose sidecar must be
# linear rather than sRGB.
CELESTIAL_LINEAR_FIELDS = frozenset({"cloudTexture"})
CELESTIAL_GPU_TEXTURE_FIELDS = (
    "backgroundPanorama", "dayTexture", "nightTexture", "cloudTexture",
)

DEFAULT_CONVERTER = Path(
    "/Applications/Xcode.app/Contents/Developer/usr/bin/TextureConverter"
)


class GpuTextureError(Exception):
    pass


# Injected so tests can substitute a fast fake instead of paying the real
# ~10 s TextureConverter run (docs/research-2026-09-28-load-and-frame-performance.md
# 二: "9-13 s 离线" per 12K image); the real converter is exercised directly
# by the pilot / integration path, not by unit tests.
ConverterRunner = Callable[[Path, Path, Path], None]


def run_texture_converter(
    converter: Path, source_jpg: Path, output_ktx: Path
) -> None:
    """Invoke Xcode's TextureConverter to produce the sidecar KTX1.

    `--wrap_mode=Repeat` keeps mip filtering correct across the panorama's
    u=0/1 seam (docs/package-spec-v2.md "Coordinate convention"), matching
    what research-2026-09-28 二 already validated for this exact profile.
    `--srgb_format` matches `PanoramaColorGrade.usda`'s authored
    `colorSpace = sRGB`, so the sidecar renders identically to the JPEG path
    (RealityKit does no extra gamma correction either way).
    """
    if not converter.is_file():
        raise GpuTextureError(f"TextureConverter not found: {converter}")
    if not source_jpg.is_file():
        raise GpuTextureError(f"source panorama not found: {source_jpg}")
    # Flags must precede the positional input path, and the output path is
    # `--output=`, not a second positional argument -- this build of
    # TextureConverter silently falls back to a legacy short-flag
    # compatibility parser (which rejects every long flag as "unrecognized
    # option") when flags follow the input, even though `--help` documents
    # the long-flag form unconditionally. Verified against the installed
    # binary during the #1118 C2 pilot; see the pilot report for the
    # exact failure text this sidesteps.
    command = [
        str(converter),
        "--compression_format=ASTC6x6",
        "--srgb_format",
        "--file_format=KTX",
        "--max_mipmaps=15",
        "--wrap_mode=Repeat",
        f"--output={output_ktx}",
        str(source_jpg),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0 or not output_ktx.is_file():
        raise GpuTextureError(
            "TextureConverter failed (exit "
            f"{result.returncode}): {result.stderr.strip() or result.stdout.strip()}"
        )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_eligible(kind: str, minimum_app_version: "tuple[int, int, int]") -> None:
    """Refuse to generate a sidecar for a package whose declared
    minimumAppVersion is below the gpu-texture floor, or whose profile
    cannot carry it at all (only a View's sky panorama can)."""
    if kind != "destination":
        raise GpuTextureError(
            f"gpu-texture sidecar only applies to View (destination) packages, got {kind}"
        )
    if minimum_app_version < MINIMUM_APP:
        raise GpuTextureError(
            "gpu-texture sidecar requires minimumAppVersion >= "
            f"{MINIMUM_APP_STRING}, got "
            + ".".join(str(part) for part in minimum_app_version)
        )


def validate_definition(value: Any, require) -> str:
    """Shape-only check of the `gpuTexture` manifest field (mirrors
    `panorama_media.validate_definition`). Archive-context checks -- does
    the referenced file exist, does its KTX1 header match, does the source
    hash match the packaged JPEG -- are the caller's job (they need the open
    archive); this only proves the JSON itself is well-formed. Returns the
    declared sidecar path.
    """
    require(
        isinstance(value, dict)
        and set(value)
        == {"path", "format", "width", "height", "mipmapLevels", "sourcePanoramaSHA256"},
        "invalid gpuTexture fields",
    )
    require(value["format"] == FORMAT, "unsupported gpuTexture format")
    require(isinstance(value["path"], str) and bool(value["path"]), "missing gpuTexture path")
    width, height = value["width"], value["height"]
    require(type(width) is int and type(height) is int and width > 0 and height > 0,
            "invalid gpuTexture dimensions")
    require(width == 2 * height, "gpuTexture dimensions must be 2:1")
    require(type(value["mipmapLevels"]) is int and value["mipmapLevels"] >= 1,
            "invalid gpuTexture mipmapLevels")
    digest = value["sourcePanoramaSHA256"]
    require(
        isinstance(digest, str) and len(digest) == 64
        and all(c in "0123456789abcdef" for c in digest),
        "invalid gpuTexture source panorama hash",
    )
    return value["path"]


def build_gpu_texture_field(
    *,
    panorama_jpg: Path,
    output_ktx: Path,
    panorama_width: int,
    panorama_height: int,
    converter: Path = DEFAULT_CONVERTER,
    run_converter: ConverterRunner = run_texture_converter,
) -> "dict[str, Any]":
    """Generate `output_ktx` from `panorama_jpg` and return the `gpuTexture`
    field for `destination.json`. Raises `GpuTextureError` if the converter's
    own output does not describe the same panorama it was given (ASTC 6x6
    sRGB, matching dimensions, at least one mip level), so a broken or
    mis-configured converter run cannot silently ship a package.
    """
    run_converter(converter, panorama_jpg, output_ktx)
    data = output_ktx.read_bytes()
    try:
        header = parse_header(data)
    except Ktx1Error as error:
        raise GpuTextureError(
            f"TextureConverter produced an invalid KTX1 file: {error}"
        ) from error
    if header.gl_internal_format != GL_COMPRESSED_SRGB8_ALPHA8_ASTC_6x6_KHR:
        raise GpuTextureError(
            "TextureConverter did not produce ASTC 6x6 sRGB "
            f"(glInternalFormat=0x{header.gl_internal_format:x})"
        )
    if (header.pixel_width, header.pixel_height) != (panorama_width, panorama_height):
        raise GpuTextureError(
            "KTX dimensions do not match the panorama "
            f"({header.pixel_width}x{header.pixel_height} vs "
            f"{panorama_width}x{panorama_height})"
        )
    if header.number_of_mipmap_levels < 1:
        raise GpuTextureError("KTX has no mip levels")
    return {
        "path": output_ktx.name,
        "format": FORMAT,
        "width": header.pixel_width,
        "height": header.pixel_height,
        "mipmapLevels": header.number_of_mipmap_levels,
        "sourcePanoramaSHA256": sha256_file(panorama_jpg),
    }


def require_eligible_v2(kind: str, minimum_app_version: "tuple[int, int, int]") -> None:
    """v2 counterpart of `require_eligible`: still a View-only profile, but
    gated on the 1.3.0 floor (docs/package-spec-v2.md "View GPU
    texture sidecar v2")."""
    if kind != "destination":
        raise GpuTextureError(
            f"gpu-texture sidecar only applies to View (destination) packages, got {kind}"
        )
    if minimum_app_version < MINIMUM_APP_V2:
        raise GpuTextureError(
            "gpuTextures (v2) sidecar requires minimumAppVersion >= "
            f"{MINIMUM_APP_V2_STRING}, got "
            + ".".join(str(part) for part in minimum_app_version)
        )


def validate_entry_v2(value: Any, require, *, index: int) -> None:
    """Shape-only check of one `gpuTextures[index]` entry."""
    prefix = f"gpuTextures[{index}]"
    require(
        isinstance(value, dict)
        and set(value) == {
            "source", "path", "format", "width", "height",
            "mipmapLevels", "sourceSHA256",
        },
        f"invalid {prefix} fields",
    )
    require(isinstance(value["source"], str) and bool(value["source"]),
            f"missing {prefix}.source")
    require(isinstance(value["path"], str) and bool(value["path"]),
            f"missing {prefix}.path")
    require(value["format"] in V2_FORMATS, f"unsupported {prefix}.format")
    width, height = value["width"], value["height"]
    require(type(width) is int and type(height) is int and width > 0 and height > 0,
            f"invalid {prefix} dimensions")
    # Full equirects are 2:1; near-orbit v2 tiles are square. Which one a given
    # source may be is checked against its real image by `validate_locusplace`.
    require(width == 2 * height or width == height,
            f"{prefix} dimensions must be 2:1 or square")
    require(type(value["mipmapLevels"]) is int and value["mipmapLevels"] >= 1,
            f"invalid {prefix}.mipmapLevels")
    digest = value["sourceSHA256"]
    require(
        isinstance(digest, str) and len(digest) == 64
        and all(c in "0123456789abcdef" for c in digest),
        f"invalid {prefix}.sourceSHA256",
    )


def validate_definition_v2(value: Any, require) -> "list[dict[str, Any]]":
    """Shape-only check of the `gpuTextures` manifest field (v2). Archive-
    context checks -- is `source` one of this destination's actually-declared
    eligible images, does the referenced `path` exist, does the KTX1 header
    match, does the source hash match the packaged source image -- are the
    caller's job (mirrors `validate_definition` above for v1). Returns the
    validated entry list; each source appears at most once.
    """
    require(isinstance(value, list) and len(value) >= 1,
            "gpuTextures must be a non-empty array")
    seen_sources: set = set()
    for index, entry in enumerate(value):
        validate_entry_v2(entry, require, index=index)
        require(entry["source"] not in seen_sources,
                f"gpuTextures[{index}].source is duplicated")
        seen_sources.add(entry["source"])
    return value


# `(converter, source, output, srgb)`; a runner is additionally passed
# `wrap_mode=` (keyword) only when it is not the default `Repeat`, so older
# four-argument fakes keep working.
ConverterRunnerV2 = Callable[..., None]


def run_texture_converter_v2(
    converter: Path, source_image: Path, output_ktx: Path, srgb: bool,
    wrap_mode: str = WRAP_FULL_EQUIRECT,
) -> None:
    """Like `run_texture_converter`, but selects sRGB vs linear ASTC 6x6 per
    source. Colour equirects (the panorama, `celestial.backgroundPanorama`/
    `dayTexture`/`nightTexture`) are sRGB; `celestial.cloudTexture` is
    sampled with RealityKit's `.raw` semantic (no gamma decode), so its
    sidecar must be linear -- omitting `--srgb_format` is what selects
    `GL_COMPRESSED_RGBA_ASTC_6x6_KHR` instead of the sRGB internal format.
    `wrap_mode` is `Repeat` for full equirects (keeps the u=0/1 seam filtered)
    and `Clamp` for near-orbit tiles, which must not bleed across their edges.
    """
    if wrap_mode not in ("Repeat", "Clamp"):
        raise GpuTextureError(f"unsupported wrap mode: {wrap_mode}")
    if not converter.is_file():
        raise GpuTextureError(f"TextureConverter not found: {converter}")
    if not source_image.is_file():
        raise GpuTextureError(f"source image not found: {source_image}")
    command = (
        [str(converter), "--compression_format=ASTC6x6"]
        + (["--srgb_format"] if srgb else [])
        + [
            "--file_format=KTX",
            "--max_mipmaps=15",
            f"--wrap_mode={wrap_mode}",
            f"--output={output_ktx}",
            str(source_image),
        ]
    )
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0 or not output_ktx.is_file():
        raise GpuTextureError(
            "TextureConverter failed (exit "
            f"{result.returncode}): {result.stderr.strip() or result.stdout.strip()}"
        )


def build_gpu_texture_entry_v2(
    *,
    source_path: Path,
    output_ktx: Path,
    source: str,
    path: "str | None" = None,
    expected_width: int,
    expected_height: int,
    linear: bool,
    wrap_mode: str = WRAP_FULL_EQUIRECT,
    converter: Path = DEFAULT_CONVERTER,
    run_converter: ConverterRunnerV2 = run_texture_converter_v2,
) -> "dict[str, Any]":
    """Generate `output_ktx` from `source_path` and return one `gpuTextures`
    entry. `source` is the package-relative path this sidecar was built from
    (`destination.panorama.path` or a `celestial.*Texture` field) -- it is
    recorded in the entry verbatim so a reader can match the sidecar back to
    the image it replaces. `path` is the package-relative sidecar path to
    record (defaults to `output_ktx.name`, correct only when the sidecar
    sits at the package root -- a `celestial/*.ktx` sidecar must pass its
    real relative path, since `.name` alone would drop the subdirectory).
    """
    recorded_path = path if path is not None else output_ktx.name
    if wrap_mode == WRAP_FULL_EQUIRECT:
        run_converter(converter, source_path, output_ktx, not linear)
    else:
        run_converter(converter, source_path, output_ktx, not linear, wrap_mode=wrap_mode)
    data = output_ktx.read_bytes()
    try:
        header = parse_header(data)
    except Ktx1Error as error:
        raise GpuTextureError(
            f"TextureConverter produced an invalid KTX1 file for {source}: {error}"
        ) from error
    expected_internal_format = (
        GL_COMPRESSED_RGBA_ASTC_6x6_KHR if linear
        else GL_COMPRESSED_SRGB8_ALPHA8_ASTC_6x6_KHR
    )
    if header.gl_internal_format != expected_internal_format:
        raise GpuTextureError(
            f"TextureConverter did not produce the expected ASTC 6x6 format for {source} "
            f"(glInternalFormat=0x{header.gl_internal_format:x})"
        )
    if (header.pixel_width, header.pixel_height) != (expected_width, expected_height):
        raise GpuTextureError(
            f"KTX dimensions do not match {source} "
            f"({header.pixel_width}x{header.pixel_height} vs "
            f"{expected_width}x{expected_height})"
        )
    if header.number_of_mipmap_levels < 1:
        raise GpuTextureError(f"KTX has no mip levels for {source}")
    return {
        "source": source,
        "path": recorded_path,
        "format": FORMAT_LINEAR if linear else FORMAT,
        "width": header.pixel_width,
        "height": header.pixel_height,
        "mipmapLevels": header.number_of_mipmap_levels,
        "sourceSHA256": sha256_file(source_path),
    }


def build_gpu_textures_field(
    *,
    destination_dir: Path,
    manifest: "dict[str, Any]",
    converter: Path = DEFAULT_CONVERTER,
    run_converter: ConverterRunnerV2 = run_texture_converter_v2,
) -> "list[dict[str, Any]]":
    """Build the v2 `gpuTextures` array for every eligible source this
    destination's manifest actually declares: the sky panorama (required),
    plus any `celestial` background/day/night/cloud texture it carries, and
    for near-orbit v2 its globals, every day tile and every surface tile
    (linear). Each sidecar is written next to its source as `<stem>.ktx`.

    Raises `GpuTextureError` if the manifest has no `panorama.path`, or if a
    referenced source file cannot be found or measured.
    """
    panorama = manifest.get("panorama") or {}
    panorama_relative = panorama.get("path")
    if not isinstance(panorama_relative, str) or not panorama_relative:
        raise GpuTextureError(
            "gpuTextures sidecar requires panorama.path"
        )
    sources: "list[tuple[str, int, int, bool, str]]" = [
        (panorama_relative, panorama["width"], panorama["height"], False, WRAP_FULL_EQUIRECT)
    ]
    celestial = manifest.get("celestial")
    if isinstance(celestial, dict):
        for field in CELESTIAL_GPU_TEXTURE_FIELDS:
            relative = celestial.get(field)
            if not isinstance(relative, str) or not relative:
                continue
            source_path = destination_dir / relative
            width, height = _measure_image(source_path, relative)
            sources.append((relative, width, height, field in CELESTIAL_LINEAR_FIELDS,
                            WRAP_FULL_EQUIRECT))
    near_orbit = manifest.get("nearOrbit")
    if isinstance(near_orbit, dict) and near_orbit.get("version") == 2:
        known = {entry[0] for entry in sources}
        for field in NEAR_ORBIT_GPU_TEXTURE_FIELDS:
            relative = near_orbit.get(field)
            if not isinstance(relative, str) or not relative or relative in known:
                continue
            known.add(relative)
            width, height = _measure_image(destination_dir / relative, relative)
            sources.append((relative, width, height, field in NEAR_ORBIT_LINEAR_FIELDS,
                            WRAP_FULL_EQUIRECT))
        tiles = near_orbit.get("tiles")
        if isinstance(tiles, dict):
            for relative in _tile_paths(destination_dir, tiles):
                if relative in known:
                    continue
                known.add(relative)
                width, height = _measure_image(destination_dir / relative, relative)
                sources.append((relative, width, height, False, WRAP_TILE))
            # Surface tiles (terrain slopes, water cover) are raw data:
            # linear ASTC, clamped like the day tiles they sit under.
            surface = near_orbit.get("surface")
            if isinstance(surface, dict):
                for relative in _tile_paths(destination_dir, surface, "surface"):
                    if relative in known:
                        continue
                    known.add(relative)
                    width, height = _measure_image(destination_dir / relative, relative)
                    sources.append((relative, width, height, True, WRAP_TILE))

    known = {entry[0] for entry in sources}
    for profile in (celestial, near_orbit):
        if isinstance(profile, dict) and 'oceanGlint' in profile:
            from ocean_glint import validate
            relative = validate(profile['oceanGlint'])['mask']
            if relative not in known:
                width, height = _measure_image(destination_dir / relative, relative)
                sources.append((relative, width, height, True, WRAP_FULL_EQUIRECT))
                known.add(relative)
    entries = []
    sidecar_paths: set = set()
    for relative, width, height, linear, wrap_mode in sources:
        source_path = destination_dir / relative
        stem = Path(relative).with_suffix("")
        relative_ktx = stem.as_posix() + ".ktx"
        if relative_ktx in sidecar_paths:
            raise GpuTextureError(f"two gpuTextures sources share the sidecar path {relative_ktx}")
        sidecar_paths.add(relative_ktx)
        output_ktx = destination_dir / Path(relative_ktx)
        output_ktx.parent.mkdir(parents=True, exist_ok=True)
        entries.append(build_gpu_texture_entry_v2(
            source_path=source_path,
            output_ktx=output_ktx,
            source=relative,
            path=relative_ktx,
            expected_width=width,
            expected_height=height,
            linear=linear,
            wrap_mode=wrap_mode,
            converter=converter,
            run_converter=run_converter,
        ))
    return entries


def _tile_paths(destination_dir: Path, block: "dict[str, Any]", kind: str = "tile") -> "list[str]":
    """Tile image paths in manifest order (row, then column) of the
    `nearOrbit.tiles` or `nearOrbit.surface` manifest."""
    manifest_path = destination_dir / str(block.get("manifest", ""))
    if not manifest_path.is_file():
        raise GpuTextureError(f"nearOrbit {kind} manifest not found: {manifest_path}")
    try:
        value = json.loads(manifest_path.read_text(encoding="utf-8"))
        return [entry["path"] for entry in value["tiles"]]
    except (ValueError, KeyError, TypeError) as error:
        raise GpuTextureError(f"invalid nearOrbit {kind} manifest: {error}") from error


def _measure_image(path: Path, field: str) -> "tuple[int, int]":
    """Real pixel dimensions of an on-disk editable-source image (not yet
    inside an archive, so `validate_locusplace.archive_image_dimensions`
    does not apply). Deferred import: `gpu_texture_sidecar` is imported by
    `validate_locusplace` itself for the archive-side checks, so importing
    it back at module scope here would be circular.
    """
    from validate_locusplace import stream_image_dimensions
    if not path.is_file():
        raise GpuTextureError(f"gpuTextures source not found: {field} ({path})")
    with path.open("rb") as handle:
        return stream_image_dimensions(
            handle, path.stat().st_size, str(path), allow_exr=False)
