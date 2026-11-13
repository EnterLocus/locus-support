"""Room TVs (`tvs`, Locus 1.4.9): the generated Example Media Room and the
complete-package validator's TV rules."""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import pack_locusplace  # noqa: E402
import validate_locusplace  # noqa: E402

BUILDER = ROOT / "examples" / "media-room" / "build_media_room.py"
SPACE = "catalog/spaces/space.example-media-room/space.json"


def load_builder():
    spec = importlib.util.spec_from_file_location("public_media_room_example", BUILDER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


MEDIA_ROOM = load_builder()


class RoomTVPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="locus-room-tv-tests-")
        cls.root = Path(cls.temporary.name)
        cls.editable = MEDIA_ROOM.write_editable(cls.root / "media-room")

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def pack(self, name, edit=None, *, current="1.4.9"):
        source = self.root / ("source-" + name)
        shutil.copytree(self.editable, source)
        if edit is not None:
            space_path = source / SPACE
            envelope_path = source / "locusplace.json"
            space = json.loads(space_path.read_text(encoding="utf-8"))
            envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
            edit(space, envelope)
            space_path.write_text(json.dumps(space), encoding="utf-8")
            envelope_path.write_text(json.dumps(envelope), encoding="utf-8")
        return pack_locusplace.pack(source, self.root / (name + ".locusplace"),
                                    current_app_version=current)

    def assert_rejected(self, name, edit, message):
        with self.assertRaises(validate_locusplace.ValidationError) as caught:
            self.pack(name, edit)
        self.assertIn(message, str(caught.exception))

    def test_example_media_room_packs_and_validates(self):
        summary = self.pack("example")
        self.assertEqual((summary["packageID"], summary["rooms"]),
                         ("place.example-media-room", 1))
        space = json.loads((self.editable / SPACE).read_text(encoding="utf-8"))
        self.assertEqual([tv["entityName"] for tv in space["tvs"]],
                         ["TV_Screen_Living", "TV_Screen_Art"])

    def test_example_requires_locus_1_4_9(self):
        with self.assertRaises(validate_locusplace.ValidationError) as caught:
            self.pack("current-1-4-8", current="1.4.8")
        self.assertIn("package requires Locus 1.4.9", str(caught.exception))

    def test_tvs_require_minimum_app_version_1_4_9(self):
        def edit(space, envelope):
            envelope["minimumAppVersion"] = "1.4.8"
        self.assert_rejected("floor", edit, "tvs requires minimumAppVersion >= 1.4.9")

    def test_tv_shape_rules(self):
        def five(space, _):
            space["tvs"] = [{"id": "tv-%d" % n, "displayName": "TV %d" % n,
                             "entityName": "TV_Screen_Living"} for n in range(5)]

        def duplicate_screen(space, _):
            space["tvs"][1]["entityName"] = "TV_Screen_Living"

        def duplicate_id(space, _):
            space["tvs"][1]["id"] = "living-tv"

        def bad_id(space, _):
            space["tvs"][0]["id"] = "Living TV"

        def blank_name(space, _):
            space["tvs"][0]["displayName"] = " "

        def default_on(space, _):
            space["tvs"][0]["defaultURL"] = "https://example.com/"

        def missing_entity(space, _):
            space["tvs"][0]["entityName"] = "TV_Screen_Missing"

        def unknown_title(space, _):
            space["localizations"]["fr"]["tvTitles"]["kitchen-tv"] = "Cuisine"

        cases = (
            (five, "must contain 1 to 4 TVs"),
            (duplicate_screen, "entityName contains duplicate value TV_Screen_Living"),
            (duplicate_id, "id contains duplicate value living-tv"),
            (bad_id, ".id is invalid"),
            (blank_name, "displayName"),
            (default_on, "unknown field defaultURL"),
            (missing_entity, "'TV_Screen_Missing' is not an entity of"),
            (unknown_title, "tvTitles references unknown ID kitchen-tv"),
        )
        for edit, message in cases:
            with self.subTest(case=edit.__name__):
                self.assert_rejected(edit.__name__, edit, message)


if __name__ == "__main__":
    unittest.main()
