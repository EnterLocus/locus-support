"""Generate small Room fixtures from source for the validator tests.

Nothing here is committed as a binary. `minimal_room()` mirrors the geometry,
names, materials and metadata that `tools/build_minimal_room.py` exports from
Blender (one desk, one seat, two walls, a roof and one emissive pendant), but
writes the USD directly so tests run in seconds without Blender. Each fixture
can be mutated to produce one specific defect.
"""

from __future__ import annotations

import copy
import hashlib
import io
import json
import struct
import sys
import zipfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
import external_assets
SPACE_ID = "space.minimal-reading-room"
SEAT_ID = "seat.primary"

PROVENANCE = {
    "formatVersion": 1,
    "creatorOrAgency": "EnterLocus.com",
    "license": {
        "identifier": "Apache-2.0",
        "name": "Apache License 2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0",
    },
    "requestedCredit": "Synthetic validator fixture by EnterLocus.com",
    "modificationNotes": "Generated locally by the public validator tests.",
    "aiGenerated": False,
}

# name: (diffuse RGB, roughness, emissive RGB or None, opacity)
MATERIALS: Dict[str, tuple] = {
    "Warm_Wood": ((0.38, 0.20, 0.09), 0.7, None, 1.0),
    "Light_Plaster": ((0.73, 0.69, 0.59), 0.85, None, 1.0),
    "Dark_Metal": ((0.06, 0.075, 0.08), 0.65, None, 1.0),
    "Lamp_Glow": ((1.0, 0.64, 0.30), 0.5, (1.0, 0.64, 0.30), 1.0),
}


def blender_box(name, position, dimensions, material):
    """One `tools/build_minimal_room.py` box, converted from Blender's Z-up
    (x, y, z) to the exported Y-up USD frame (x, z, -y)."""
    x, y, z = position
    sx, sy, sz = dimensions
    return {"name": name, "center": (x, z, -y), "size": (sx, sz, sy),
            "material": material}


def minimal_boxes() -> List[dict]:
    boxes = [
        blender_box("Floor", (0, 0, -.08), (4, 4, .16), "Warm_Wood"),
        blender_box("Back_Wall", (0, -1.95, 1.3), (4, .1, 2.6), "Light_Plaster"),
        blender_box("Left_Wall", (-1.95, 0, 1.3), (.1, 4, 2.6), "Light_Plaster"),
        blender_box("Roof", (0, 0, 2.65), (4, 4, .1), "Light_Plaster"),
        blender_box("Table_Top", (0, .4, .70), (1.5, .7, .08), "Warm_Wood"),
    ]
    for number, (x, y) in enumerate([(-.65, .12), (.65, .12), (-.65, .68), (.65, .68)]):
        boxes.append(blender_box(f"Table_Leg_{number}", (x, y, .33), (.07, .07, .66), "Dark_Metal"))
    boxes.append(blender_box("Chair_Seat", (0, -.45, .44), (.5, .5, .08), "Warm_Wood"))
    boxes.append(blender_box("Chair_Back", (0, -.69, .70), (.5, .06, .55), "Warm_Wood"))
    for number, (x, y) in enumerate([(-.2, -.65), (.2, -.65), (-.2, -.25), (.2, -.25)]):
        boxes.append(blender_box(f"Chair_Leg_{number}", (x, y, .2), (.06, .06, .4), "Dark_Metal"))
    boxes.append(blender_box("Pendant_Stem", (0, .4, 2.42), (.035, .035, .36), "Dark_Metal"))
    boxes.append(blender_box("Pendant_Glow", (0, .4, 2.21), (.32, .32, .06), "Lamp_Glow"))
    return boxes


def _number(value: float) -> str:
    return repr(round(float(value), 6))


def _box_mesh(box: dict) -> str:
    cx, cy, cz = box["center"]
    sx, sy, sz = box["size"]
    points = []
    for index in range(8):
        xb, yb, zb = (index >> 2) & 1, (index >> 1) & 1, index & 1
        points.append("(%s, %s, %s)" % (
            _number(cx + (xb - .5) * sx), _number(cy + (yb - .5) * sy),
            _number(cz + (zb - .5) * sz)))
    faces = [0, 1, 3, 2, 4, 6, 7, 5, 0, 4, 5, 1, 2, 3, 7, 6, 0, 2, 6, 4, 1, 5, 7, 3]
    return _mesh_body(points, [4] * 6, faces)


