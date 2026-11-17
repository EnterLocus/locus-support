"""Room interactive states (`interactiveStates`, Locus 1.5.1+): schema,
complete-package validation, RealityKit bindings, and check_room coverage."""

from __future__ import annotations

import copy
import json
import platform
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import check_room  # noqa: E402
import room_bindings  # noqa: E402
import room_fixtures  # noqa: E402
import validate_locusplace  # noqa: E402

HAS_REALITYKIT = platform.system() == "Darwin" and shutil.which("xcrun") is not None


def interactive_controls():
    return [
        {
            "id": "door.deck",
            "displayName": "Deck Sliding Door",
            "kind": "opening",
            "targetEntities": ["Door_Frame", "Door_Pull"],
            "defaultStateID": "closed",
            "states": [
                {
                    "id": "closed",
                    "displayName": "Closed",
                    "poses": [
                        {
                            "entityName": "Door_Leaf",
                            "translationMeters": [0.0, 0.0, 0.0],
                            "durationSeconds": 0.9,
                            "timing": "easeInOut",
                            "keyframes": [
                                {
                                    "at": 0.78,
                                    "fromStateIDs": ["breeze", "open"],
                                    "translationMeters": [0.0, 0.0, 0.0],
                                }
                            ],
                        },
                        {
                            "entityName": "Door_Pull",
                            "rotation": {"axis": [0.0, 0.0, 1.0], "angleDegrees": 0.0},
                            "delaySeconds": 0.68,
                            "durationSeconds": 0.22,
                        },
                    ],
                },
                {
                    "id": "breeze",
                    "displayName": "Breeze",
                    "poses": [
                        {
                            "entityName": "Door_Pull",
                            "rotation": {"axis": [0.0, 0.0, 1.0], "angleDegrees": -90.0},
                            "durationSeconds": 0.2,
                            "timing": "easeOut",
                        },
                        {
                            "entityName": "Door_Leaf",
                            "translationMeters": [-0.25, 0.0, 0.0],
                            "durationSeconds": 0.7,
                            "keyframes": [
                                {
                                    "at": 0.2,
                                    "fromStateIDs": ["closed"],
                                    "translationMeters": [0.0, 0.0, 0.0],
                                }
                            ],
                        },
                    ],
                },
                {
                    "id": "open",
                    "displayName": "Open",
                    "poses": [
                        {
                            "entityName": "Door_Pull",
                            "rotation": {"axis": [0.0, 0.0, 1.0], "angleDegrees": -90.0},
                            "durationSeconds": 0.2,
                            "timing": "easeOut",
                        },
                        {
                            "entityName": "Door_Leaf",
                            "translationMeters": [-1.2, 0.0, 0.0],
                            "durationSeconds": 0.9,
                            "keyframes": [
                                {
                                    "at": 0.2,
                                    "fromStateIDs": ["closed"],
                                    "translationMeters": [0.0, 0.0, 0.0],
                                }
                            ],
                        },
                    ],
                },
            ],
        },
        {
            "id": "hearth-fire",
            "displayName": "Hearth Fire",
            "kind": "fire",
            "targetEntities": ["Hearth_Grate"],
            "defaultStateID": "off",
            "states": [
                {
                    "id": "off",
                    "displayName": "Off",
                    "emissives": [{"entityName": "Ember_Bed", "scale": 0.0}],
                    "particleEffects": [{"particleEffectID": "hearth", "intensity": 0.0}],
                },
                {
                    "id": "full",
                    "displayName": "Full Fire",
                    "emissives": [{"entityName": "Ember_Bed", "scale": 1.8, "durationSeconds": 0.6}],
                    "particleEffects": [{"particleEffectID": "hearth", "intensity": 1.2, "durationSeconds": 0.8}],
                },
            ],
        },
    ]


