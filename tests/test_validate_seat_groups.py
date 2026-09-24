"""Focused tests for Room v6 seatGroups support (Locus 1.2.0): grouping
existing teleport IDs into one seating-area entry in the Seats picker. A
group's seatIDs must already be authored teleports, and a teleport can
belong to at most one group. Mirrors scripts/validate_seat_groups in the
private Locus repo's scripts/validate_locus_asset.py, and requires
formatVersion 6."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "validate_locus_asset", ROOT / "tools/validate_locus_asset.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SeatGroupValidationTests(unittest.TestCase):
    def teleport_ids(self):
        return {"window-cafe-south", "window-banquette-south", "coffee-bar-stool"}

    def test_valid_groups_leave_a_seat_ungrouped(self):
        groups = [
            {
                "id": "window-tables",
                "title": "Window Tables",
                "seatIDs": ["window-cafe-south", "window-banquette-south"],
            }
        ]
        # "coffee-bar-stool" is intentionally left out of every group: a
        # client keeps it discoverable as a direct row.
        module.validate_seat_groups(groups, self.teleport_ids())

    def test_singleton_group_is_accepted_but_not_required(self):
        # The product's validate_seat_groups (scripts/validate_locus_asset.py)
        # only requires seatIDs to be non-empty; a lone seat does not need a
        # singleton group, but nothing rejects one that is authored anyway.
        groups = [{"id": "solo", "title": "Solo", "seatIDs": ["coffee-bar-stool"]}]
        module.validate_seat_groups(groups, self.teleport_ids())

    def test_unknown_seat_id_is_rejected(self):
        groups = [{"id": "g1", "title": "G1", "seatIDs": ["not-a-real-seat"]}]
        with self.assertRaisesRegex(module.ValidationError, "is not an authored seat"):
            module.validate_seat_groups(groups, self.teleport_ids())

    def test_seat_grouped_twice_is_rejected(self):
        groups = [
            {"id": "g1", "title": "G1", "seatIDs": ["window-cafe-south"]},
            {"id": "g2", "title": "G2", "seatIDs": ["window-cafe-south"]},
        ]
        with self.assertRaisesRegex(module.ValidationError, "already grouped"):
            module.validate_seat_groups(groups, self.teleport_ids())

    def test_duplicate_group_id_is_rejected(self):
        groups = [
            {"id": "g1", "title": "G1", "seatIDs": ["window-cafe-south"]},
            {"id": "g1", "title": "G1 again", "seatIDs": ["coffee-bar-stool"]},
        ]
        with self.assertRaisesRegex(module.ValidationError, "is duplicated"):
            module.validate_seat_groups(groups, self.teleport_ids())

    def test_empty_seat_groups_array_is_rejected(self):
        with self.assertRaisesRegex(module.ValidationError, "non-empty array"):
            module.validate_seat_groups([], self.teleport_ids())

    def test_group_with_no_seats_is_rejected(self):
        groups = [{"id": "g1", "title": "G1", "seatIDs": []}]
        with self.assertRaisesRegex(module.ValidationError, "non-empty array"):
            module.validate_seat_groups(groups, self.teleport_ids())


class RoomFormatVersionGateTests(unittest.TestCase):
    """validate_room's formatVersion gate for seatGroups is checked right
    after decoding space.json, before teleport-points.json or any other room
    file is opened, so these fixtures need only a space.json."""

    def base_metadata(self):
        return {
            "formatVersion": 6,
            "displayName": "Window Tables Room",
            "seatedOrigin": {
                "translationMeters": [0, 0, 0],
                "orientationXYZW": [0, 0, 0, 1],
            },
            "safeHeadVolume": {
                "centerMeters": [0, 1.25, 0],
                "sizeMeters": [1.2, 1, 1.2],
            },
            "viewOpenings": [
                {
                    "id": "surroundings",
                    "transform": {
                        "translationMeters": [0, 1.25, -2],
                        "orientationXYZW": [0, 0, 0, 1],
                    },
                    "widthMeters": 4,
                    "heightMeters": 2.5,
                }
            ],
            "seatGroups": [
                {
                    "id": "window-tables",
                    "title": "Window Tables",
                    "seatIDs": ["window-cafe-south", "window-banquette-south"],
                }
            ],
        }

    def write_space_json(self, directory: Path, metadata: dict) -> Path:
        root = directory
        (root / "space.json").write_text(json.dumps(metadata))
        return root

    def test_seat_groups_on_formatversion_5_is_rejected(self):
        metadata = self.base_metadata()
        metadata["formatVersion"] = 5
        with tempfile.TemporaryDirectory() as directory:
            root = self.write_space_json(Path(directory), metadata)
            with self.assertRaisesRegex(
                module.ValidationError, "seatGroups requires formatVersion 6"
            ):
                module.validate_room(root)

    def test_seat_groups_on_formatversion_6_passes_the_version_gate(self):
        # No teleport-points.json is on disk, so validate_room fails trying to
        # open it once the formatVersion/seatGroups gate and the rest of the
        # space.json-only checks pass -- proving the gate itself accepted v6.
        metadata = self.base_metadata()
        with tempfile.TemporaryDirectory() as directory:
            root = self.write_space_json(Path(directory), metadata)
            with self.assertRaises(FileNotFoundError):
                module.validate_room(root)


if __name__ == "__main__":
    unittest.main()