def _plane_mesh(box: dict) -> str:
    """A zero-thickness rectangle in the XZ plane at the box center."""
    cx, cy, cz = box["center"]
    sx, _, sz = box["size"]
    points = ["(%s, %s, %s)" % (_number(cx + dx * sx / 2), _number(cy), _number(cz + dz * sz / 2))
              for dx, dz in ((-1, -1), (-1, 1), (1, 1), (1, -1))]
    return _mesh_body(points, [4], [0, 1, 2, 3])


def _mesh_body(points, counts, indices) -> str:
    return (
        "            int[] faceVertexCounts = [%s]\n"
        "            int[] faceVertexIndices = [%s]\n"
        "            point3f[] points = [%s]\n"
        '            uniform token subdivisionScheme = "none"\n'
    ) % (", ".join(map(str, counts)), ", ".join(map(str, indices)), ", ".join(points))


def _material(name: str, spec: tuple) -> str:
    diffuse, roughness, emissive, opacity = spec
    lines = [
        '        def Material "%s"' % name,
        "        {",
        '            token outputs:surface.connect = </root/_materials/%s/Surface.outputs:surface>' % name,
        '            def Shader "Surface"',
        "            {",
        '                uniform token info:id = "UsdPreviewSurface"',
        "                color3f inputs:diffuseColor = (%s, %s, %s)" % tuple(map(_number, diffuse)),
        "                float inputs:roughness = %s" % _number(roughness),
        "                float inputs:metallic = 0",
        "                float inputs:opacity = %s" % _number(opacity),
    ]
    if emissive is not None:
        lines.append("                color3f inputs:emissiveColor = (%s, %s, %s)"
                     % tuple(map(_number, emissive)))
    lines += [
        "                token outputs:surface",
        "            }",
        "        }",
    ]
    return "\n".join(lines) + "\n"


def _prim(box: dict, boxes: List[dict], depth: int) -> str:
    pad = "    " * depth
    shape = box.get("shape", "box")
    lines = ['%sdef Xform "%s"' % (pad, box["name"]), pad + "{"]
    if "translate" in box:
        lines.append("%s    double3 xformOp:translate = (%s, %s, %s)"
                     % ((pad,) + tuple(map(_number, box["translate"]))))
        lines.append('%s    uniform token[] xformOpOrder = ["xformOp:translate"]' % pad)
    if shape != "group":
        body = _plane_mesh(box) if shape == "plane" else _box_mesh(box)
        material = box.get("material")
        header = '%s    def Mesh "%s_Geometry"' % (pad, box["name"])
        if material is not None:
            header += ' (\n%s        prepend apiSchemas = ["MaterialBindingAPI"]\n%s    )' % (pad, pad)
        lines += [header, pad + "    {"]
        lines += [pad + "        " + line.strip()
                  for line in body.rstrip("\n").split("\n")]
        if material is not None:
            lines.append("%s        rel material:binding = </root/_materials/%s>" % (pad, material))
        if box.get("doubleSided"):
            lines.append("%s        uniform bool doubleSided = 1" % pad)
        lines.append(pad + "    }")
    for child in boxes:
        if child.get("parent") == box["name"]:
            lines.append(_prim(child, boxes, depth + 1).rstrip("\n"))
    lines.append(pad + "}")
    return "\n".join(lines) + "\n"


