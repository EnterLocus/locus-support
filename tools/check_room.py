#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Validate a Room on macOS through structure, binding and entry checks."""
from __future__ import annotations

import argparse
import json
import platform
import re
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path


_build_directory = None


def executable() -> Path:
    """Compile once per process in a private directory, never a shared executable cache."""
    global _build_directory
    if _build_directory is None:
        temporary = tempfile.TemporaryDirectory(prefix="locus-room-check-build-")
        build = Path(temporary.name)
        package = Path(__file__).parent / "locus-room-check"
        # This dependency-free executable needs no package manifest evaluation.
        # Compile the reviewed sources directly so externally sandboxed authoring
        # environments do not require a nested SwiftPM sandbox.
        sources = sorted((package / "Sources" / "LocusRoomCheck").glob("*.swift"))
        command = ["xcrun", "--sdk", "macosx", "swiftc", "-swift-version", "6",
                   "-target", platform.machine() + "-apple-macosx15.0",
                   "-o", str(build / "locus-room-check")] + [str(source) for source in sources]
        try:
            compiled = subprocess.run(command, capture_output=True, text=True, timeout=300)
            if compiled.returncode:
                raise RuntimeError("Could not build macOS RealityKit checker: " + compiled.stderr[-4000:])
        except Exception:
            temporary.cleanup()
            raise
        _build_directory = temporary
    return Path(_build_directory.name) / "locus-room-check"


def check_modelio(root: Path, manifest: dict, binary: Path, v2) -> tuple[list, list]:
    """Apply the App's ModelIO counting policy to every imported model.

    Structural validation has already checked all paths before this is called.
    The counts describe this Mac's ModelIO, not the installed visionOS build.
    """
    groups = []
    for space_id in manifest["contents"].get("spaceIDs", []):
        directory = root / "catalog" / "spaces" / space_id
        space = json.loads((directory / "space.json").read_text())
        models = [("scene", directory / space["scene"])]
        collision = space.get("collision", {})
        if collision.get("mode") == "separate":
            models.append(("collision", directory / collision["path"]))
        groups.append(("room", space_id, models))
    for destination_id in manifest["contents"].get("destinationIDs", []):
        directory = root / "catalog" / "destinations" / destination_id
        destination = json.loads((directory / "destination.json").read_text())
        path = (destination.get("midground") or {}).get("path")
        if path:
            groups.append(("midground", destination_id, [("midground", directory / path)]))
    return check_modelio_groups(root, groups, binary, v2)


def check_modelio_groups(root: Path, groups: list, binary: Path, v2) -> tuple[list, list]:
    results, errors = [], []
    limits = {"triangles": v2.TRIANGLES, "materials": v2.MATERIALS, "entities": v2.ENTITIES}
    for kind, identifier, models in groups:
        total = dict.fromkeys(limits, 0)
        entries = []
        complete = True
        for role, path in models:
            process = subprocess.run([str(binary), "--modelio-budget", str(path)],
                                     capture_output=True, text=True, timeout=300)
            try:
                stats = json.loads(process.stdout.strip().splitlines()[-1])
            except (ValueError, IndexError) as error:
                raise RuntimeError("ModelIO inspection failed: " + process.stderr[-4000:]) from error
            name = str(path.relative_to(root))
            entries.append({"role": role, "path": name, "statistics": stats})
            if process.returncode or stats.get("error"):
                complete = False
                errors.append({"layer": "S", "code": "modelIOBudget",
                               "message": f"ModelIO rejected {name}: {stats.get('error', 'inspection failed')}"})
            else:
                for key in limits:
                    total[key] += stats[key]
        result = {"kind": kind, "id": identifier, "models": entries,
                  "totals": total if complete else None, "limits": limits}
        results.append(result)
        if complete:
            for key, limit in limits.items():
                if total[key] > limit:
                    errors.append({"layer": "S", "code": "modelIOBudget",
                                   "message": f"ModelIO {key} budget exceeded in {kind} {identifier}: {total[key]} > {limit}"})
    return results, errors


