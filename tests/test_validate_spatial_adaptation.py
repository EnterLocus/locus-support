"""Focused tests for validate_spatial_adaptation's deskGroupEntitiesByTeleportID
support (Locus 1.1.5): a hideable-desk group must name a seat that already has
a deskEntitiesByTeleportID mapping. A lounge seat with no desk mapping at all
remains valid and untouched by this field."""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "validate_locus_asset", ROOT / "tools/validate_locus_asset.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SpatialAdaptationDeskGroupTests(unittest.TestCase):
    def base_adaptation(self):
        return {
            "wallEntities": [],
            "roofEntities": [],
            "deskEntitiesByTeleportID": {"seat.window": "Window_Desk_Top"},
        }

    def test_lounge_seat_without_any_desk_mapping_is_valid(self):
        adaptation = {
            "wallEntities": [],
            "roofEntities": [],
            "deskEntitiesByTeleportID": {},
        }
        module.validate_spatial_adaptation(adaptation, {"seat.sofa"})

    def test_desk_group_entry_requires_matching_desk_entity(self):
        adaptation = self.base_adaptation()
        adaptation["deskGroupEntitiesByTeleportID"] = {
            "seat.window": "Window_Desk_Group"
        }
        module.validate_spatial_adaptation(adaptation, {"seat.window"})

    def test_desk_group_entry_without_desk_entity_is_rejected(self):
        adaptation = {
            "wallEntities": [],
            "roofEntities": [],
            "deskEntitiesByTeleportID": {},
            "deskGroupEntitiesByTeleportID": {"seat.sofa": "Sofa_Group"},
        }
        with self.assertRaisesRegex(module.ValidationError, "desk group mapping"):
            module.validate_spatial_adaptation(adaptation, {"seat.sofa"})

    def test_desk_group_entry_with_blank_value_is_rejected(self):
        adaptation = self.base_adaptation()
        adaptation["deskGroupEntitiesByTeleportID"] = {"seat.window": "   "}
        with self.assertRaisesRegex(module.ValidationError, "desk group mapping"):
            module.validate_spatial_adaptation(adaptation, {"seat.window"})

    def test_desk_group_entry_for_unknown_teleport_is_rejected(self):
        adaptation = self.base_adaptation()
        adaptation["deskGroupEntitiesByTeleportID"] = {
            "seat.unknown": "Unknown_Group"
        }
        with self.assertRaisesRegex(module.ValidationError, "desk group mapping"):
            module.validate_spatial_adaptation(adaptation, {"seat.window"})

    def test_desk_group_map_must_be_an_object(self):
        adaptation = self.base_adaptation()
        adaptation["deskGroupEntitiesByTeleportID"] = ["Window_Desk_Group"]
        with self.assertRaisesRegex(
            module.ValidationError, "deskGroupEntitiesByTeleportID must be an object"
        ):
            module.validate_spatial_adaptation(adaptation, {"seat.window"})


if __name__ == "__main__":
    unittest.main()
