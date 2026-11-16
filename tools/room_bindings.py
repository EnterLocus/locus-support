"""Run Locus's RealityKit Room entity-binding check from Python.

Both public validators use this module: `validate_locus_asset.py` for a flat
Room ZIP and `validate_locusplace.py` for every Room in a Package v2. The
Swift source lives once, in the `room-bindings/` directory beside this file,
and is compiled with `xcrun --sdk macosx swiftc` into a private temporary
directory on first use (one executable per Python process; a shared cache
entry is never executed). Requires macOS with Xcode or the Command Line Tools.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Any, Optional

SWIFT_DIRECTORY = Path(__file__).resolve().parent / "room-bindings"
SWIFT_SOURCES = ("RoomBindings.swift", "ValidateRoomBindings.swift")

# Top-level `space.json` fields whose values can name model entities. When
# none is present the app's binding contract has no names, and Locus does not
# load the model during import; the check is skipped the same way.
ENTITY_REFERENCE_FIELDS = (
    "spatialAdaptation",
    "rendering",
    "lighting",
    "ambientAnimations",
    "videoSurfaces",
    "particleEffects",
    "textureFlow",
    "tvs",
)


class BindingCheckError(ValueError):
    """The shared Swift check rejected the Room (or could not run)."""


class BindingToolError(BindingCheckError):
    """The shared Swift check could not be built or started."""


def references_entities(space: Any) -> bool:
    return isinstance(space, dict) and any(
        space.get(field) is not None for field in ENTITY_REFERENCE_FIELDS
    )


def swift_sources() -> list:
    return [SWIFT_DIRECTORY / name for name in SWIFT_SOURCES]


def compile_command(output: Path) -> list:
    return [
        "xcrun", "--sdk", "macosx", "swiftc", "-parse-as-library",
        *map(str, swift_sources()), "-o", str(output),
    ]


_tool_directory: Optional[tempfile.TemporaryDirectory] = None


def _executable() -> Path:
    global _tool_directory
    if _tool_directory is None:
        missing = [str(path) for path in swift_sources() if not path.is_file()]
        if missing:
            raise BindingToolError(
                "Room binding check source is missing; keep the room-bindings/ "
                "directory beside the validator: " + ", ".join(missing))
        directory = tempfile.TemporaryDirectory(prefix="locus-binding-validator-")
        output = Path(directory.name) / "validate-room-bindings"
        try:
            result = subprocess.run(
                compile_command(output), capture_output=True, text=True,
                timeout=300, check=False)
        except FileNotFoundError as error:
            directory.cleanup()
            raise BindingToolError(
                "Could not build RealityKit binding validator (macOS with Xcode "
                "or the Command Line Tools is required): xcrun was not found"
            ) from error
        except subprocess.TimeoutExpired as error:
            directory.cleanup()
            raise BindingToolError(
                "Room binding validator compilation timed out") from error
        if result.returncode != 0:
            directory.cleanup()
            raise BindingToolError(
                "Could not build RealityKit binding validator (Xcode is required): "
                + result.stderr[-4000:])
        _tool_directory = directory
    return Path(_tool_directory.name) / "validate-room-bindings"


def check(model: Path, space_json: Path, *, model_budget: bool = False) -> None:
    """Raise BindingCheckError unless the Room's entity bindings resolve.

    With `model_budget`, also apply the flat ZIP's ModelIO model budget first.
    """
    command = [str(_executable())]
    if model_budget:
        command.append("--model-budget")
    command += [str(model), str(space_json)]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=180, check=False)
    except subprocess.TimeoutExpired as error:
        raise BindingCheckError("entity binding validation timed out") from error
    if result.returncode != 0:
        raise BindingCheckError(
            result.stderr.strip()[-4000:] or "RealityKit could not load the model")