def interactive_room(mutate=None):
    room = room_fixtures.minimal_room()
    room.boxes.extend([
        room_fixtures.blender_box("Door_Frame", (-1.0, 1.9, 1.0), (0.8, 0.06, 2.0), "Dark_Metal"),
        room_fixtures.blender_box("Door_Pull", (-0.65, 1.85, 1.0), (0.04, 0.04, 0.14), "Dark_Metal"),
        room_fixtures.blender_box("Door_Leaf", (-1.0, 1.9, 1.0), (0.02, 0.02, 0.02), "Dark_Metal"),
        room_fixtures.blender_box("Hearth_Grate", (1.2, 1.8, 0.25), (0.5, 0.1, 0.12), "Dark_Metal"),
        room_fixtures.blender_box("Ember_Bed", (1.2, 1.8, 0.10), (0.4, 0.2, 0.04), "Lamp_Glow"),
    ])
    room.extra_usda = '\n    def Xform "Hearth_Fire_Anchor" (\n    )\n    {\n        double3 xformOp:translate = (1.2, 0.14, -1.8)\n        uniform token[] xformOpOrder = ["xformOp:translate"]\n    }\n'
    room.seats = [room_fixtures.minimal_seat(room.boxes)]

    original_v2_space = room.v2_space

    def v2_space():
        space = original_v2_space()
        space["particleEffects"] = [
            {
                "id": "hearth",
                "displayName": "Hearth Fire",
                "preset": "fire",
                "anchorEntity": "Hearth_Fire_Anchor",
                "sizeMeters": [0.3, 0.4, 0.3],
            }
        ]
        space["interactiveStates"] = copy.deepcopy(interactive_controls())
        space["localizations"] = {
            "fr": {
                "interactiveTitles": {
                    "door.deck": "Porte coulissante de terrasse",
                    "door.deck.closed": "Fermée",
                    "door.deck.breeze": "Entrouverte",
                    "door.deck.open": "Ouverte",
                    "hearth-fire": "Feu de cheminée",
                    "hearth-fire.off": "Éteint",
                    "hearth-fire.full": "Grand feu",
                }
            }
        }
        return space

    room.v2_space = v2_space
    if mutate is not None:
        mutate(room)
    return room


class RoomInteractiveStatesTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="locus-interactive-test-")
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def write_edited_v2(self, name: str, edit_space=None, minimum: str = "1.5.1") -> Path:
        def mutate(room):
            base_v2_space = room.v2_space

            def wrapped():
                space = base_v2_space()
                if edit_space is not None:
                    edit_space(space)
                return space

            room.v2_space = wrapped

        room = interactive_room(mutate)
        return room.write_v2(self.root / f"{name}.locusplace", minimum_app_version=minimum)

    def test_schema_uses_public_id_and_has_no_private_references(self):
        schema_path = ROOT / "schemas" / "room-interactive-states-v1.schema.json"
        raw = schema_path.read_text(encoding="utf-8")
        schema = json.loads(raw)
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(
            schema["$id"],
            "https://enterlocus.com/schemas/room-interactive-states-v1.schema.json",
        )
        for forbidden in ("enterlocus.dev", "PackageV2Store", "RoomModelBindingValidator", "docs/package-spec-v2.md"):
            self.assertNotIn(forbidden, raw)

    def test_valid_interactive_states_archive_validates_and_checks(self):
        archive = self.write_edited_v2("valid")
        summary = validate_locusplace.validate(archive, current_app_version="1.5.1")
        self.assertEqual(summary["rooms"], 1)
        if HAS_REALITYKIT:
            report = check_room.check(archive, "1.5.1")
            self.assertTrue(report["valid"], report["errors"])
            self.assertEqual(report["errors"], [])

    def test_app_version_floor_is_enforced(self):
        valid = self.write_edited_v2("valid-151", minimum="1.5.1")
        with self.assertRaisesRegex(validate_locusplace.ValidationError, "package requires Locus 1.5.1"):
            validate_locusplace.validate(valid, current_app_version="1.5.0")

        low_floor = self.write_edited_v2("floor-150", minimum="1.5.0")
        with self.assertRaisesRegex(
            validate_locusplace.ValidationError,
            "interactiveStates requires minimumAppVersion >= 1.5.1",
        ):
            validate_locusplace.validate(low_floor, current_app_version="1.5.1")

    def test_manifest_structural_and_ownership_rejections(self):
        def bad_keyframe_order(space):
            space["interactiveStates"][0]["states"][0]["poses"][0]["keyframes"].append(
                {"at": 0.5, "translationMeters": [0.0, 0.01, 0.0]}
            )

        def unknown_from_state(space):
            space["interactiveStates"][0]["states"][1]["poses"][1]["keyframes"][0]["fromStateIDs"] = ["missing"]

        def cross_control_pose_collision(space):
            space["interactiveStates"][1]["states"][1]["poses"] = [
                {"entityName": "Door_Pull", "translationMeters": [0.0, 0.01, 0.0]}
            ]

        def unknown_particle(space):
            space["interactiveStates"][1]["states"][1]["particleEffects"][0]["particleEffectID"] = "missing-fire"

        def bad_interactive_title(space):
            space["localizations"]["fr"]["interactiveTitles"]["door.deck.unknown"] = "Inconnu"

        def emissive_overlaps_luminaire_group(space):
            space["interactiveStates"][1]["states"][1]["emissives"][0]["entityName"] = "Pendant_Glow"

        cases = (
            (bad_keyframe_order, "at must be strictly increasing in (0, 1)"),
            (unknown_from_state, "fromStateIDs contains invalid or duplicate id"),
            (cross_control_pose_collision, "owns a pose entity already owned by another control"),
            (unknown_particle, "particleEffectID is unknown or duplicated within state"),
            (bad_interactive_title, "interactiveTitles references unknown ID"),
            (emissive_overlaps_luminaire_group, "overlaps lighting entities"),
        )
        for edit, expected_msg in cases:
            with self.subTest(case=edit.__name__):
                archive = self.write_edited_v2(edit.__name__, edit_space=edit)
                with self.assertRaises(validate_locusplace.ValidationError) as caught:
                    validate_locusplace.validate(archive, current_app_version="1.5.1")
                self.assertIn(expected_msg, str(caught.exception))

    @unittest.skipUnless(HAS_REALITYKIT, "RealityKit binding check requires macOS with Xcode")
    def test_realitykit_binding_and_check_room_emissive_rules(self):
        def non_emissive_target(space):
            space["interactiveStates"][1]["states"][0]["emissives"][0]["entityName"] = "Table_Top"
            space["interactiveStates"][1]["states"][1]["emissives"][0]["entityName"] = "Table_Top"

        bad_emissive = self.write_edited_v2("non-emissive", edit_space=non_emissive_target)
        with self.assertRaisesRegex(validate_locusplace.ValidationError, "has no positive-emissive material"):
            validate_locusplace.validate(bad_emissive, current_app_version="1.5.1")

        # Also check missing entity error in space.json against scene prims.
        def missing_target(space):
            space["interactiveStates"][0]["targetEntities"].append("Missing_Target")

        missing = self.write_edited_v2("missing-target", edit_space=missing_target)
        with self.assertRaisesRegex(validate_locusplace.ValidationError, "is not an entity of"):
            validate_locusplace.validate(missing, current_app_version="1.5.1")

        # Verify RoomBindings directly catches non-emissive material when called standalone.
        with zipfile.ZipFile(bad_emissive) as zf:
            tmp = self.root / "standalone"
            tmp.mkdir()
            scene = tmp / "scene.usdz"
            space_file = tmp / "space.json"
            scene.write_bytes(zf.read("catalog/spaces/space.minimal-reading-room/scene.usdz"))
            space_file.write_bytes(zf.read("catalog/spaces/space.minimal-reading-room/space.json"))
            with self.assertRaisesRegex(room_bindings.BindingCheckError, "has no positive-emissive material"):
                room_bindings.check(scene, space_file)


if __name__ == "__main__":
    unittest.main()