def check(archive: Path, version: str, renders: Path | None = None) -> dict:
    report = {"valid": False, "layers": [], "errors": [], "warnings": [], "rooms": [],
              "currentAppVersion": version, "macOS": platform.mac_ver()[0]}
    started = time.monotonic()
    def fail(layer, message):
        report["errors"].append({"layer": layer, "message": str(message)})
    if platform.system() != "Darwin":
        fail("environment", "Room checking requires macOS 15 or later with Xcode or Command Line Tools; no reduced validation is provided.")
        return report
    try:
        import validate_locusplace as v2
        import validate_locus_asset as flat
        v2.parse_version(version, "currentAppVersion")
        with zipfile.ZipFile(archive) as source:
            is_v2 = "locusplace.json" in source.namelist()
        summary = v2.validate(archive, current_app_version=version) if is_v2 else flat.validate(archive)
        report["summary"] = summary
        report["layers"] += ["S", "B"]
        with tempfile.TemporaryDirectory(prefix="locus-room-check-") as temporary:
            root = Path(temporary)
            # Structural validation has already enforced paths, sizes and symlinks.
            with zipfile.ZipFile(archive) as source:
                source.extractall(root)
            if is_v2:
                manifest = json.loads((root / "locusplace.json").read_text())
                spaces = [root / "catalog" / "spaces" / sid / "space.json"
                          for sid in manifest["contents"].get("spaceIDs", [])]
            else:
                spaces = [root / "space.json"] if (root / "space.json").is_file() else []
            if not spaces:
                raise ValueError("Archive contains no Room.")
            binary = executable()
            if is_v2:
                modelio, modelio_errors = check_modelio(root, manifest, binary, v2)
            else:
                modelio, modelio_errors = check_modelio_groups(
                    root, [("room", "flat", [("scene", root / "scene.usdz")])], binary, v2)
            report["modelIO"] = {"platform": "macOS", "groups": modelio}
            report["errors"].extend(modelio_errors)
            for index, path in enumerate(spaces):
                space = json.loads(path.read_text())
                if is_v2:
                    catalog = space["teleportCatalog"]
                    data = json.loads((path.parent / catalog["path"]).read_text())
                    seats = data["houses"][catalog["houseID"]]
                    model = path.parent / space["scene"]
                else:
                    seats = json.loads((root / "teleport-points.json").read_text())["points"]
                    model = root / "scene.usdz"
                seat_file = root / ("seats-%d.json" % index)
                seat_file.write_text(json.dumps(seats))
                if not is_v2:
                    # Match the reader floor declared when flat imports are normalized.
                    lighting = space.get("lighting", {})
                    groups = lighting.get("luminaireGroups", [])
                    sound = json.loads((root / "sound.json").read_text()) if (root / "sound.json").exists() else {}
                    music = any(x.get("role") == "music" for x in sound.get("sources", []))
                    modern = (space.get("videoSurfaces") or space.get("particleEffects") or
                              "viewForwardYawRadians" in space or
                              any(x.get("illuminatedEntities") for x in groups) or
                              (lighting.get("bakedIndirect") or {}).get("layers"))
                    floor = "1.4.1" if music else "1.2.1" if modern else "1.2.0" if space.get("seatGroups") else "1.1.4" if sound else "1.0.0"
                    if v2.parse_version(version, "currentAppVersion") < v2.parse_version(floor, "minimumAppVersion"):
                        raise ValueError("Room requires Locus " + floor + " or later.")
                arguments = [str(binary), str(model), str(path), str(seat_file)]
                if renders is not None:
                    arguments.append(str(renders.resolve() / ("room-%d" % index)))
                result = subprocess.run(arguments, capture_output=True, text=True, timeout=300)
                try:
                    room = json.loads(result.stdout.strip().splitlines()[-1])
                except (ValueError, IndexError) as error:
                    raise RuntimeError("RealityKit checker failed: " + result.stderr[-4000:]) from error
                flattened = root / ("inspection-%d.usda" % index)
                inspected = subprocess.run(["usdcat", "--flatten", "--skipSourceFileComment", str(model), "-o", str(flattened)], capture_output=True, text=True, timeout=120)
                if inspected.returncode:
                    raise RuntimeError("USD risk inspection failed: " + inspected.stderr[-2000:])
                stats = v2.inspect_flattened_usda(flattened, model.name)
                room["budgets"] = {name: {"used": value, "limit": limit, "ratio": value / limit}
                    for name, value, limit in (("triangles", stats["triangleCount"], v2.TRIANGLES),
                    ("materials", stats["materialCount"], v2.MATERIALS), ("entities", stats["entityCount"], v2.ENTITIES))}
                texture_pixels = 0
                max_texture = 0
                with zipfile.ZipFile(model) as usdz:
                    for member in usdz.infolist():
                        if Path(member.filename).suffix.lower() in {".png", ".jpg", ".jpeg", ".exr"}:
                            dimensions = v2.image_dimensions(usdz.read(member), member.filename)
                            texture_pixels += dimensions[0] * dimensions[1]
                            max_texture = max(max_texture, *dimensions)
                for name, value, limit in (("texturePixels", texture_pixels, v2.MODEL_TEXTURE_PIXELS),
                                            ("maxTextureDimension", max_texture, v2.MODEL_TEXTURE_DIMENSION)):
                    room["budgets"][name] = {"used": value, "limit": limit, "ratio": value / limit}
                text = flattened.read_text()
                if re.search(r"doubleSided\s*=\s*(?:1|true)", text):
                    room["warnings"].append({"layer": "W", "code": "doubleSided", "message": "USD declares double-sided geometry; RealityKit backface behavior needs inspection from both sides. Use outward normals and explicit back geometry where needed."})
                rough = set(re.findall(r"inputs:roughness\.connect\s*=\s*<([^>]+)>", text))
                metal = set(re.findall(r"inputs:metallic\.connect\s*=\s*<([^>]+)>", text))
                shared_sampler = {path.split('.outputs:', 1)[0] for path in rough} & {path.split('.outputs:', 1)[0] for path in metal}
                textures = re.findall(r"\basset\s+inputs:file\s*=\s*@([^@]+)@", text)
                reused_image = len(textures) != len(set(textures))
                if rough and metal and (shared_sampler or reused_image):
                    room["warnings"].append({"layer": "W", "code": "packedORM", "message": "Roughness and metallic use connected textures. Inspect for packed ORM and split into independent grayscale images if shared; dark rendering is a platform-dependent risk."})
                room["manifest"] = str(path.relative_to(root))
                report["rooms"].append(room)
                report["errors"].extend(room["errors"])
                report["warnings"].extend(room["warnings"])
                if result.returncode and not room["errors"]:
                    fail("E", "RealityKit checker exited unsuccessfully.")
            report["layers"] += ["E", "W"]
            if renders is not None and all("R" in room["layers"] for room in report["rooms"]):
                report["layers"].append("R")
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, zipfile.BadZipFile, KeyError) as error:
        import room_bindings
        cause = error
        while cause is not None and not isinstance(cause, room_bindings.BindingCheckError):
            cause = cause.__cause__
        if cause is not None:
            if "S" not in report["layers"]:
                report["layers"].append("S")
            fail("B", error)
        else:
            fail("S" if "S" not in report["layers"] else "E", error)
    report["valid"] = not report["errors"]
    report["durationSeconds"] = round(time.monotonic() - started, 3)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--current-app-version", required=True, help="Version actually installed on Vision Pro")
    parser.add_argument("--renders", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = check(args.archive, args.current_app_version, args.renders)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(("VALID" if report["valid"] else "INVALID") + ": " + ", ".join(report["layers"]))
        for level in ("errors", "warnings"):
            for item in report[level]:
                print("%s [%s]: %s" % (level[:-1].upper(), item["layer"], item["message"]))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
