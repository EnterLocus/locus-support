"""End-to-end command-line checks for the public Room checker.

These use source-generated USDZ archives and invoke ``tools/check_room.py``
as an author would.  The checker therefore performs its real Package/flat
validation, RealityKit binding load, and entry-condition inspection; this
module has no test-only checker seam or substitute implementation.
"""

from __future__ import annotations

import json
import platform
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests import room_fixtures


ROOT = Path(__file__).resolve().parents[1]
CHECK_ROOM = ROOT / "tools" / "check_room.py"


def introduce_binding_typo(room: room_fixtures.Room) -> None:
    room.space["spatialAdaptation"]["deskEntitiesByTeleportID"][
        room_fixtures.SEAT_ID
    ] = "Table_Top_TYPO"


@unittest.skipUnless(
    platform.system() == "Darwin",
    "Room checking requires macOS RealityKit; no reduced validation is provided",
)
class CheckRoomCLITests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="locus-check-room-cli-")
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_checker(self, archive: Path, *arguments: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                sys.executable,
                str(CHECK_ROOM),
                str(archive),
                "--current-app-version",
                "1.4.4",
                "--json",
                *arguments,
            ],
            capture_output=True,
            text=True,
            timeout=360,
        )

    def assert_valid(self, archive: Path) -> dict:
        result = self.run_checker(archive)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["valid"])
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["layers"], ["S", "B", "E", "W"])
        self.assertEqual(len(report["rooms"]), 1)
        return report

    def assert_binding_typo_rejected(self, archive: Path) -> None:
        result = self.run_checker(archive)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertFalse(report["valid"])
        self.assertIn("Table_Top_TYPO", report["errors"][0]["message"])

    def test_minimal_flat_room_passes(self) -> None:
        report = self.assert_valid(
            room_fixtures.Room().write_flat(self.root / "minimal-flat.zip")
        )
        self.assertEqual(report["summary"]["kind"], "room")

    def test_minimal_v2_room_passes(self) -> None:
        report = self.assert_valid(
            room_fixtures.Room().write_v2(self.root / "minimal-v2.locusplace")
        )
        self.assertEqual(report["summary"]["packageID"], "place.minimal-reading-room")

    def test_flat_binding_typo_is_rejected(self) -> None:
        room = room_fixtures.Room()
        introduce_binding_typo(room)
        self.assert_binding_typo_rejected(room.write_flat(self.root / "typo-flat.zip"))

    def test_v2_binding_typo_is_rejected(self) -> None:
        room = room_fixtures.Room()
        introduce_binding_typo(room)
        self.assert_binding_typo_rejected(room.write_v2(self.root / "typo-v2.locusplace"))

    def test_explicit_current_app_version_is_required(self) -> None:
        archive = room_fixtures.Room().write_flat(self.root / "minimal-flat.zip")
        result = subprocess.run(
            [sys.executable, str(CHECK_ROOM), str(archive)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("--current-app-version", result.stderr)


if __name__ == "__main__":
    unittest.main()