def room_usda(boxes: List[dict], materials: Optional[Dict[str, tuple]] = None,
              extra: str = "") -> bytes:
    """A Y-up, meter-scale stage shaped like Blender's export: `/root` holds
    one Xform per object with a `<name>_Geometry` mesh child. A box may set
    `parent` (nest inside another Xform), `shape` ("box", "plane" or
    "group" for an Xform without a mesh) and `doubleSided`."""
    materials = MATERIALS if materials is None else materials
    parts = [
        '#usda 1.0\n(\n    defaultPrim = "root"\n    metersPerUnit = 1\n'
        '    upAxis = "Y"\n)\n\ndef Xform "root"\n{\n',
    ]
    for box in boxes:
        if box.get("parent") is None:
            parts.append(_prim(box, boxes, 1))
    parts.append(extra)
    parts.append('    def Scope "_materials"\n    {\n')
    for name, spec in materials.items():
        parts.append(_material(name, spec))
    parts.append("    }\n}\n")
    return "".join(parts).encode("utf-8")


def usdz_bytes(layers: Dict[str, bytes]) -> bytes:
    """Store every layer uncompressed with 64-byte aligned data, like usdzip."""
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name, data in layers.items():
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            padding = (-(output.tell() + 30 + len(name.encode()) + 4)) % 64
            info.extra = struct.pack("<HH", 0xFFFF, padding) + bytes(padding)
            archive.writestr(info, data)
    return output.getvalue()


def bounds(boxes: List[dict]):
    lo = [min(b["center"][i] - b["size"][i] / 2 for b in boxes) for i in range(3)]
    hi = [max(b["center"][i] + b["size"][i] / 2 for b in boxes) for i in range(3)]
    return lo, hi


def minimal_space(boxes: List[dict]) -> dict:
    """The flat `space.json` the public scaffolder writes for this Room."""
    ui_fade = [b["name"] for b in boxes if b["name"].startswith(("Table_", "Chair_"))]
    return {
        "formatVersion": 5,
        "displayName": "Minimal Reading Room",
        "caption": "One desk, one seat, and one light.",
        "previewCamera": {"yawDegrees": 0, "pitchDegrees": -8, "zoom": 0.8},
        "seatedOrigin": {"translationMeters": [0, 0, 0], "orientationXYZW": [0, 0, 0, 1]},
        "safeHeadVolume": {"centerMeters": [0, 1.2, 0], "sizeMeters": [1.2, 0.8, 1.2]},
        "viewOpenings": [{
            "id": "surroundings",
            "transform": {"translationMeters": [0, 1.4, -2],
                          "orientationXYZW": [0, 0, 0, 1]},
            "widthMeters": 4,
            "heightMeters": 2.5,
        }],
        "spatialAdaptation": {
            "wallEntities": ["Back_Wall", "Left_Wall"],
            "roofEntities": ["Roof"],
            "deskEntitiesByTeleportID": {SEAT_ID: "Table_Top"},
        },
        "lighting": {"luminaireGroups": [{
            "id": "primary-pendant",
            "displayName": "Primary Pendant",
            "entities": ["Pendant_Glow"],
            "authoredColor": {"mode": "temperature", "kelvin": 2700},
            "controls": {"brightnessEVRange": [-4, 1],
                         "temperatureKelvinRange": [2000, 6500],
                         "supportsFullColor": False},
            "proxy": {"type": "spot", "anchorEntity": "Pendant_Glow",
                      "intensityLumens": 650.0, "attenuationRadiusMeters": 3.5,
                      "colorTemperatureKelvin": 2700, "innerAngleDegrees": 30,
                      "outerAngleDegrees": 70, "castsShadow": False,
                      "direction": [0.0, -1.0, 0.0]},
        }]},
        "rendering": {"softenedReflectionEntities": [], "uiFadeEntities": ui_fade},
    }


def minimal_seat(boxes: List[dict]) -> dict:
    lo, hi = bounds(boxes)
    # The authored seat is Blender (0, -.45) -> USD (x=0, z=.45).
    return {
        "id": SEAT_ID,
        "title": "Reading Desk",
        "anchorXZ": [(0 - lo[0]) / (hi[0] - lo[0]), (.45 - lo[2]) / (hi[2] - lo[2])],
        "sourceFloorOffset": -lo[1],
        "eyeHeight": 1.2,
        "yawRadians": 0,
    }


