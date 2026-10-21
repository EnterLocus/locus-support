"""Public flat Room music contract and the packer's real validation path."""

import importlib.util
import io
import json
import struct
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load_tool(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator = load_tool("validate_locus_asset")
with patch.dict(sys.modules, {"validate_locus_asset": validator}):
    packer = load_tool("pack_locus_asset")


def sound_source(identifier="music", *, role="music", gain=0.3):
    return {
        "id": identifier,
        "title": identifier.title(),
        "clips": [f"{identifier}.wav"],
        "role": role,
        "gain": gain,
        "placement": {"type": "ambient"},
        "playback": {"type": "loop"},
    }


def sound_definition(*sources, version=2):
    return {"version": version, "backgroundPriority": 0, "sources": list(sources)}


def write_sound(root, definition):
    (root / "sound.json").write_text(json.dumps(definition), encoding="utf-8")
    for source in definition["sources"]:
        for name in source.get("clips", [source.get("path")]):
            if name:
                # Like the app importer fixture, these bytes exercise declared
                # assets and packaging, not audio decoding or playback quality.
                (root / name).write_bytes(b"RIFF-fixture")


class RoomMusicValidationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def validate(self, definition, *, owner="room"):
        write_sound(self.root, definition)
        validator.validate_sound_sidecar(
            self.root, {path.name for path in self.root.iterdir()}, owner=owner)

    def test_room_music_can_coexist_with_background_and_effect(self):
        music = sound_source()
        music["playback"].update(fadeInSeconds=0.5, fadeOutSeconds=1)
        self.validate(sound_definition(
            music, sound_source("rain", role="background"),
            sound_source("bird", role="effect")))

    def test_existing_sound_v1_roles_remain_valid_for_views(self):
        sources = []
        for role in ("background", "effect"):
            source = sound_source(role, role=role)
            source["path"] = source.pop("clips")[0]
            del source["placement"], source["playback"]
            sources.append(source)
        self.validate(sound_definition(*sources, version=1), owner="view")

    def test_view_music_is_rejected(self):
        with self.assertRaisesRegex(validator.ValidationError, "only by Rooms"):
            self.validate(sound_definition(sound_source()), owner="view")

    def test_sound_v1_music_is_rejected(self):
        source = sound_source()
        source["path"] = source.pop("clips")[0]
        del source["placement"], source["playback"]
        with self.assertRaisesRegex(validator.ValidationError, "requires sound version 2"):
            self.validate(sound_definition(source, version=1))

    def test_spatial_music_is_rejected(self):
        source = sound_source()
        source["placement"] = {
            "type": "point", "frame": "room", "point": {"positionMeters": [0, 1, 0]}}
        with self.assertRaisesRegex(validator.ValidationError, "requires ambient placement"):
            self.validate(sound_definition(source))

    def test_random_music_is_rejected(self):
        source = sound_source()
        source["playback"] = {
            "type": "random", "intervalSeconds": [1, 2], "maxConcurrent": 1}
        with self.assertRaisesRegex(validator.ValidationError, "loop playback"):
            self.validate(sound_definition(source))

    def test_multiple_music_clips_are_rejected(self):
        source = sound_source()
        source["clips"].append("second.wav")
        with self.assertRaisesRegex(validator.ValidationError, "exactly one clip"):
            self.validate(sound_definition(source))

    def test_multiple_music_sources_are_rejected(self):
        with self.assertRaisesRegex(validator.ValidationError, "at most one music source"):
            self.validate(sound_definition(sound_source(), sound_source("second")))

    def test_music_counts_toward_eight_source_limit(self):
        sources = [sound_source(gain=0.125)] + [
            sound_source(f"effect-{index}", role="effect", gain=0.125)
            for index in range(7)]
        self.validate(sound_definition(*sources))
        sources.append(sound_source("ninth", role="background", gain=0))
        with self.assertRaisesRegex(validator.ValidationError, "1 through 8 sources"):
            self.validate(sound_definition(*sources))

    def test_music_counts_toward_total_gain_limit(self):
        with self.assertRaisesRegex(validator.ValidationError, "gain may total at most 1"):
            self.validate(sound_definition(
                sound_source(gain=0.6), sound_source("rain", role="background", gain=0.5)))

    def test_music_still_requires_its_audio_file(self):
        write_sound(self.root, sound_definition(sound_source()))
        (self.root / "music.wav").unlink()
        with self.assertRaisesRegex(validator.ValidationError, "missing audio file"):
            validator.validate_sound_sidecar(self.root, {"sound.json"}, owner="room")


class RoomMusicPackerTests(unittest.TestCase):
    def make_room(self, root):
        source = root / "room"
        source.mkdir()
        # Reuse only existing public metadata and thumbnail; the tiny model
        # keeps this real USD/RealityKit validation test inexpensive.
        with zipfile.ZipFile(ROOT / "examples/atrium-loft-room.zip") as archive:
            for name in ("space.json", "teleport-points.json", "provenance.json", "thumbnail.jpg"):
                (source / name).write_bytes(archive.read(name))
        manifest = json.loads((source / "space.json").read_text())
        for field in ("spatialAdaptation", "lighting", "ambientAnimations", "rendering"):
            manifest.pop(field, None)
        (source / "space.json").write_text(json.dumps(manifest), encoding="utf-8")
        model = io.BytesIO()
        with zipfile.ZipFile(model, "w") as archive:
            info = zipfile.ZipInfo("root.usda")
            padding = (-(30 + len(info.filename.encode()) + 4)) % 64
            info.extra = struct.pack("<HH", 0xFFFF, padding) + bytes(padding)
            archive.writestr(info, b'''#usda 1.0
(defaultPrim = "Root"
 upAxis = "Y"
 metersPerUnit = 1)
def Xform "Root" {
 def Cube "Box" {
  double size = 1
 }
}
''')
        (source / "scene.usdz").write_bytes(model.getvalue())
        return source

    def test_packer_accepts_room_music_and_rejects_invalid_music_without_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.make_room(root)
            music = sound_source()
            write_sound(source, sound_definition(music))
            output = root / "music-room.zip"
            summary = packer.pack(source, output)
            self.assertEqual(summary["kind"], "room")
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(json.loads(archive.read("sound.json")), sound_definition(music))
                self.assertEqual(archive.read("music.wav"), b"RIFF-fixture")
            accepted_bytes = output.read_bytes()
            music["playback"] = {
                "type": "random", "intervalSeconds": [1, 2], "maxConcurrent": 1}
            write_sound(source, sound_definition(music))
            rejected = root / "rejected.zip"
            with self.assertRaisesRegex(validator.ValidationError, "loop playback"):
                packer.pack(source, rejected)
            self.assertFalse(rejected.exists())
            self.assertFalse(list(root.glob(".*.packing-*")))
            self.assertEqual(output.read_bytes(), accepted_bytes)


if __name__ == "__main__":
    unittest.main()