class Room:
    """An editable Room fixture: geometry, materials and flat metadata."""

    def __init__(self):
        self.boxes = minimal_boxes()
        self.materials = copy.deepcopy(MATERIALS)
        self.space = minimal_space(self.boxes)
        self.seats = [minimal_seat(self.boxes)]
        self.extra_usda = ""
        self.extra_layers: Dict[str, bytes] = {}

    def box(self, name: str) -> dict:
        return next(b for b in self.boxes if b["name"] == name)

    def usdz(self) -> bytes:
        layers = {"scene.usda": room_usda(self.boxes, self.materials, self.extra_usda)}
        layers.update(self.extra_layers)
        return usdz_bytes(layers)

    def thumbnail(self) -> bytes:
        with zipfile.ZipFile(external_assets.hydrate("examples/atrium-loft-room.zip")) as source:
            return source.read("thumbnail.jpg")

    # Flat compatibility ZIP -------------------------------------------------

    def flat_files(self) -> Dict[str, bytes]:
        return {
            "space.json": _json(self.space),
            "teleport-points.json": _json({"formatVersion": 1, "points": self.seats}),
            "provenance.json": _json(PROVENANCE),
            "scene.usdz": self.usdz(),
            "thumbnail.jpg": self.thumbnail(),
        }

    def write_flat(self, output: Path) -> Path:
        with zipfile.ZipFile(output, "x") as archive:
            for name, data in sorted(self.flat_files().items()):
                archive.writestr(name, data)
        return output

    # Package v2 -------------------------------------------------------------

    def v2_space(self) -> dict:
        flat = self.space
        space = {
            "formatVersion": 2,
            "id": SPACE_ID,
            "title": flat["displayName"],
            "scene": "scene.usdz",
            "thumbnail": "thumbnail.jpg",
            "caption": flat["caption"],
            "previewCamera": flat["previewCamera"],
            "seatedOrigin": flat["seatedOrigin"],
            "safeHeadVolume": flat["safeHeadVolume"],
            "destinationOpenings": flat["viewOpenings"],
            "collision": {"mode": "embedded"},
            "teleportCatalog": {"path": "teleport-points.json", "houseID": SPACE_ID},
            "quality": {"status": "unverified", "triangleCount": 0,
                        "materialCount": 0, "entityCount": 0,
                        "maxTextureDimension": 0},
            "provenance": "provenance.json",
        }
        for field in ("spatialAdaptation", "lighting", "rendering",
                      "ambientAnimations", "seatGroups"):
            if field in flat:
                space[field] = flat[field]
        return space

    def v2_payload(self) -> Dict[str, bytes]:
        base = "catalog/spaces/" + SPACE_ID
        return {
            base + "/space.json": _json(self.v2_space()),
            base + "/scene.usdz": self.usdz(),
            base + "/thumbnail.jpg": self.thumbnail(),
            base + "/teleport-points.json": _json({"houses": {SPACE_ID: self.seats}}),
            base + "/provenance.json": _json(PROVENANCE),
        }

    def write_v2(self, output: Path, minimum_app_version: str = "1.2.1") -> Path:
        payload = self.v2_payload()
        records = [{"path": path, "byteCount": len(data),
                    "sha256": hashlib.sha256(data).hexdigest()}
                   for path, data in sorted(payload.items())]
        envelope = {
            "formatVersion": 1,
            "packageID": "place.minimal-reading-room",
            "contentVersion": "1.0.0",
            "minimumAppVersion": minimum_app_version,
            "contents": {"destinationIDs": [], "spaceIDs": [SPACE_ID],
                         "experienceIDs": []},
            "files": records,
            "contentHash": _content_hash(records),
        }
        with zipfile.ZipFile(output, "x", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("locusplace.json", _json(envelope))
            for path, data in sorted(payload.items()):
                archive.writestr(path, data)
        return output


def minimal_room(mutate: Optional[Callable[[Room], Any]] = None) -> Room:
    room = Room()
    if mutate is not None:
        mutate(room)
    return room


def _json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _content_hash(records) -> str:
    canonical = bytearray()
    for record in sorted(records, key=lambda item: item["path"]):
        for part in (record["path"], str(record["byteCount"]), record["sha256"]):
            canonical.extend(part.encode("utf-8"))
            canonical.append(0)
    return hashlib.sha256(canonical).hexdigest()
